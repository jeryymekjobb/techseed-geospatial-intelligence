"""Reading the satellite monitor's new log lines aloud through the computer's speakers.

The satellite monitor (monitor.js) chooses the lines and their voices and sends them to
POST /api/speak; this module speaks them one at a time in Swedish with Piper, a neural speech
synthesis that runs offline, with the voice "alma" (the monitor no longer uses "nst")
(VOICES, fetched to data/voices/ by tools/fetch_piper_voices.py). Each line is synthesised to a
WAV file and played with pw-play. Without Piper or a voice's model the line is read with
speech-dispatcher's Swedish espeak-ng voice instead (`spd-say -l sv`). The browser's own speech
synthesis is not used: Chrome on the exhibition PC lists no voices and then speaks English.

Before a line is synthesised, `spoken_form` writes it as it should be said, since the Swedish
rules of espeak-ng, which turn the text into sounds for both voices, read "47,1" as "fyrtisju punkt
ett", drop the dash of "2–6" and read "SMHI" as one syllable: a decimal comma becomes "komma", a
dash between two numbers "till", "1" before a common-gender word "en" ("en ort"), a hyphen in a
designation nothing ("Sentinel 2"), a day of the
month its ordinal ("fjortonde juli"), and an abbreviation in capitals is spelt letter by letter
("S M H I"), except those said as words (SAID_AS_WORDS). LEXICON gives words whose vowel length
espeak-ng gets wrong their sounds directly. The voices speak slightly slower than Piper's default
(LENGTH_SCALE), for the numbers.

At most MAX_QUEUED lines wait; older ones are dropped, so the voice never falls far behind the
scenario clock. Lines sent with `keep` - the scenario's summary at its start, while the clock
stands still - all wait, until lines without it come. `stop` empties the queue and cancels what
is being said.
"""

from __future__ import annotations

import re
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
CREDIT = ("Uppläsning: Piper, rösten alma (CC BY 4.0), tränad på NST:s svenska "
          "taldata från Språkbanken vid Nasjonalbiblioteket")
# Slower than Piper's 1.0, so the numbers come through.
LENGTH_SCALE = 1.12
# Abbreviations in capitals that are said as words; every other one is spelt letter by letter.
SAID_AS_WORDS = {"NASA", "FIRMS", "NOAA", "MODIS", "VIIRS", "SATCOM", "SYNC", "SENSOR", "FAILURE", "ERA"}
# Written forms that are spelt although not all in capitals.
SPELT = {"IoT": "I O T"}
MONTHS = ("januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
          "november", "december")
ORDINALS = ("första", "andra", "tredje", "fjärde", "femte", "sjätte", "sjunde", "åttonde", "nionde", "tionde",
            "elfte", "tolfte", "trettonde", "fjortonde", "femtonde", "sextonde", "sjuttonde", "artonde", "nittonde",
            "tjugonde", "tjugoförsta", "tjugoandra", "tjugotredje", "tjugofjärde", "tjugofemte", "tjugosjätte",
            "tjugosjunde", "tjugoåttonde", "tjugonionde", "trettionde", "trettioförsta")
# Words espeak-ng says with the wrong vowel length or stress, with their sounds (IPA, as Piper's
# Swedish voices use them). Add a word when it is heard wrong.
LEXICON = {
    "Sentinel": "sˈɛntɪnɛl",
    # A short a, stressed, as the long t forces: espeak-ng's "mˈeːɡavˌat" is heard as "wat".
    "megawatt": "mˌeːɡavˈatː",
    "watt": "vˈatː",
    # A short o, as in "bort", and an r of its own: espeak-ng's "ˈuːʈ" was hard to hear, and the
    # retroflex "ˈʊʈ" sounded like "oht" (the user chose this of two samples).
    "ort": "ˈʊrt",
    "orter": "ˈʊrtər",
}
# Words said "en" after the number 1, as they are common gender: espeak-ng says "ett ort".
COMMON_GENDER = {"ort", "detektion", "byggnad", "timme", "händelse", "nivågivare", "bräddgivare", "sensor", "millimeter"}
_MONTH = "|".join(MONTHS)


def spoken_form(text: str) -> str:
    """`text` as it should be said (see the module's text): numbers, dates and abbreviations."""
    ordinal = lambda day: ORDINALS[int(day) - 1] if 1 <= int(day) <= 31 else day  # noqa: E731
    text = re.sub(rf"\b(\d{{1,2}})–(\d{{1,2}}) ({_MONTH})\b",
                  lambda m: f"{ordinal(m[1])} till {ordinal(m[2])} {m[3]}", text)
    text = re.sub(rf"\b(\d{{1,2}}) ({_MONTH})\b", lambda m: f"{ordinal(m[1])} {m[2]}", text)
    text = re.sub(r"(\d),(\d)", r"\1 komma \2", text)
    text = re.sub(r"(?<![\d,])\b1 (\w+)", lambda m: f"en {m[1]}" if m[1] in COMMON_GENDER else m[0], text)
    text = re.sub(r"(?<=[\w])–(?=[\w])", " till ", text)
    # A hyphen in a designation is not said ("Sentinel-2", "NOAA-20", "ERA5-Land"); alone, "-2" is "minus två".
    text = re.sub(r"(?<=\w)-(?=\w)", " ", text)
    for written, said in SPELT.items():
        text = re.sub(rf"\b{written}\b", said, text)

    def spell(match: re.Match[str]) -> str:
        letters, digits = match[1], match[2]
        if letters in SAID_AS_WORDS:
            return match[0]
        return " ".join(letters) + (f" {digits}" if digits else "")

    return re.sub(r"\b([A-ZÅÄÖ]{2,})(\d*)\b", spell, text)


def lexicon_phonemes(voice: Any, text: str, lexicon: dict[str, str] = LEXICON) -> list[str]:
    """The text's sounds from Piper's phonemizer, with LEXICON's words put in as they are written there."""
    if not lexicon:
        return [phoneme for sentence in voice.phonemize(text) for phoneme in sentence]
    phonemes: list[str] = []
    for part in re.split(r"\b(" + "|".join(map(re.escape, lexicon)) + r")\b", text):
        if part in lexicon:
            phonemes.extend(lexicon[part])
        elif part.strip():
            sentences = voice.phonemize(part)
            if phonemes and part[:1].isspace():
                phonemes.append(" ")
            phonemes.extend(phoneme for sentence in sentences for phoneme in sentence)
            if part[-1:].isspace():
                phonemes.append(" ")
    return phonemes


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
            from piper.config import SynthesisConfig
            import numpy as np

            ids = voice.phonemes_to_ids(lexicon_phonemes(voice, text))
            audio = voice.phoneme_ids_to_audio(ids, SynthesisConfig(length_scale=LENGTH_SCALE))
            audio = audio[0] if isinstance(audio, tuple) else audio
            peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
            samples = (np.clip(audio / peak if peak > 1e-8 else audio, -1.0, 1.0) * 32767).astype("<i2")
            with wave.open(str(target), "wb") as wav:
                wav.setframerate(voice.config.sample_rate)
                wav.setsampwidth(2)
                wav.setnchannels(1)
                wav.writeframes(samples.tobytes())

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
        self.queue: deque[tuple[str, str]] = deque()
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

    def say(self, lines: Sequence[tuple[str, str]], keep: bool = False) -> None:
        """Queue lines as (text, voice); a voice that is not in VOICES reads with "alma". Without `keep`
        only the newest MAX_QUEUED lines wait."""
        with self.condition:
            for text, voice in lines:
                text = " ".join(str(text).split())[:MAX_TEXT]
                if text:
                    self.queue.append((text, voice if voice in VOICES else "alma"))
            while not keep and len(self.queue) > MAX_QUEUED:
                self.queue.popleft()
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
        text = spoken_form(text)
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
