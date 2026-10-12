"""Tests for reading the log aloud (app/backend/speech.py and POST /api/speak), with stand-ins for
Piper, pw-play and spd-say, so nothing is played."""

from __future__ import annotations

import json
import sys
import threading
import time
import wave
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app.backend import lantmateriet, server, speech
from app.backend.scenario_engine import ScenarioEngine
from tools import fetch_piper_voices

# Takes a moment, like speaking; the WAV file or the text is its last argument.
PLAY = [sys.executable, "-c", "import time; time.sleep(0.2)"]
CANCEL = [sys.executable, "-c", "pass"]


def wait_for(condition, seconds: float = 10.0) -> None:
    deadline = time.time() + seconds
    while not condition():
        assert time.time() < deadline, "timed out"
        time.sleep(0.02)


def fake_voices(*names: str):
    """Synthesisers that write a short silent WAV, like Piper's."""
    def synthesise(text: str, target: Path) -> None:
        with wave.open(str(target), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b"\0\0" * 100)
    return lambda: {name: synthesise for name in names}


def test_satellite_lines_take_nst_and_the_others_alma_one_at_a_time() -> None:
    assert speech.VOICES == {"nst": "sv_SE-nst-medium", "alma": "sv_SE-alma-medium"}
    speaker = speech.Speaker(fake_voices("nst", "alma"), PLAY, PLAY, CANCEL)
    speaker.say([("Sentinel-1C (SAR) över Sundsvall", "nst"), ("Bräddgivare DV1 Bergsåker bräddar", "alma"), ("  ok  ", "okänd")])
    wait_for(lambda: len(speaker.spoken) == 3)
    assert speaker.spoken == [("nst", "Sentinel-1C (SAR) över Sundsvall"), ("alma", "Bräddgivare DV1 Bergsåker bräddar"), ("alma", "ok")]


def test_old_lines_are_dropped_and_stop_silences() -> None:
    speaker = speech.Speaker(fake_voices("nst", "alma"), PLAY, PLAY, CANCEL)
    speaker.say([("rad 1", "alma")])
    wait_for(lambda: speaker.spoken == [("alma", "rad 1")])
    speaker.say([(f"rad {n}", "alma") for n in range(2, 9)])  # while rad 1 is spoken
    wait_for(lambda: len(speaker.spoken) == 1 + speech.MAX_QUEUED)
    assert [text for _, text in speaker.spoken] == ["rad 1", "rad 5", "rad 6", "rad 7", "rad 8"]
    speaker.say([("rad 9", "alma"), ("rad 10", "alma")])
    wait_for(lambda: len(speaker.spoken) == 6)
    speaker.stop()
    time.sleep(0.5)
    assert [text for _, text in speaker.spoken][-1] == "rad 9" and not speaker.queue


def test_without_a_piper_voice_espeak_ng_reads_and_without_anything_the_log_stays_silent() -> None:
    speaker = speech.Speaker(fake_voices("nst"), PLAY, PLAY, CANCEL)
    speaker.say([("Bräddgivare DV1 Bergsåker bräddar", "alma")])
    wait_for(lambda: speaker.spoken == [("espeak-ng", "Bräddgivare DV1 Bergsåker bräddar")])
    assert speech.FALLBACK == ("spd-say", "--wait", "-l", "sv")
    broken = speech.Speaker(lambda: 1 / 0, PLAY, PLAY, CANCEL)  # a model that cannot be loaded
    assert broken.available() == []
    silent = speech.Speaker(lambda: {}, ["no-such-player"], ["no-such-spd-say"], ["no-such-spd-say"])
    silent.say([("rad 1", "nst")])
    silent.stop()
    time.sleep(0.2)
    assert silent.spoken == []


def test_the_installed_voices_are_the_pinned_ones() -> None:
    assert set(fetch_piper_voices.SHA256) == {f"{model}{suffix}" for model in speech.VOICES.values() for suffix in (".onnx", ".onnx.json")}
    assert fetch_piper_voices.url("alma", "MODEL_CARD").endswith("/sv/sv_SE/alma/medium/MODEL_CARD")
    assert "alma (CC BY 4.0)" in speech.CREDIT and "nst (CC0)" in speech.CREDIT


@pytest.fixture()
def base_url():
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None),
        "engine": ScenarioEngine(datetime(2014, 7, 31, tzinfo=timezone.utc), datetime(2014, 8, 15, tzinfo=timezone.utc)),
        "control_token": "secret",  # the monitor speaks without the control token
        "speaker": speech.Speaker(fake_voices("nst", "alma"), PLAY, PLAY, CANCEL),
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", handler.speaker
    httpd.shutdown()
    httpd.server_close()


def post(url: str, body: object) -> tuple[int, dict]:
    request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def test_the_monitor_sends_its_lines_and_voices_to_the_backend(base_url) -> None:
    url, speaker = base_url
    line = {"text": "Bräddgivare DV1 Bergsåker bräddar", "voice": "alma"}
    assert post(f"{url}/api/speak", {"lines": [line]}) == (200, {"queued": 1})
    wait_for(lambda: speaker.spoken == [("alma", "Bräddgivare DV1 Bergsåker bräddar")])
    for body in ({"lines": []}, {"lines": [line] * (speech.MAX_QUEUED + 1)}, {"lines": [{"text": "a", "voice": "espeak"}]},
                 {"lines": [{"text": 1, "voice": "nst"}]}, {"texts": ["a"]}):
        assert post(f"{url}/api/speak", body)[0] == 400
    assert post(f"{url}/api/speak/stop", {}) == (200, {"stopped": True})
