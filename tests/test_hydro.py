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


DAILY_FLOW_CSV = """Stationsnamn;StationsId;Stationsnät;Stationens latitud;Stationens longitud
LÄNNÄSSJÖN;20035;SMHIs stationsnät;62.6289;14.1294

Parameternamn;Enhet
Vattenföring (Dygn);m³/s

Datum (svensk sommartid);Vattenföring (Dygn);Kvalitet;;
1995-06-01;180.0;G;;;Tidsperiod (fr.o.m.) = 1973-01-01
2023-08-09;208.0;O;
2023-08-10;205.0;O;
"""


def test_daily_flows_stay_by_the_day() -> None:
    # Where SMHI has no flow every 15 minutes for the period, the day's flow (parameter 1) at 00 UTC.
    assert fetch.KINDS[1] == ("flow", "m³/s")
    result = fetch.series(fetch.parse(DAILY_FLOW_CSV), 1, date(2023, 8, 1), date(2023, 8, 21))
    assert [(moment.isoformat(), value) for moment, value, _ in result["rows"]] == [
        ("2023-08-09T00:00:00+00:00", 208.0), ("2023-08-10T00:00:00+00:00", 205.0)]
    assert result["earlier_max"]["value"] == 180.0


def test_a_15_minute_series_takes_its_record_from_the_longer_daily_series() -> None:
    # Skallböle: 15-minute flows from 2006 (highest 407 m³/s), daily flows from 1956 (1050 m³/s in 2000).
    result = {"rows": [], "earlier_max": {"value": 407.0, "time_utc": "2006-10-29T14:45:00Z"}, "since": "2006-01-01"}
    daily = fetch.parse(DAILY_FLOW_CSV.replace("1995-06-01;180.0", "2000-07-22;1050.0"))
    merged = fetch.with_daily_record(result, daily, date(2023, 8, 1))
    assert merged["earlier_max"] == {"value": 1050.0, "time_utc": "2000-07-22T00:00:00Z"} and merged["since"] == "2000-07-22"
    # A lower daily record leaves the 15-minute one.
    assert fetch.with_daily_record(result, fetch.parse(DAILY_FLOW_CSV), date(2023, 8, 1))["earlier_max"]["value"] == 407.0


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


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_a_record_is_named_only_for_the_hold_days_after_it() -> None:
    # SYNTHETIC daily levels: a record above the earlier highest in January 2017, a lower peak in 2023.
    station = {"earlier_max": {"value": 146.1}, "record_hold_days": 30, "observations": [
        {"time_utc": "2017-01-04T00:00:00Z", "value": 168.6}, {"time_utc": "2023-10-21T00:00:00Z", "value": 149.5}]}
    code = (f"const m = require({json.dumps(str(HYDRO_JS))}); const s = {json.dumps(station)};"
            "const at = (t) => m.hydroRecord(s, m.hydroAt(s.observations, Date.parse(t)).highest, Date.parse(t));"
            "const forever = {...s, record_hold_days: null};"
            "const later = Date.parse('2023-10-21T12:00:00Z'), highest = m.hydroAt(s.observations, later).highest;"
            "console.log(JSON.stringify([at('2017-01-04T12:00:00Z'), at('2017-02-03T00:00:00Z'), at('2017-02-04T00:00:01Z'),"
            " at('2023-10-21T12:00:00Z'), m.hydroRecord(forever, highest, later), m.hydroRecord(s, highest)]));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    # Without the clock (the panel's note under the period's highest) the hold does not apply.
    assert result == [True, True, False, False, True, True]


def write_sea_level(folder: Path) -> None:
    """SYNTHETIC hourly sea levels at a Skanör-like station, in fetch_smhi_sea_level's layout."""
    rows = [("2017-01-04T16:00:00Z", 163.2, "G"), ("2017-01-04T17:00:00Z", 168.6, "G"), ("2017-01-05T03:00:00Z", 101.0, "G"),
            ("2019-01-02T08:00:00Z", 124.1, "G"), ("2023-10-20T23:00:00Z", 146.5, "G"), ("2023-10-21T00:00:00Z", 149.5, "O")]
    (folder / "sea-level-30488.csv").write_text("time_utc,value,quality\n" + "".join(f"{t},{v},{q}\n" for t, v, q in rows), encoding="utf-8")
    (folder / "SOURCE.json").write_text(json.dumps({"source": "SMHI havsvattenstånd", "stations": [{
        "station": "30488", "name": "Skanör", "unit": "cm", "height_system": "RH2000", "file": "sea-level-30488.csv",
        "latitude": 55.4168, "longitude": 12.8296, "measured_since": "1992-02-17",
        "earlier_max": {"value": 146.1, "time_utc": "1997-04-11T16:00:00Z"}}]}), encoding="utf-8")


def test_the_sea_level_is_a_level_station_with_each_day_s_highest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import hydro
    monkeypatch.setattr(hydro, "HYDRO_DIR", None)
    monkeypatch.setattr(hydro, "SEA_LEVEL_DIR", tmp_path)
    monkeypatch.setattr(hydro.scenario, "SEA_LEVEL_STATIONS", {"30488": "Skanör"})
    monkeypatch.setattr(hydro.scenario, "HYDRO_RECORD_HOLD_DAYS", 30)
    write_sea_level(tmp_path)
    hydro.stations.cache_clear(), hydro.sea_levels.cache_clear()
    [station] = hydro.stations()["stations"]
    assert (station["id"], station["name"], station["kind"], station["sea"], station["unchecked"]) == ("sea-30488", "Skanör (havet)", "level", True, True)
    assert station["record_hold_days"] == 30
    assert station["observations"][:2] == [{"time_utc": "2017-01-04T00:00:00Z", "value": 168.6}, {"time_utc": "2017-01-05T00:00:00Z", "value": 101.0}]
    hydro.stations.cache_clear(), hydro.sea_levels.cache_clear()


def test_a_short_scenario_shows_the_sea_level_by_the_hour_with_hours_ahead(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import hydro
    monkeypatch.setattr(hydro, "HYDRO_DIR", None)
    monkeypatch.setattr(hydro, "MODEL_FLOW_DIR", None)
    monkeypatch.setattr(hydro, "SEA_LEVEL_DIR", tmp_path)
    monkeypatch.setattr(hydro.scenario, "SEA_LEVEL_STATIONS", {"30488": "Skanör"})
    monkeypatch.setattr(hydro.scenario, "SEA_LEVEL_HOURLY", True)
    monkeypatch.setattr(hydro.scenario, "SEA_LEVEL_AHEAD_HOURS", 72)
    write_sea_level(tmp_path)
    hydro.stations.cache_clear(), hydro.sea_levels.cache_clear()
    [station] = hydro.stations()["stations"]
    hydro.stations.cache_clear(), hydro.sea_levels.cache_clear()
    assert (station["daily"], station["ahead_hours"]) == (False, 72)
    assert station["observations"][:2] == [{"time_utc": "2017-01-04T16:00:00Z", "value": 163.2}, {"time_utc": "2017-01-04T17:00:00Z", "value": 168.6}]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_find_the_highest_sea_level_in_the_hours_ahead() -> None:
    # SYNTHETIC hourly sea levels round Spikarna's 76.7 cm of 8 August 2023.
    observations = [{"time_utc": "2023-08-07T12:00:00Z", "value": 40.3}, {"time_utc": "2023-08-08T15:00:00Z", "value": 76.7},
                    {"time_utc": "2023-08-10T13:00:00Z", "value": 54.2}, {"time_utc": "2023-08-12T00:00:00Z", "value": 90.0}]
    code = (f"const m = require({json.dumps(str(HYDRO_JS))}); const o = {json.dumps(observations)};"
            "const at = (t, h) => m.hydroAhead(o, Date.parse(t), h);"
            "console.log(JSON.stringify([at('2023-08-07T12:00:00Z', 72).value, at('2023-08-08T15:00:00Z', 72).value,"
            " at('2023-08-12T00:00:00Z', 72), m.hydroWhen('level', '2023-08-08T15:00:00Z', () => 'tid', false),"
            " m.hydroWhen('level', '2023-08-08T00:00:00Z', () => 'tid')]));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    # The clock's own hour is not ahead; 90 cm lies more than 72 hours after the second clock.
    assert result == [76.7, 54.2, None, "tid", "8 aug 2023"]


def test_storms_are_the_peaks_three_days_apart_with_the_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import hydro
    monkeypatch.setattr(hydro, "SEA_LEVEL_DIR", tmp_path)
    monkeypatch.setattr(hydro.scenario, "SEA_LEVEL_STATIONS", {"30488": "Skanör"})
    monkeypatch.setattr(hydro.scenario, "SEA_LEVEL_STORM_CM", 100.0)
    write_sea_level(tmp_path)
    hydro.storms.cache_clear()
    storms = hydro.storms()
    # 2017-01-05 03:00 is within three days of Axel's peak; Babet's two hours are one storm.
    assert [(s["time_utc"], s["value_cm"], s["record"]) for s in storms] == [
        ("2017-01-04T17:00:00Z", 168.6, True), ("2019-01-02T08:00:00Z", 124.1, False), ("2023-10-21T00:00:00Z", 149.5, False)]
    assert storms[0]["station"] == "Skanör" and storms[0]["height_system"] == "RH2000"
    hydro.storms.cache_clear()


def test_a_renumbered_station_takes_its_record_from_its_earlier_numbers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Åkesta kvarn: 2773 from August 2023, earlier 2771 (2021-2023) and 2216 (1980-2021, 42.9 m³/s in 1983).
    flows = FLOW_CSV.replace("2005-03-18 10:30:00;25.8", "2023-08-29 15:15:00;23.9")
    old = DAILY_FLOW_CSV.replace("1995-06-01;180.0", "1983-04-20;42.9")
    pages = {fetch.archive_url("2773", 2): flows, fetch.archive_url("2773", 1): DAILY_FLOW_CSV.replace("1995-06-01;180.0", "2023-08-30;24.0"),
             fetch.archive_url("2771", 1): DAILY_FLOW_CSV.replace("1995-06-01;180.0", "2022-04-01;30.1"), fetch.archive_url("2216", 1): old}
    monkeypatch.setattr(fetch, "download", pages.__getitem__)
    monkeypatch.setattr(fetch.scenario, "HYDRO_STATIONS", {"2773:2": "Åkesta kvarn"})
    monkeypatch.setattr(fetch.scenario, "HYDRO_EARLIER_STATIONS", {"2773:2": ("2771", "2216")})
    assert fetch.main(["--start", "2023-08-01", "--end", "2024-02-25", "--out", str(tmp_path)]) == 0
    station = json.loads((tmp_path / "stations.json").read_text(encoding="utf-8"))["stations"][0]
    assert station["earlier_max"] == {"value": 42.9, "time_utc": "1983-04-20T00:00:00Z"}
    assert station["measured_since"] == "1983-04-20" and station["earlier_stations"] == ["2771", "2216"]
