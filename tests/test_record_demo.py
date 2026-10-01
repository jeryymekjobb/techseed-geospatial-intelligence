"""Tests for the pure parts of tools/record_demo.py and the kiosk options (no browser)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import record_demo

KIOSK = Path(__file__).resolve().parents[1] / "app" / "frontend" / "kiosk.js"


def test_kiosk_url_and_size() -> None:
    url = record_demo.kiosk_url("http://127.0.0.1:9000", "2014-08-04T06:00:00Z", 10800, "6")

    assert url == "http://127.0.0.1:9000/?autoplay=1&speed=10800&at=2014-08-04T06%3A00%3A00Z&horizon=6"
    assert record_demo.kiosk_url("http://x", None, 3600, None) == "http://x/?autoplay=1&speed=3600"
    assert record_demo.size("1920x1080") == (1920, 1080)


def test_ffmpeg_skips_the_loading_seconds() -> None:
    command = record_demo.ffmpeg_command("ffmpeg", Path("a.webm"), Path("a.mp4"), 8.456)

    assert command[command.index("-ss") + 1] == "8.46"
    assert command[-1] == "a.mp4"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_kiosk_options_are_parsed_and_validated() -> None:
    code = (
        f"const k = require({json.dumps(str(KIOSK))});"
        "console.log(JSON.stringify(["
        "k.parseKioskOptions('?at=2014-08-04T06:00:00Z&autoplay=1&speed=10800&horizon=6'),"
        "k.parseKioskOptions('?at=nonsense&speed=5&horizon=7&show=all'),"
        "[k.speedLabel(3600), k.speedLabel(10800), k.speedLabel(86400), k.speedLabel(1800)]]));"
    )
    valid, invalid, labels = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)

    assert valid == {"showAll": False, "at": "2014-08-04T06:00:00.000Z", "autoplay": True, "speed": 10800, "horizon": "6"}
    assert invalid == {"showAll": True, "at": None, "autoplay": False, "speed": None, "horizon": None}
    assert labels == ["1 timme/s", "3 timmar/s", "1 dygn/s", "30 minuter/s"]
