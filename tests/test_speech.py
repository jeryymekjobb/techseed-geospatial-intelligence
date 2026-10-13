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



def test_the_summary_s_lines_all_wait_until_ordinary_lines_come() -> None:
    speaker = speech.Speaker(fake_voices("nst", "alma"), PLAY, PLAY, CANCEL)
    speaker.say([(f"rad {n}", "nst") for n in range(1, 8)], keep=True)
    wait_for(lambda: len(speaker.spoken) == 7)
    assert [text for _, text in speaker.spoken] == [f"rad {n}" for n in range(1, 8)]
    speaker.say([("rad 8", "nst")])
    speaker.say([(f"rad {n}", "nst") for n in range(9, 16)], keep=True)
    speaker.say([("rad 16", "alma")])  # an ordinary line: again only the newest MAX_QUEUED wait
    wait_for(lambda: speaker.spoken[-1] == ("alma", "rad 16"))
    assert len(speaker.spoken) <= 8 + 1 + speech.MAX_QUEUED

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
    assert "alma (CC BY 4.0)" in speech.CREDIT and "nst (CC0)" not in speech.CREDIT  # only alma is heard


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
    for body in ({"lines": []}, {"lines": [line] * (speech.MAX_SENT + 1)}, {"lines": [{"text": "a", "voice": "espeak"}]},
                 {"lines": [{"text": 1, "voice": "nst"}]}, {"texts": ["a"]}):
        assert post(f"{url}/api/speak", body)[0] == 400
    assert post(f"{url}/api/speak", {"lines": [line], "keep": True}) == (200, {"queued": 1})
    assert post(f"{url}/api/speak/stop", {}) == (200, {"stopped": True})


def test_lines_are_written_as_they_should_be_said() -> None:
    said = speech.spoken_form
    assert said("starkast 47,1 megawatt, 54,57 meter") == "starkast 47 komma 1 megawatt, 54 komma 57 meter"
    assert said("3 orter hotas inom 2–6 timmar") == "3 orter hotas inom 2 till 6 timmar"
    assert said("Terra, 14–28 juli, den 4 juli 2018 och 31 januari") == \
        "Terra, fjortonde till tjugoåttonde juli, den fjärde juli 2018 och trettioförsta januari"
    assert said("Data från SMHI, MCF och VA-huvudmännen; NG5 och DV1–DV8; IoT avstängt") == \
        "Data från S M H I, M C F och V A huvudmännen; N G 5 och D V 1 till D V 8; I O T avstängt"
    # Said as words; a designation's hyphen is not said ("minus" alone); a dash with spaces is kept.
    assert said("NASA FIRMS och NOAA-20; SATCOM nere – satellitdata köas") == "NASA FIRMS och NOAA 20; SATCOM nere – satellitdata köas"
    assert said("Bilder från Sentinel-2 och ERA5-Land") == "Bilder från Sentinel 2 och ERA5 Land"


def test_the_lexicon_gives_its_words_their_sounds() -> None:
    class Voice:
        def phonemize(self, text: str) -> list[list[str]]:
            return [list(text.strip().upper())]

    assert "".join(speech.lexicon_phonemes(Voice(), "bild från Sentinel-2", {"Sentinel": "sɛn"})) == "BILD FRÅN sɛn-2"
    assert "".join(speech.lexicon_phonemes(Voice(), "ab", {})) == "AB"
    assert speech.LEXICON["Sentinel"] == "sˈɛntɪnɛl" and 1.0 < speech.LENGTH_SCALE < 1.2
    # "watt" with a short, stressed a (the user chose this of three samples).
    assert speech.LEXICON["megawatt"] == "mˌeːɡavˈatː" and speech.LEXICON["watt"] == "vˈatː"


@pytest.mark.skipif(not (speech.VOICE_DIR / f"{speech.VOICES['alma']}.onnx").is_file(), reason="needs the Piper voices (tools/fetch_piper_voices.py)")
def test_a_real_voice_says_a_line_with_the_lexicon_and_the_slower_pace(tmp_path: Path) -> None:
    voices = speech.piper_voices()
    target = tmp_path / "line.wav"
    voices["alma"](speech.spoken_form("Bilder från Sentinel-2, starkast 47,1 megawatt"), target)
    with wave.open(str(target)) as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() == 22050
        assert wav.getnframes() / wav.getframerate() > 2  # some seconds of speech
