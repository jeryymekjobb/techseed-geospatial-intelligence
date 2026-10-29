from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.backend import daily_rain, flood_assessment, level_sensors
from tools import fetch_smhi_daily

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
ARCHIVE = """﻿Stationsnamn;Stationsnummer;Stationsnät;Mäthöjd (meter över marken)
Kramfors;127560;SMHIs stationsnät;2.0

Parameternamn;Beskrivning;Enhet
Nederbördsmängd;summa 1 dygn, 1 gång/dygn, kl 06;millimeter

Tidsperiod (fr.o.m);Tidsperiod (t.o.m);Höjd (meter över havet);Latitud (decimalgrader);Longitud (decimalgrader)
1951-01-01 00:00:00;1993-02-28 23:59:59;87.0;62.9366;17.7304
1995-05-01 00:00:00;2026-09-30 23:59:59;45.601;62.9291;17.7615

Från Datum Tid (UTC);Till Datum Tid (UTC);Representativt dygn;Nederbördsmängd;Kvalitet;;Tidsutsnitt:
2025-09-05 06:00:01;2025-09-06 06:00:00;2025-09-05;2.0;G;;Kvalitetskontrollerade historiska data
2025-09-06 06:00:01;2025-09-07 06:00:00;2025-09-06;123.5;G
"""


def node(script: str, expression: str) -> object:
    code = f"const m = require({json.dumps(str(FRONTEND / script))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def test_smhi_s_daily_archive_gives_the_latest_place_and_each_day_from_06_to_06() -> None:
    parsed = fetch_smhi_daily.parse(ARCHIVE)
    assert (parsed["latitude"], parsed["longitude"]) == (62.9291, 17.7615)
    day = parsed["days"][-1]
    assert (day["from_utc"].isoformat(), day["to_utc"].isoformat(), day["mm"]) == (
        "2025-09-06T06:00:00+00:00", "2025-09-07T06:00:00+00:00", 123.5)


STATION = {"id": "127560", "name": "Kramfors", "latitude": 62.93, "longitude": 17.76,
           "days": [{"from_utc": "2025-09-05T06:00:00Z", "to_utc": "2025-09-06T06:00:00Z", "mm": 2.0},
                    {"from_utc": "2025-09-06T06:00:00Z", "to_utc": "2025-09-07T06:00:00Z", "mm": 123.5}]}


def test_a_day_counts_once_it_has_ended_and_the_assessment_names_it_a_daily_value() -> None:
    five_days = timedelta(days=5)
    assert daily_rain.sum_since(STATION, utc("2025-09-07T05:59:00Z"), five_days) == 2.0
    assert daily_rain.sum_since(STATION, utc("2025-09-07T06:00:00Z"), five_days) == 125.5
    hourly = [{"id": "128390", "name": "Lungö A", "latitude": 62.64, "longitude": 18.09,
               "observations": [{"time_utc": "2025-09-06T18:00:00Z", "precip_mm": 9.0}]}]
    assessor = flood_assessment.FloodAssessor(hourly, [], [], (62.93, 17.76), daily=[STATION])
    assert assessor._wettest_since(utc("2025-09-07T05:00:00Z"))[1]["name"] == "Lungö A"
    value, station = assessor._wettest_since(utc("2025-09-07T07:00:00Z"))
    assert (value, station["name"]) == (125.5, "Kramfors")
    assert assessor._rain_days_text(value, station) == (
        "125,5 mm regn de senaste 5 dygnen vid Kramfors (SMHI, dygnsvärden 06–06 UTC; regel ≥ 30,0 mm)")


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_maps_show_each_station_s_latest_ended_day() -> None:
    assert node("rain.js", f"dailyRainAt([{json.dumps(STATION)}], Date.parse('2025-09-06T05:00:00Z'))") == []
    shown = node("rain.js", f"dailyRainAt([{json.dumps(STATION)}], Date.parse('2025-09-07T07:00:00Z'))")
    assert [(item["name"], item["mm"]) for item in shown] == [("Kramfors", 123.5)]
    assert node("rain.js", "dailyRainText(123.5)") == "123,5 mm"


def test_a_level_sensor_can_alarm_on_a_rise_over_the_flow_at_the_start(tmp_path: Path) -> None:
    points = tmp_path / "points.geojson"
    points.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [17.77, 63.38]},
         "properties": {"id": "ng-01", "name": "NG1 Stambanan Stugusjön", "station": "2604:2"}}]}), encoding="utf-8")
    station = {"id": "2604:2", "name": "Stugusjön", "kind": "flow", "latitude": 63.38, "longitude": 17.77,
               "earlier_max": {"value": 24.7, "time_utc": "2013-09-21T05:15:00Z"},
               "observations": [{"time_utc": "2025-09-06T12:00:00Z", "value": 1.0},
                                {"time_utc": "2025-09-07T05:00:00Z", "value": 5.2},
                                {"time_utc": "2025-09-07T20:00:00Z", "value": 24.7}]}
    start = datetime(2025, 9, 6, 12, tzinfo=timezone.utc)
    sensors = level_sensors.LevelSensors(points, [station], rise=5.0, start=start)
    assert sensors.at(utc("2025-09-07T04:00:00Z"))["confirms"] == 0
    item = sensors.at(utc("2025-09-07T05:00:00Z"))["sensors"][0]
    assert (item["confirms"], item["rise"], item["rise_rule"]) == (True, 5.2, 5.0)
    assert flood_assessment.level_text(item) == "larmar, Stugusjön 5,2 gånger flödet vid start (regel ≥ 5,0)"
    # Without a rise the record holds: 24.7 is not above 24.7.
    assert level_sensors.LevelSensors(points, [station]).at(utc("2025-09-07T20:00:00Z"))["confirms"] == 0


class StubOverflow:
    """Stands in for flood_sensors.FloodSensors: one overflow sensor that confirms, and any placed sensor."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def at(self, clock, failed=(), placed=()):
        self.calls.append((clock, tuple(failed), tuple(placed)))
        sensors = [{"id": "dv-01", "kind": "sewer", "status": "ok", "confirms": True},
                   *({"id": item["id"], "kind": "sewer", "status": "ok", "confirms": False, "placed": True} for item in placed)]
        return {"label": "bräddgivare", "sensors": sensors, "confirms": 1, "operating": len(sensors)}


def test_overflow_and_level_sensors_together_are_one_set(tmp_path: Path) -> None:
    # Ljungan 2023 keeps sundsvall2026's overflow sensors beside its level sensors (OVERFLOW_WITH_LEVEL_SENSORS).
    points = tmp_path / "points.geojson"
    points.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [17.059, 62.327]},
         "properties": {"id": "ng-01", "name": "NG1 Öhns camping, Matfors", "station": "1650:2"}}]}), encoding="utf-8")
    station = {"id": "1650:2", "name": "Skallböle", "kind": "flow", "latitude": 62.36, "longitude": 16.96,
               "earlier_max": {"value": 1050.0, "time_utc": "2000-07-22T00:00:00Z"},
               "observations": [{"time_utc": "2023-08-05T00:00:00Z", "value": 204.8}, {"time_utc": "2023-08-11T20:00:00Z", "value": 410.0}]}
    level = level_sensors.LevelSensors(points, [station], rise=2.0, start=utc("2023-08-05T00:00:00Z"))
    overflow = StubOverflow()
    both = level_sensors.BothSensors(overflow, level)
    placed = [{"id": "placed-1", "name": "Placerad", "latitude": 62.39, "longitude": 17.3}]
    result = both.at(utc("2023-08-12T00:00:00Z"), ["dv-02"], placed)
    assert [item["id"] for item in result["sensors"]] == ["dv-01", "placed-1", "ng-01"]
    assert (result["confirms"], result["operating"], result["label"]) == (2, 3, level_sensors.BOTH_LABEL)
    # The failures reach both kinds; a placed sensor goes among the overflow sensors, which follow rain.
    assert overflow.calls == [(utc("2023-08-12T00:00:00Z"), ("dv-02",), tuple(placed))]
    assert both.at(utc("2023-08-12T00:00:00Z"), ["ng-01"])["sensors"][-1]["status"] == "failed"


def test_without_a_level_station_the_river_flood_s_classification_counts_the_level_sensors() -> None:
    flow = {"id": "2604:2", "name": "Stugusjön", "kind": "flow", "latitude": 63.38, "longitude": 17.77,
            "earlier_max": {"value": 24.7, "time_utc": "2013-09-21T05:15:00Z"},
            "observations": [{"time_utc": "2025-09-07T05:00:00Z", "value": 5.2}]}
    gauge = {"id": "128390", "name": "Lungö A", "latitude": 62.64, "longitude": 18.09,
             "observations": [{"time_utc": "2025-09-07T04:00:00Z", "precip_mm": 33.0}]}
    assessor = flood_assessment.FloodAssessor([gauge], [], [], (62.93, 17.76), hydro=[flow])
    sensor = {"kind": "level", "status": "ok", "confirms": True, "latitude": 63.38, "longitude": 17.77}
    result = assessor.classify({"pass_utc": "2025-09-07T05:21:30Z", "centre": None}, {"sensors": [sensor, {**sensor, "confirms": False}]})
    assert [rule["text"] for rule in result["rules"]][2] == "1 av 2 nivågivare larmar (syntetiska)"
    assert (result["outcome"], len(result["rules"]), result["counts"]["Översvämning"]) == ("Översvämning trolig", 4, 2)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_rain_chart_can_show_a_daily_station_by_its_ended_days() -> None:
    # SYNTHETIC days round Skultuna's 59.7 mm on 1 September 2023 (06-06 UTC to 2 September).
    days = [{"from_utc": "2023-08-30T06:00:00Z", "to_utc": "2023-08-31T06:00:00Z", "mm": 2.1},
            {"from_utc": "2023-08-31T06:00:00Z", "to_utc": "2023-09-01T06:00:00Z", "mm": 4.0},
            {"from_utc": "2023-09-01T06:00:00Z", "to_utc": "2023-09-02T06:00:00Z", "mm": 59.7}]
    sums = lambda clock: node("rain.js", f"dailyRainSums({json.dumps(days)}, Date.parse('{clock}'), Date.parse('2023-08-30T00:00:00Z'))")  # noqa: E731
    assert sums("2023-08-31T05:00:00Z") == {"day": None, "total": 0}
    assert sums("2023-09-02T06:00:00Z") == {"day": 59.7, "total": 65.8}
    bars = node("rain.js", f"dailyRainBars({json.dumps(days)}, Date.parse('2023-08-31T00:00:00Z'), Date.parse('2023-09-01T12:00:00Z'))")
    assert [bar["mm"] for bar in bars] == [2.1, 4.0, 59.7]


def test_mission_control_offers_the_daily_stations_as_rain_gauges(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import server
    monkeypatch.setattr(server, "weather", lambda: {"stations": [{"id": "96190", "name": "Eskilstuna A", "distance_km": 25.7}]})
    monkeypatch.setattr(server.daily_rain, "stations", lambda: [{"id": "96350", "name": "Västerås", "days": [{}]}])
    monkeypatch.setattr(server.scenario, "WILDFIRE", False)
    monkeypatch.setattr(server.scenario, "RAIN_CHART_STATION", "daily-96350")
    monkeypatch.setattr(server.hydro, "stations", lambda: None)
    choice = server.panel_choices()["rain_station"]
    assert choice["options"] == [["96190", "Eskilstuna A (25.7 km)"], ["daily-96350", "Västerås (per dygn)"]]
    assert choice["default"] == "daily-96350"
