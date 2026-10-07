"""Tests for the rain at the scenario clock (app/frontend/rain.js), in Node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "rain.js"
OBSERVATIONS = [  # hourly sums, stamped at the end of the hour; dry hours missing, as at the municipality's gauges
    {"time_utc": "2026-08-16T07:00:00Z", "precip_mm": 4.2},
    {"time_utc": "2026-08-16T08:00:00Z", "precip_mm": 10.6},
    {"time_utc": "2026-08-16T09:00:00Z", "precip_mm": None},
    {"time_utc": "2026-08-17T10:00:00Z", "precip_mm": 1.0},
]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")


def node(expression: str) -> object:
    code = f"const m = require({json.dumps(str(SCRIPT))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def sums(clock: str) -> dict:
    return node(f"rainSums({json.dumps(OBSERVATIONS)}, Date.parse({json.dumps(clock)}))")


def test_the_hour_and_the_day_up_to_the_clock() -> None:
    assert sums("2026-08-16T08:30:00Z") == {"hour": 10.6, "day": 14.8, "total": 14.8}
    assert sums("2026-08-16T09:00:00Z") == {"hour": 0, "day": 14.8, "total": 14.8}  # a missing value is dry
    assert sums("2026-08-17T10:00:00Z") == {"hour": 1.0, "day": 1.0, "total": 15.8}  # the 16th has left the day
    assert sums("2026-08-16T06:00:00Z") == {"hour": 0, "day": 0, "total": 0}


def test_one_value_per_playback_hour_for_the_chart() -> None:
    values = node(f"hourlyRain({json.dumps(OBSERVATIONS)}, Date.parse('2026-08-16T05:00:00Z'), Date.parse('2026-08-16T10:00:00Z'))")
    assert values == [0, 4.2, 10.6, 0, 0]


def test_the_markers_follow_smhi_s_classes_of_rain_by_the_hour() -> None:
    classes = node("[0, 0.3, 0.5, 0.6, 4, 4.1, 49.9, 50].map((mm) => rainClass(mm).key)")
    assert classes == ["none", "light", "light", "moderate", "moderate", "heavy", "heavy", "cloudburst"]
