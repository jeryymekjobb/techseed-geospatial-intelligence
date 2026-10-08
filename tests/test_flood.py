"""Tests for the flood's synthetic overflow sensors, assessment and detection sequence
(app/backend/flood_sensors.py, flood_assessment.py) with SYNTHETIC rain, and their texts."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.backend import flood_assessment as fa
from app.backend import flood_sensors as fsen

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
START = datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 8, 17, 0, 0, tzinfo=timezone.utc)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def point(fid: int, area: str, depth: float | None, lat: float = 62.39, lon: float = 17.30) -> dict:
    return {"geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"fid": fid, "omrade": area, "objekttyp": "Trumma", "model_depth_100y_m": depth}}


STATION = {"name": "Mätaren", "latitude": 62.39, "longitude": 17.31, "observations": [  # synthetic, dry hours missing
    {"time_utc": "2026-08-16T07:00:00Z", "precip_mm": 4.0},
    {"time_utc": "2026-08-16T08:00:00Z", "precip_mm": 10.0},
    {"time_utc": "2026-08-16T09:00:00Z", "precip_mm": 2.0},
]}


def sensors(tmp_path: Path, features: list[dict]) -> fsen.FloodSensors:
    path = tmp_path / "points.geojson"
    path.write_text(json.dumps({"features": features}), encoding="utf-8")
    return fsen.FloodSensors(path, [STATION], START, END)


def test_the_deepest_modelled_points_are_chosen_one_per_area_first() -> None:
    chosen = fsen.choose_points([point(1, "A", 0.9), point(2, "A", 0.8), point(3, "B", 0.2), point(4, "C", 0.05), point(5, "D", None)], 3)
    assert [item["properties"]["fid"] for item in chosen] == [1, 3, 2]  # C is too shallow, D outside the model


def test_the_reservoir_fills_with_rain_drains_and_overflows_when_full() -> None:
    states = fsen.reservoir([0, 10, 10, 0, 0, 0], 2.0)  # inflow 20 mm/h, drain 6
    assert [round(storage, 1) for storage, _ in states] == [0, 14, 15, 9, 3, 0]
    assert [flowing for _, flowing in states] == [False, False, True, False, False, False]


def test_the_sensors_are_shaped_like_diwise_sewers_with_overflow_times(tmp_path: Path) -> None:
    flood = sensors(tmp_path, [point(1, "Haga", 0.75)])  # inflow factor 4
    before, peak, after = (flood.at(at(moment)) for moment in ("2026-08-16T07:30:00Z", "2026-08-16T08:30:00Z", "2026-08-16T12:00:00Z"))
    assert before["sensors"][0]["percent"] == 67 and before["sensors"][0]["overflow"] == "stopped"  # 16 - 6 = 10 of 15 mm
    sewer = peak["sensors"][0]
    assert (sewer["id"], sewer["name"], sewer["kind"], sewer["overflow"], sewer["percent"]) == ("dv-01", "DV1 Haga", "sewer", "started", 100)
    assert sewer["overflow_observed_at"] == "2026-08-16T07:00:00Z" and sewer["overflow_ended_at"] is None and peak["confirms"] == 1
    assert sewer["level_m"] == 2.0 and sewer["gauge"] == "Mätaren"
    ended = after["sensors"][0]
    # The hour to 09:00 still overflows: 15 + 2 x 4 - 6 = 17 mm.
    assert ended["overflow"] == "stopped" and ended["overflow_ended_at"] == "2026-08-16T09:00:00Z" and ended["overflow_cumulative_h"] == 2
    failed = flood.at(at("2026-08-16T08:30:00Z"), failed=["dv-01"])
    assert failed["sensors"][0]["status"] == "failed" and failed["operating"] == 0


def test_the_assessment_weighs_rain_and_overflow_and_keeps_the_model_and_images_as_context(tmp_path: Path) -> None:
    flood = sensors(tmp_path, [point(1, "Haga", 0.75)])
    acquisitions = [{"time_utc": "2026-08-16T05:21:32Z", "satellite": "Sentinel-1C", "norad": "62261"}]
    assessor = fa.FloodAssessor([STATION], acquisitions, [], (62.39, 17.31))
    peak = assessor.at(at("2026-08-16T08:30:00Z"), flood.at(at("2026-08-16T08:30:00Z")))
    keys = {item["key"]: item for item in peak["evidence"]}
    assert keys["rain_hour"]["status"] == "ok" and keys["rain_day"]["status"] == "miss"  # 10 mm in the hour, 14 in the day
    assert keys["iot:dv-01"]["status"] == "ok" and keys["model:dv-01"]["weight"] == 0.0
    assert "inte hämtad" in keys["radar"]["text"] and keys["image"]["text"] == "Ingen klar optisk satellitbild under regnet"
    assert (peak["outcome"], peak["score_pct"]) == ("Possible flood", 48)  # 1 - 0.70 x 0.75
    outage = assessor.at(at("2026-08-16T08:30:00Z"), flood.at(at("2026-08-16T08:30:00Z")), at("2026-08-16T05:00:00Z"))
    assert outage["evidence"][0]["key"] == "satcom" and "radar" not in {item["key"] for item in outage["evidence"]}


def test_the_detection_sequence_starts_from_the_next_real_acquisition_and_says_the_image_is_not_analysed(tmp_path: Path) -> None:
    acquisitions = [{"time_utc": "2026-08-16T05:21:32Z", "satellite": "Sentinel-1C", "norad": "62261"},
                    {"time_utc": "2026-08-16T16:37:32Z", "satellite": "Sentinel-1C", "norad": "62261"}]
    assessor = fa.FloodAssessor([STATION], acquisitions, [], (62.39, 17.31))
    summary = assessor.next_pass(at("2026-08-16T06:00:00Z"))
    assert (summary["pass_utc"], summary["norad"], summary["kind"]) == ("2026-08-16T16:37:32Z", "62261", "flood")
    assert assessor.next_pass(at("2026-08-17T00:00:00Z")) is None
    flood = sensors(tmp_path, [point(1, "Haga", 0.75)])
    result = assessor.classify(assessor.pass_at("2026-08-16T05:21:32Z"), flood.at(at("2026-08-16T08:30:00Z")))
    assert [rule["holds"] for rule in result["rules"]] == [False, True, True, False]
    assert result["outcome"] == "Översvämning trolig" and result["counts"] == {"Översvämning": 2}


def node(script: str, expression: str) -> object:
    code = f"const m = require({json.dumps(str(FRONTEND / script))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_name_the_sewer_values_and_the_flood_s_steps() -> None:
    sewer = {"kind": "sewer", "name": "DV1 Haga", "status": "ok", "level_m": 2.0, "percent": 100, "overflow": "started",
             "overflow_observed_at": "2026-08-16T07:00:00Z", "overflow_cumulative_h": 2, "model_depth_m": 0.736, "placed": False}
    assert node("sensors.js", f"syntheticSensorText({json.dumps(sewer)})") == (
        "DV1 Haga: nivå 2 m, 100 % fyllt, BRÄDDAR sedan 07:00 UTC, bräddat 2 h totalt; modell 0,74 m vid 100-årsregn (syntetisk)")
    assert node("scenario_events.js", "detectionSteps(3, 'Sundsvall')[3].title") == "Zoom till Sundsvall"
    assert node("scenario_events.js", "detectionStepLine({step: 3, steps: 6})") == "Steg 4/6: Zoom till branden (verkliga data)"
    info = {"name": "acquired", "pass": {"kind": "flood", "instrument": "SAR", "satellite": "Sentinel-1C", "pass_utc": "2026-08-16T05:21:32Z"},
            "classification": {"counts": {}, "rules": []}}
    assert node("scenario_events.js", f"detectionDetail({json.dumps(info)}, null)").startswith("Radar (SAR) på Sentinel-1C tar en bild över Sundsvall 05:21 UTC")
    assert node("scenario_events.js", "syncLines({passes: [{time_utc: '2026-08-16T05:21:32Z', text: 'Sentinel-1C radarbild'}], area_increase_pct: null})") == [
        {"level": "info", "text": "08-16 05:21 UTC – Sentinel-1C radarbild"}]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_sentinel_1_passes_are_the_catalogue_acquisitions() -> None:
    item = {"half_swath_km": None, "acquisitions": ["2026-08-16T05:21:32Z", "2026-08-16T16:37:32Z", "2026-08-17T05:13:33Z"]}
    day = "Date.parse('2026-08-16T00:00:00Z'), Date.parse('2026-08-17T00:00:00Z')"
    passes = node("orbits.js", f"satellitePasses(null, {json.dumps(item)}, {day}, 62.39, 17.31)")
    assert [(entry["end"] - entry["start"]) for entry in passes] == [25000, 25000]
    assert node("orbits.js", f"[hasPasses({json.dumps(item)}), hasPasses({{half_swath_km: null}}), hasPasses({{half_swath_km: 92.5}})]") == [True, False, True]


def run_flood(code: str) -> str:
    import os
    import sys
    env = {**os.environ, "TECHSEED_SCENARIO": "sundsvall2026"}
    return subprocess.run([sys.executable, "-c", code], cwd=FRONTEND.parents[1], env=env, capture_output=True, text=True, check=True).stdout


def test_the_flood_has_its_own_questions_and_the_overflow_question_uses_the_assessment_s_points() -> None:
    code = """
from app.backend import spatial
print(list(spatial.QUESTIONS))
assessment = {"evidence": [
    {"key": "iot:dv-01", "status": "ok", "text": "IoT DV1 Bergsåker: bräddning", "ref": {"latitude": 62.42, "longitude": 17.21}},
    {"key": "iot:dv-02", "status": "miss", "text": "IoT DV2 Granlo: 40 % fyllt", "ref": {"latitude": 62.40, "longitude": 17.25}},
    {"key": "rain_hour", "status": "ok", "text": "Regn", "ref": {"latitude": 62.39, "longitude": 17.33}}]}
points = spatial.overflow_points(assessment)
print(points)
from datetime import datetime, timezone
sql = spatial.sql_for("near_overflow", datetime(2026, 8, 16, 8, 30, tzinfo=timezone.utc), points)
print("ST_MakePoint(17.21, 62.42)" in sql, "{points}" in sql, "ST_DWithin" in sql)
rows = [{"kind": "building", "area": "Ljungan (MCF)", "total": 3}, {"kind": "building", "area": "Ljungan (MCF) · Selångersån (kommunen, 2009)", "total": 3}]
print(spatial.flood_summary("buildings_100y", rows, None))
print(spatial.flood_summary("near_overflow", [], []))
"""
    lines = run_flood(code).splitlines()
    assert lines[0] == "['why_flood', 'buildings_100y', 'roads_100y', 'near_overflow']"
    assert lines[1] == "[('DV1 Bergsåker', 62.42, 17.21)]"  # only the overflowing sensors
    assert lines[2] == "True False True"
    # Two rows of three shown; a building can lie in two areas.
    assert lines[3] == ("3 byggnader inom 100-årsflödet (Ljungan (MCF): 2, Selångersån (kommunen, 2009): 1) (de första 1000 visas). "
                        "Kommunens och MCF:s modeller, inte observationer.")
    assert lines[4] == "Inga bräddande punkter vid scenariotiden (syntetiska bräddgivare)."


def radar_scene(moment: str, separable: bool, share: float) -> dict:
    return {"acquired_utc": moment, "images": {"radar": "x", "radarwater": "y"}, "separable": separable, "new_water_pct": share}


def test_the_radar_image_s_water_counts_only_where_it_can_tell_water_from_land(tmp_path: Path) -> None:
    acquisitions = [{"time_utc": "2026-08-16T05:21:32Z", "satellite": "Sentinel-1C", "norad": "62261"},
                    {"time_utc": "2026-08-17T05:13:33Z", "satellite": "Sentinel-1D", "norad": "66315"}]
    scenes = [radar_scene("2026-08-16T05:21:32Z", False, 3.0), radar_scene("2026-08-17T05:13:33Z", True, 1.5)]
    assessor = fa.FloodAssessor([STATION], acquisitions, scenes, (62.39, 17.31))
    flood = sensors(tmp_path, [point(1, "Haga", 0.75)])
    uncertain = assessor.classify(assessor.pass_at("2026-08-16T05:21:32Z"), flood.at(at("2026-08-16T08:30:00Z")))["rules"][3]
    assert not uncertain["holds"] and "skiljs dåligt åt" in uncertain["text"]
    clear = assessor.classify(assessor.pass_at("2026-08-17T05:13:33Z"), flood.at(at("2026-08-16T08:30:00Z")))["rules"][3]
    assert clear["holds"] and clear["text"].startswith("Radarbilden: vatten utanför sjöar och hav på 1,5 % av stans land")
    line = {item["key"]: item for item in assessor.at(at("2026-08-17T06:00:00Z"), flood.at(at("2026-08-17T06:00:00Z")))["evidence"]}["radar"]
    assert line["text"].startswith("Senaste radarbild: Sentinel-1D 08-17 05:13 UTC – vatten utanför sjöar och hav på 1,5 %")


def test_the_flood_shows_the_era5_land_wind_as_the_fire_does() -> None:
    code = """
from app.backend import scenario, server
print(scenario.ATTRIBUTION["era5_land"].startswith("Innehåller bearbetad information från Copernicus"))
print(scenario.WIND_FILE.exists())
if scenario.WIND_FILE.exists():
    field = server.wind_field()
    print(len(field["points"]), field["times_utc"][0], field["times_utc"][-1], field["sources"].count("ERA5-Land"))
"""
    lines = run_flood(code).splitlines()
    assert lines[0] == "True"
    if lines[1] == "True":  # data/ is not in the repository; fetched with tools/fetch_era5_land.py and fetch_era5_sea.py
        # 39 ERA5-Land points on land; with the sea file also the 11 at sea from ERA5
        assert lines[2] in ("39 2026-08-14T00:00:00Z 2026-08-22T23:00:00Z 39", "50 2026-08-14T00:00:00Z 2026-08-22T23:00:00Z 39")


def test_the_flood_s_words_come_from_the_scenario() -> None:
    info = {"pass": {"kind": "flood", "instrument": "SAR", "satellite": "Sentinel-1A", "pass_utc": "2024-01-27T16:45:22Z"},
            "name": "acquired", "classification": {"counts": {}, "rules": []}}
    assert node("scenario_events.js", f"detectionDetail({json.dumps(info)}, null, 'Ringsjöarna')").startswith(
        "Radar (SAR) på Sentinel-1A tar en bild över Ringsjöarna 16:45 UTC")
    scene = {"separable": True, "new_water_pct": 2.13}
    words = fa.FloodAssessor([], [], [], (55.9, 13.5), place_name="Ringsjöarna", focus_land="marken runt Ringsjöarna",
                             gauges="VA-huvudmännens mätare")
    assert words.radar_text(scene) == "vatten utanför sjöar och hav på 2,13 % av marken runt Ringsjöarna (beräknat, enkel tröskel)"
    assert fa.FloodAssessor([], [], [], (62.4, 17.3)).radar_text(scene).endswith("av stans land (beräknat, enkel tröskel)")


# A river flood's SYNTHETIC rain, flows and level, shaped like /api/hydro (hydro.py).
RIVER_RAIN = {"name": "Regnmätaren", "latitude": 55.9, "longitude": 13.4, "observations": [
    {"time_utc": "2024-01-22T12:00:00Z", "precip_mm": 20.0},
    {"time_utc": "2024-01-24T12:00:00Z", "precip_mm": 15.0},
]}
FLOW = {"id": "1:2", "name": "Ån", "kind": "flow", "latitude": 55.88, "longitude": 13.5,
        "earlier_max": {"value": 25.0, "time_utc": "2005-03-18T10:30:00Z"},
        "observations": [{"time_utc": "2024-01-24T00:00:00Z", "value": 20.0}, {"time_utc": "2024-01-25T00:00:00Z", "value": 30.0}]}
LEVEL = {"id": "2:3", "name": "Sjön", "kind": "level", "latitude": 55.87, "longitude": 13.45,
         "earlier_max": {"value": 5478.0, "time_utc": "2002-03-09T00:00:00Z"},
         "observations": [{"time_utc": "2024-01-25T00:00:00Z", "value": 5470.0}, {"time_utc": "2024-01-26T00:00:00Z", "value": 5480.0}]}
NO_SENSORS = {"sensors": []}


def test_a_river_flood_weighs_the_rain_of_days_and_smhi_s_flows_and_levels_above_their_records() -> None:
    assessor = fa.FloodAssessor([RIVER_RAIN], [], [], (55.88, 13.47), gauges="mätarna", hydro=[FLOW, LEVEL])
    early = {item["key"]: item for item in assessor.at(at("2024-01-24T18:00:00Z"), NO_SENSORS)["evidence"]}
    assert "rain_hour" not in early and early["rain_days"]["status"] == "ok"  # 35 mm in five days
    assert early["rain_days"]["text"] == "35,0 mm regn de senaste 5 dygnen vid Regnmätaren (SMHI, mätarna; regel ≥ 30,0 mm)"
    assert early["flow"]["status"] == "miss" and early["flow"]["text"] == "Vattenföring under tidigare högsta: närmast Ån 20,0 m³/s av 25,0 m³/s (SMHI)"
    late = assessor.at(at("2024-01-26T06:00:00Z"), NO_SENSORS)
    keys = {item["key"]: item for item in late["evidence"]}
    assert keys["flow"]["text"] == "Vattenföring över tidigare högsta: Ån 30,0 m³/s (tidigare högsta 25,0 m³/s, 2005) (SMHI)"
    assert keys["level"]["status"] == "ok" and "Sjön 54,80 m (tidigare högsta 54,78 m, 2002)" in keys["level"]["text"]
    assert (late["outcome"], late["score_pct"]) == ("Possible flood", 63)  # 1 - 0.75 x 0.70 x 0.70


def test_a_river_flood_s_detection_counts_the_rain_of_days_the_flows_the_level_and_the_radar() -> None:
    acquisitions = [{"time_utc": "2024-01-25T16:45:00Z", "satellite": "Sentinel-1A", "norad": "39634"}]
    scenes = [radar_scene("2024-01-25T16:45:00Z", True, 2.0)]
    assessor = fa.FloodAssessor([RIVER_RAIN], acquisitions, scenes, (55.88, 13.47), hydro=[FLOW, LEVEL])
    result = assessor.classify(assessor.pass_at("2024-01-25T16:45:00Z"), NO_SENSORS)
    assert [rule["holds"] for rule in result["rules"]] == [True, True, False, True]  # the level rises over it the next day
    assert result["rules"][0]["text"].startswith("35,0 mm regn de 5 dygnen före bilden vid Regnmätaren")
    assert result["outcome"] == "Översvämning trolig" and result["counts"] == {"Översvämning": 3}
    assert "SMHI:s uppmätta flöden och nivåer" in result["label"]


def run_scenario(name: str, code: str) -> str:
    import os
    import sys
    env = {**os.environ, "TECHSEED_SCENARIO": name}
    return subprocess.run([sys.executable, "-c", code], cwd=FRONTEND.parents[1], env=env, capture_output=True, text=True, check=True).stdout


def test_skane_s_questions_name_mcf_s_climate_adapted_flow_and_load_without_municipal_data() -> None:
    code = """
from app.backend import scenario, spatial
print(spatial.QUESTIONS["buildings_100y"]["question"])
print(spatial.flood_summary("buildings_100y", [{"kind": "building", "area": "Kävlingeån (MCF, klimatanpassat)", "total": 1}], None))
print(scenario.MCF_LAYERS["100ar"][0], scenario.FLOOD_HAZARD_WMS["visible"])
if (scenario.MCF_DIR / "mcf-100ar.geojson").is_file():  # data/ is not in the repository
    from tools import load_postgis
    sql = "\\n".join(load_postgis.flood_rows())
    print("stormwater_points" in sql, "(MCF, klimatanpassat)" in sql)
"""
    lines = run_scenario("skane2024", code).splitlines()
    assert lines[0] == "Vilka byggnader ligger inom det klimatanpassade 100-årsflödet?"
    assert lines[1] == ("1 byggnader inom det klimatanpassade 100-årsflödet (Kävlingeån (MCF, klimatanpassat): 1). "
                        "MCF:s modell för slutet av seklet, inte observationer.")
    assert lines[2] == "3 ['12']"  # REST layer 3 and WMS layer 12: the climate-adapted 100-year flow
    if len(lines) > 3:
        assert lines[3] == "False True"  # no municipal stormwater points, MCF's areas with their label
