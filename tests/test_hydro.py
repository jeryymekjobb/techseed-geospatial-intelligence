"""Tests for SMHI's flows and lake levels (tools/fetch_smhi_hydro.py, app/backend/hydro.py, hydro.js).
SYNTHETIC values in SMHI's CSV layout."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tools import fetch_smhi_hydro as fetch

HYDRO_JS = Path(__file__).resolve().parents[1] / "app" / "frontend" / "hydro.js"
FLOW_CSV = """﻿Stationsnamn;StationsId;Stationsnät;Stationens latitud;Stationens longitud
HEÅKRA;2128;SMHIs stationsnät;55.8449;13.6350

Parameternamn;Enhet
Vattenföring (15 min);m³/s

Datum Tid (UTC);Vattenföring (15 min);Kvalitet;;
2005-03-18 10:30:00;25.8;G;;;Tidsperiod (fr.o.m.) = 1973-05-23 11:30:00 (UTC)
2024-01-24 16:00:00;30.0;G;;;
2024-01-24 16:15:00;30.4;O;;;
2024-01-24 17:00:00;29.0;G;
"""
LEVEL_CSV = """Stationsnamn;StationsId;Stationsnät;Stationens latitud;Stationens longitud
RINGSJÖDAMMEN ÖVRE;2176;SMHIs stationsnät;55.9141;13.4409

Parameternamn;Enhet
Vattenstånd;cm

Datum (svensk sommartid);Vattenstånd;Kvalitet;;
2002-03-09;5478;G;;;Tidsperiod (fr.o.m.) = 1974-04-21
2024-02-10;5494;O;
"""


def test_flows_become_hourly_means_and_the_earlier_highest_is_kept() -> None:
    parsed = fetch.parse(FLOW_CSV)
    assert (parsed["name"], parsed["latitude"], parsed["longitude"]) == ("Heåkra", 55.8449, 13.635)
    result = fetch.series(parsed, 2, date(2024, 1, 20), date(2024, 2, 25))
    assert [(moment.isoformat(), value, quality) for moment, value, quality in result["rows"]] == [
        ("2024-01-24T16:00:00+00:00", 30.2, "O"), ("2024-01-24T17:00:00+00:00", 29.0, "G")]  # an unchecked quarter marks the hour
    assert result["earlier_max"] == {"value": 25.8, "time_utc": "2005-03-18T10:30:00Z"} and result["since"] == "2005-03-18"


def test_levels_are_by_the_day() -> None:
    result = fetch.series(fetch.parse(LEVEL_CSV), 3, date(2024, 1, 20), date(2024, 2, 25))
    assert [(moment.isoformat(), value) for moment, value, _ in result["rows"]] == [("2024-02-10T00:00:00+00:00", 5494.0)]
    assert result["earlier_max"]["value"] == 5478.0


def test_the_backend_lists_the_stations_with_their_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import hydro
    monkeypatch.setattr(hydro, "HYDRO_DIR", tmp_path)
    hydro.stations.cache_clear()
    assert hydro.stations() is None
    (tmp_path / "flow-2128.csv").write_text("time_utc,value,quality\n2024-01-24T16:00:00Z,30.2,G\n", encoding="utf-8")
    (tmp_path / "stations.json").write_text(json.dumps({"source": "SMHI", "stations": [{
        "id": "2128:2", "name": "Heåkra", "kind": "flow", "unit": "m³/s", "file": "flow-2128.csv", "latitude": 55.8, "longitude": 13.6,
        "measured_since": "1973-05-23", "earlier_max": {"value": 25.8, "time_utc": "2005-03-18T10:30:00Z"}}]}), encoding="utf-8")
    hydro.stations.cache_clear()
    station = hydro.stations()["stations"][0]
    assert station["observations"] == [{"time_utc": "2024-01-24T16:00:00Z", "value": 30.2}] and station["unchecked"] is False
    hydro.stations.cache_clear()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_show_the_value_up_to_the_clock_and_a_record() -> None:
    station = {"earlier_max": {"value": 25.8}, "observations": [
        {"time_utc": "2024-01-24T15:00:00Z", "value": 24.0}, {"time_utc": "2024-01-24T16:00:00Z", "value": 30.2},
        {"time_utc": "2024-01-24T17:00:00Z", "value": 29.0}]}
    code = (f"const m = require({json.dumps(str(HYDRO_JS))}); const s = {json.dumps(station)};"
            "const a = m.hydroAt(s.observations, Date.parse('2024-01-24T15:30:00Z'));"
            "const b = m.hydroAt(s.observations, Date.parse('2024-01-24T18:00:00Z'));"
            "console.log(JSON.stringify([a.latest.value, m.hydroRecord(s, a.highest), b.latest.value, b.highest.value, m.hydroRecord(s, b.highest),"
            " m.hydroText('flow', 30.2), m.hydroText('level', 5494), m.hydroText('level', null),"
            " m.hydroWhen('level', '2024-02-10T00:00:00Z', () => 'tid'), m.hydroWhen('flow', '2024-01-24T16:00:00Z', () => 'tid')]));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    # A level is a daily value: its date only, not 01:00 Swedish time.
    assert result == [24.0, False, 29.0, 30.2, True, "30,2 m³/s", "54,94 m", "–", "10 feb 2024", "tid"]
