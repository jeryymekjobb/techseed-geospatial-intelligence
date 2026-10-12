"""Tests for the log of satellite and IoT events under the satellite monitor (app/frontend/satlog.js), in Node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "satlog.js"
MINUTE = 60000
HOUR = 60 * MINUTE
CLOCK = 1_407_150_000_000  # 2014-08-04T11:00:00Z

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")


def node(expression: str) -> object:
    code = f"const m = require({json.dumps(str(SCRIPT))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def hotspot(moment: str, satellite: str = "SNPP", instrument: str = "VIIRS", frp: float = 1.0) -> dict:
    return {"properties": {"acq_datetime_utc": moment, "satellite": satellite, "instrument": instrument, "frp": frp}}


def test_firms_detections_are_grouped_into_passes_per_satellite() -> None:
    features = [
        hotspot("2014-08-04T01:36:00Z", frp=2.5), hotspot("2014-08-04T01:38:00Z", frp=6.96),
        hotspot("2014-08-04T01:37:00Z", "Aqua", "MODIS", 30.0),
        hotspot("2014-08-04T03:18:00Z", frp=1.0),  # the next orbit, more than 15 minutes later
    ]
    passes = node(f"firmsPasses({json.dumps(features)})")
    assert [(item["satellite"], item["detections"], item["maxFrp"]) for item in passes] == [
        ("SNPP", 2, 6.96), ("Aqua", 1, 30.0), ("SNPP", 1, 1.0)]


def test_the_log_lists_what_happened_up_to_the_clock_newest_first() -> None:
    data = {
        "satellites": [{"name": "Suomi NPP", "instrument": "VIIRS", "passes": [
            {"start": CLOCK - 2 * HOUR, "end": CLOCK - 2 * HOUR + 5 * MINUTE},
            {"start": CLOCK - 2 * MINUTE, "end": CLOCK + 3 * MINUTE},  # going on now: only its entry
            {"start": CLOCK + HOUR, "end": CLOCK + HOUR + 5 * MINUTE},  # ahead of the clock
        ]}],
        "firms": [{"atMs": CLOCK - 2 * HOUR + MINUTE, "satellite": "SNPP", "instrument": "VIIRS", "detections": 154, "maxFrp": 6.96}],
        "scenes": [{"acquired_utc": "2014-08-04T10:06:00Z"}, {"acquired_utc": "2014-09-14T10:00:00Z"}],
        "events": [{"kind": "satcom_failure", "clock_utc": "2014-08-04T10:30:00Z"}, {"kind": "iot", "clock_utc": "2014-08-04T10:40:00Z"}],
    }
    lines = node(f"satelliteLog({json.dumps(data)}, {CLOCK})")
    assert [(line["text"], line["source"]) for line in lines] == [
        ("Suomi NPP (VIIRS) över branden", "computed"),
        ("IoT avstängt från mission control", "simulated"),
        ("SATCOM nere – satellitdata köas", "simulated"),
        ("Landsat 8 tar bild över branden", "landsat"),
        ("Suomi NPP (VIIRS) lämnar branden", "computed"),
        ("154 detektioner från Suomi NPP (VIIRS), starkast 7 MW", "firms"),
        ("Suomi NPP (VIIRS) över branden", "computed"),
    ]


def test_the_log_keeps_the_last_day_and_a_few_lines() -> None:
    passes = [{"start": CLOCK - hours * HOUR, "end": CLOCK - hours * HOUR + MINUTE} for hours in (1, 2, 3, 4, 30)]
    lines = node(f"satelliteLog({{satellites: [{{name: 'Aqua', instrument: 'MODIS', passes: {json.dumps(passes)}}}]}}, {CLOCK}, 86400000, 6)")
    assert len(lines) == 6 and lines[0]["atMs"] == CLOCK - HOUR + MINUTE
    assert len(node(f"satelliteLog({{satellites: [{{name: 'Aqua', passes: {json.dumps(passes)}}}]}}, {CLOCK})")) == 8  # the 30 h old pass is out
    assert all(line["atMs"] > CLOCK - 24 * HOUR for line in node(f"satelliteLog({{satellites: [{{name: 'Aqua', passes: {json.dumps(passes)}}}]}}, {CLOCK}, 86400000, 99)"))
    assert node(f"satelliteLog({{}}, {CLOCK})") == []


def test_firms_lines_name_their_year_and_noaa_20() -> None:
    lines = node(f"satelliteLog({{ firms: firmsPasses([{json.dumps(hotspot('2018-07-17T11:20:00Z', 'N20'))}]) }}, "
                 "Date.parse('2018-07-17T12:00:00Z'))")
    assert [(line["text"], line["sourceText"]) for line in lines] == [("1 detektion från NOAA-20 (VIIRS), starkast 1 MW", "FIRMS 2018")]


def test_the_sensors_changes_and_mission_control_s_iot_events_are_in_the_log() -> None:
    def at(minutes: int) -> str:
        return f"new Date({CLOCK} - {minutes} * {MINUTE}).toISOString()"
    sensor_events = (
        f"[{{clock_utc: {at(300)}, sensor: 'sensor-17', name: 'Sensor 17', kind: 'fire', confirms: true}},"
        f" {{clock_utc: {at(200)}, sensor: 'dv-03', name: 'DV3 Kubikenborg', kind: 'sewer', confirms: true}},"
        f" {{clock_utc: {at(100)}, sensor: 'sensor-17', name: 'Sensor 17', kind: 'fire', confirms: false}},"  # after its failure
        f" {{clock_utc: {at(50)}, sensor: 'ng-01', name: 'NG1 Räddningsvägen', kind: 'level', confirms: true}},"  # while IoT is off
        f" {{clock_utc: {at(10)}, sensor: 'dv-03', name: 'DV3 Kubikenborg', kind: 'sewer', confirms: false}}]"
    )
    events = (
        f"[{{kind: 'sensor_failure', target: 'sensor-17', clock_utc: {at(150)}}},"
        f" {{kind: 'iot', clock_utc: {at(60)}}}, {{kind: 'iot', clock_utc: {at(40)}}},"
        f" {{kind: 'place_sensor', target: 'placed-1', clock_utc: {at(30)}}}]"
    )
    lines = node(f"satelliteLog({{ events: {events}, sensorEvents: {sensor_events} }}, {CLOCK})")
    assert [(line["text"], line["source"]) for line in lines] == [
        ("Bräddgivare DV3 Kubikenborg slutar brädda", "synthetic"),
        ("Syntetisk sensor P1 placerad på kartan", "simulated"),
        ("IoT påslaget från mission control", "simulated"),
        ("IoT avstängt från mission control", "simulated"),
        ("SENSOR FAILURE – Sensor 17 slutar svara", "simulated"),
        ("Bräddgivare DV3 Kubikenborg bräddar", "synthetic"),
        ("Sensor 17 känner rök eller värme", "synthetic"),
    ]
    assert node("SATLOG_SOURCES.synthetic") == "syntetiskt"


def test_the_monitor_lists_everything_since_the_demo_s_start_in_a_scrolling_list() -> None:
    start = CLOCK - 3 * 24 * HOUR
    passes = [{"start": start + hours * HOUR, "end": start + hours * HOUR + MINUTE} for hours in range(0, 72, 2)]
    data = f"{{satellites: [{{name: 'Aqua', passes: {json.dumps(passes)}}}]}}"
    lines = node(f"satelliteLog({data}, {CLOCK}, {CLOCK} - {start} + 1, Infinity)")
    assert len(lines) == 72 and lines[-1]["atMs"] == start  # back to the first line, at the demo's start
    assert node(f"satelliteLog({data}, {CLOCK}, {CLOCK} - {start + MINUTE} + 1, Infinity)")[-1]["atMs"] == start + MINUTE
    frontend = SCRIPT.parent
    monitor = (frontend / "monitor.js").read_text(encoding="utf-8")
    assert "clock.getTime() - startMs + 1, Infinity, place" in monitor and "row.remove()" not in monitor
    assert ".monitor-log ol { flex: 1; min-height: 0; overflow-y: auto;" in (frontend / "styles.css").read_text(encoding="utf-8")
    assert "från demons start, senaste överst" in (frontend / "monitor.html").read_text(encoding="utf-8")


def test_threatened_buildings_are_in_the_log() -> None:
    sensor_events = (
        f"[{{clock_utc: new Date({CLOCK} - 120 * {MINUTE}).toISOString(), sensor: 'dv-03', name: 'DV3 Skönsmon', kind: 'sewer', confirms: true}},"
        f" {{clock_utc: new Date({CLOCK} - 60 * {MINUTE}).toISOString(), sensor: 'dv-01', name: 'DV1 Bergsåker', kind: 'sewer', confirms: true}},"
        f" {{clock_utc: new Date({CLOCK} - 30 * {MINUTE}).toISOString(), sensor: 'dv-03', name: 'DV3 Skönsmon', kind: 'sewer', confirms: false}}]"
    )
    places = [{"clock_utc": "2014-08-04T08:00:00Z", "places": [{"name": name, "span": f"{index + 2}–10 h"} for index, name in
                                                              enumerate(["Axholm", "Lågbo", "Ormdalen", "Skillberg", "Hönäs", "Näs"])]},
              {"clock_utc": "2014-08-04T09:30:00Z", "places": [{"name": "Fläckebo", "span": "7–>24 h"}]}]
    threats = {"places": places, "buildings_near": {"dv-03": 78, "dv-01": 1}, "distance_m": 200}
    lines = node(f"satelliteLog({{ sensorEvents: {sensor_events}, threats: {json.dumps(threats)} }}, {CLOCK})")
    assert [(line["text"], line["source"]) for line in lines] == [
        ("Bräddgivare DV3 Skönsmon slutar brädda", "synthetic"),
        ("1 byggnad inom 200 m från Bräddgivare DV1 Bergsåker", "postgis"),
        ("Bräddgivare DV1 Bergsåker bräddar", "synthetic"),
        ("1 ort hotas inom 24 h: Fläckebo 7–>24 h", "model"),
        ("78 byggnader inom 200 m från Bräddgivare DV3 Skönsmon", "postgis"),
        ("Bräddgivare DV3 Skönsmon bräddar", "synthetic"),
        ("6 orter hotas inom 24 h: Axholm 2–10 h, Lågbo 3–10 h, Ormdalen 4–10 h, Skillberg 5–10 h och 2 till", "model"),
    ]
    assert node("[SATLOG_SOURCES.model, SATLOG_SOURCES.postgis]") == ["modell", "PostGIS"]
