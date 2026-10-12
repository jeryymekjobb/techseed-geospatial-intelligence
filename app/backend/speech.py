"""Reading the satellite monitor's new log lines aloud through the computer's speakers.

The satellite monitor (monitor.js) chooses the lines and their voices and sends them to
POST /api/speak; this module speaks them one at a time in Swedish with Piper, a neural speech
synthesis that runs offline, the voices "nst" and "alma" taking turns, one message each
(VOICES, fetched to data/voices/ by tools/fetch_piper_voices.py). Each line is synthesised to a
WAV file and played with pw-play. Without Piper or a voice's model the line is read with
speech-dispatcher's Swedish espeak-ng voice instead (`spd-say -l sv`). The browser's own speech
synthesis is not used: Chrome on the exhibition PC lists no voices and then speaks English.

At most MAX_QUEUED lines wait; older ones are dropped, so the voice never falls far behind the
scenario clock. `stop` empties the queue and cancels what is being said.
"""

from __future__ import annotations

import subprocess
import tempfile
import threading
import wave
from collections import deque
from pathlib import Path
from typing import Any, Callable, Sequence

from app.backend.scenarios import REPO_ROOT

MAX_QUEUED = 4
MAX_SENT = 2 * MAX_QUEUED  # lines in one POST /api/speak; the queue keeps the newest MAX_QUEUED
MAX_TEXT = 300
VOICE_DIR = REPO_ROOT / "data" / "voices"
# The Piper voices (rhasspy/piper-voices on Hugging Face), both trained on the NST Swedish data of
# Språkbanken at the National Library of Norway: nst under CC0, alma under CC BY 4.0, which needs
# the credit below wherever the voice is used.
VOICES = {"nst": "sv_SE-nst-medium", "alma": "sv_SE-alma-medium"}
CREDIT = ("Uppläsning: Piper, rösterna nst (CC0) och alma (CC BY 4.0), tränade på NST:s svenska "
          "taldata från Språkbanken vid Nasjonalbiblioteket")
PLAY = ("pw-play",)
FALLBACK = ("spd-say", "--wait", "-l", "sv")
CANCEL = ("spd-say", "--cancel")


def piper_voices(folder: Path = VOICE_DIR) -> dict[str, Callable[[str, Path], None]]:
    """A synthesiser per voice whose model is in `folder`; none without Piper. Each writes a line to a WAV file."""
    try:
        from piper import PiperVoice
    except ImportError:
        return {}
    found: dict[str, Callable[[str, Path], None]] = {}
    for name, model in VOICES.items():
        path = folder / f"{model}.onnx"
        if not path.is_file():
            continue
        voice: Any = PiperVoice.load(path)

        def synthesise(text: str, target: Path, voice: Any = voice) -> None:
            with wave.open(str(target), "wb") as wav:
                voice.synthesize_wav(text, wav)

        found[name] = synthesise
    return found


class Speaker:
    def __init__(self, voices: Callable[[], dict[str, Callable[[str, Path], None]]] = piper_voices,
                 play: Sequence[str] = PLAY, fallback: Sequence[str] = FALLBACK, cancel: Sequence[str] = CANCEL) -> None:
        self.load_voices = voices
        self.voices: dict[str, Callable[[str, Path], None]] | None = None  # loaded on the first line
        self.play = list(play)
        self.fallback = list(fallback)
        self.cancel = list(cancel)
        self.queue: deque[tuple[str, str]] = deque(maxlen=MAX_QUEUED)
        self.condition = threading.Condition()
        self.current: subprocess.Popen[bytes] | None = None
        self.spoken: list[tuple[str, str]] = []  # (voice used, text), for the tests
        self.thread: threading.Thread | None = None

    def available(self) -> list[str]:
        """The Piper voices that can be used; loads them on the first call."""
        if self.voices is None:
            try:
                self.voices = self.load_voices()
            except Exception:  # noqa: BLE001 - a broken model must not stop the backend; espeak-ng reads instead
                self.voices = {}
        return sorted(self.voices)

    def say(self, lines: Sequence[tuple[str, str]]) -> None:
        """Queue lines as (text, voice); a voice that is not in VOICES reads with "alma"."""
        with self.condition:
            for text, voice in lines:
                text = " ".join(str(text).split())[:MAX_TEXT]
                if text:
                    self.queue.append((text, voice if voice in VOICES else "alma"))
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()
            self.condition.notify()

    def stop(self) -> None:
        with self.condition:
            self.queue.clear()
            current = self.current
        if current is not None and current.poll() is None:
            current.terminate()
        try:
            subprocess.run(self.cancel, check=False, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _command(self, text: str, voice: str, folder: Path) -> tuple[list[str], str]:
        """The command that says the line, and the voice it uses."""
        self.available()
        synthesise = (self.voices or {}).get(voice)
        if synthesise is not None:
            target = folder / "line.wav"
            try:
                synthesise(text, target)
                return [*self.play, str(target)], voice
            except Exception:  # noqa: BLE001 - fall back to espeak-ng rather than stay silent
                pass
        return [*self.fallback, text], "espeak-ng"

    def _run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="techseed-speech-") as scratch:
            while True:
                with self.condition:
                    while not self.queue:
                        self.condition.wait()
                    text, voice = self.queue.popleft()
                command, used = self._command(text, voice, Path(scratch))
                try:
                    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    continue  # nothing to play with: the log is still shown, only not read aloud
                with self.condition:
                    self.current = process
                    self.spoken.append((used, text))
                try:
                    process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    process.kill()
                with self.condition:
                    self.current = None
