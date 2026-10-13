"""Tests for SMHI's observed lightning (tools/fetch_smhi_lightning.py, app/backend/lightning.py)."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.backend import lightning, scenario
from tools import fetch_smhi_lightning as fetch

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"


def flash(minute: int, lat: float, lon: float, cloud: int = 0) -> dict:
    return {"year": 2018, "month": 7, "day": 14, "hours": 14, "minutes": minute, "seconds": 0, "lat": lat, "lon": lon,
            "peakCurrent": -21.4, "cloudIndicator": cloud}


def test_the_day_keeps_the_flashes_over_the_area_with_few_fields() -> None:
    kept = fetch.strikes([flash(5, 61.95, 15.4), flash(6, 40.0, 15.4), flash(7, 62.0, 15.5, cloud=1)], (0, 54, 35, 71))
    assert kept == [[1531577100, 61.95, 15.4, -21, 0], [1531577220, 62.0, 15.5, -21, 1]]  # the one in the Mediterranean is out
    assert fetch.DAY_URL.format(day=datetime(2018, 7, 14).date()).endswith("/year/2018/month/07/day/14/data.json")
    assert "CC BY 4.0" in fetch.LICENCE and "SMHI" in fetch.ATTRIBUTION


def test_the_screens_get_the_last_hour_s_flashes_and_the_log_the_hours_near_the_incident(monkeypatch: pytest.MonkeyPatch) -> None:
    lat0, lon0 = scenario.FIRE_CENTRE
    start = int(datetime(2018, 7, 14, 14, tzinfo=timezone.utc).timestamp())
    flashes = ((start + 60, lat0 + 0.05, lon0, -20), (start + 1800, lat0 + 2.0, lon0, 15), (start + 3700, lat0, lon0 + 0.1, -9))
    shown = lightning.at(datetime(2018, 7, 14, 15, 0, tzinfo=timezone.utc), flashes)
    assert [strike["age_min"] for strike in shown["strikes"]] == [59, 30] and shown["near"] == 1 and shown["near_km"] == 30.0
    assert lightning.events(flashes) == [{"at_utc": "2018-07-14T15:00:00Z", "count": 1}, {"at_utc": "2018-07-14T16:00:00Z", "count": 1}]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_log_says_how_many_struck_near_the_incident() -> None:
    events = [{"at_utc": "2018-07-14T15:00:00Z", "count": 29}]
    code = (f"const m = require({json.dumps(str(FRONTEND / 'satlog.js'))});"
            f"console.log(JSON.stringify(m.satelliteLog({{ lightningEvents: {json.dumps(events)} }}, Date.parse('2018-07-14T16:00:00Z'))))")
    lines = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert lines == [{"atMs": 1531580400000, "text": "29 blixtnedslag inom 30 kilometer från branden den senaste timmen",
                      "source": "lightning", "kind": "lightning"}]
