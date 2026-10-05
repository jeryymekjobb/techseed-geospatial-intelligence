"""Tests for the satellite monitor's timeline and map (app/frontend/satmonitor.js), in Node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "satmonitor.js"
HOUR = 3600000
CLOCK = 1_407_150_000_000  # 2014-08-04T11:00:00Z

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")


def node(expression: str) -> object:
    code = f"const m = require({json.dumps(str(SCRIPT))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def test_the_map_is_equirectangular() -> None:
    assert node("[mapPoint(-180, 90, 400, 200), mapPoint(0, 0, 400, 200), mapPoint(16.2, 59.9, 400, 200)]") == [
        [0, 0], [200, 100], [pytest.approx(218.0, abs=0.01), pytest.approx(33.44, abs=0.01)]]


def test_the_timeline_shows_the_passes_in_the_window_and_marks_now() -> None:
    passes = [
        {"start": CLOCK - 3 * HOUR, "end": CLOCK - 3 * HOUR + 600000},        # before the window
        {"start": CLOCK - HOUR - 300000, "end": CLOCK - HOUR + 300000},       # cut at the start
        {"start": CLOCK + 2 * HOUR, "end": CLOCK + 2 * HOUR + 600000},        # inside
        {"start": CLOCK + 6 * HOUR, "end": CLOCK + 6 * HOUR + 600000},        # after the window
    ]
    row = node(f"timelineRow({json.dumps(passes)}, {CLOCK})")
    assert row["now"] == pytest.approx(1 / 6)
    assert [(round(block["from"], 4), round(block["to"], 4)) for block in row["blocks"]] == [
        (0.0, round(300000 / (6 * HOUR), 4)), (round(3 / 6, 4), round((3 * HOUR + 600000) / (6 * HOUR), 4))]
    assert row["overNow"] is False and row["next"] == CLOCK + 2 * HOUR


def test_a_pass_going_on_now_is_marked() -> None:
    passes = [{"start": CLOCK - 120000, "end": CLOCK + 240000}, {"start": CLOCK + HOUR, "end": CLOCK + HOUR + 1}]
    row = node(f"timelineRow({json.dumps(passes)}, {CLOCK})")
    assert row["overNow"] is True and row["next"] == CLOCK + HOUR


def test_the_axis_has_a_mark_every_hour() -> None:
    ticks = node(f"timelineTicks({CLOCK} + 1800000)")  # 11:30: marks at 11, 12, 13, 14, 15, 16
    assert [tick["at"] for tick in ticks] == [CLOCK + i * HOUR for i in range(6)]
    assert all(0 <= tick["x"] <= 1 for tick in ticks)
