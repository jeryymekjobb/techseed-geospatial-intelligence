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


def test_a_moment_is_placed_on_the_timeline_only_inside_the_window() -> None:
    assert node(f"[timelineX({CLOCK}, {CLOCK}), timelineX({CLOCK + 2 * HOUR}, {CLOCK}), timelineX({CLOCK - 2 * HOUR}, {CLOCK}), timelineX({CLOCK + 6 * HOUR}, {CLOCK})]") == [
        pytest.approx(1 / 6), pytest.approx(0.5), None, None]


def test_the_track_splits_where_the_satellite_is_now() -> None:
    track = [{"latitude": lat, "longitude": 10.0} for lat in (-20.0, -10.0, 0.0, 10.0, 20.0)]
    split = node(f"splitTrack({json.dumps(track)}, {{latitude: 1.0, longitude: 10.0}})")
    assert [point["latitude"] for point in split["past"]] == [-20.0, -10.0, 0.0]
    assert [point["latitude"] for point in split["ahead"]] == [0.0, 10.0, 20.0]
    assert node("splitTrack([], {latitude: 0, longitude: 0})") == {"past": [], "ahead": []}


def test_the_sun_stands_overhead_where_the_almanac_puts_it() -> None:
    # The June solstice 2026, 12:00 UTC: about 23.4 N, and still about 0.4 E: with the equation of time at
    # -1.6 min the sun crosses Greenwich at 12:01:36 UTC.
    sun = node("subsolarPoint(Date.parse('2026-06-21T12:00:00Z'))")
    assert sun["latitude"] == pytest.approx(23.44, abs=0.1) and sun["longitude"] == pytest.approx(0.4, abs=0.2)
    # The September equinox 2026 (23 Sept): the sun over the equator.
    assert node("subsolarPoint(Date.parse('2026-09-23T00:00:00Z')).latitude") == pytest.approx(0.0, abs=0.5)


def test_night_and_day_in_sundsvall_in_august() -> None:
    elevation = "solarElevation(62.391, 17.307, Date.parse('{}'))"
    assert node(elevation.format("2026-08-16T00:00:00Z")) < -5   # two o'clock at night, Swedish summer time
    assert node(elevation.format("2026-08-16T10:30:00Z")) > 35   # half past twelve, near noon
    assert node("[nightShade(10), nightShade(-3), nightShade(-12)]") == [0, pytest.approx(0.375), 0.75]


def test_the_timeline_marks_the_hours_of_night_at_the_incident() -> None:
    # 16 August 2026 from 20:00 to 02:00 Swedish time: the sun sets at about 20:45 local.
    spans = node(f"nightSpans(62.391, 17.307, Date.parse('2026-08-16T19:00:00Z'))")
    assert len(spans) == 1 and spans[0][1] == 1
    assert spans[0][0] == pytest.approx((18 * 60 + 45 - 18 * 60) / 360, abs=0.03)  # 18:45 UTC in a window from 18:00
