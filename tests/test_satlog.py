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
    places = [{"clock_utc": "2014-08-04T08:00:00Z", "places": [{"name": name, "span": f"{index + 2}–10 h", "latitude": 59.9, "longitude": 16.0 + index / 10}
                                                              for index, name in enumerate(["Axholm", "Lågbo", "Ormdalen", "Skillberg", "Hönäs", "Näs"])]},
              {"clock_utc": "2014-08-04T09:30:00Z", "places": [{"name": "Fläckebo", "span": "7–>24 h", "latitude": 59.95, "longitude": 16.3}]}]
    threats = {"places": places, "distance_m": 200, "buildings_near": {
        "dv-03": {"count": 78, "latitude": 62.37, "longitude": 17.31, "place": "Skönsmon"},
        "dv-01": {"count": 1, "latitude": 62.42, "longitude": 17.36, "place": None},
    }}
    lines = node(f"satelliteLog({{ sensorEvents: {sensor_events}, threats: {json.dumps(threats)} }}, {CLOCK})")
    assert [(line["text"], line["source"]) for line in lines] == [
        ("Bräddgivare DV3 Skönsmon slutar brädda", "synthetic"),
        ("1 byggnad inom 200 m från Bräddgivare DV1 Bergsåker", "postgis"),
        ("Bräddgivare DV1 Bergsåker bräddar", "synthetic"),
        ("1 ort hotas inom 24 h: Fläckebo 7–>24 h", "model"),
        ("78 byggnader i Skönsmon inom 200 m från Bräddgivare DV3 Skönsmon", "postgis"),
        ("Bräddgivare DV3 Skönsmon bräddar", "synthetic"),
        ("6 orter hotas inom 24 h: Axholm 2–10 h, Lågbo 3–10 h, Ormdalen 4–10 h, Skillberg 5–10 h och 2 till", "model"),
    ]
    assert node("[SATLOG_SOURCES.model, SATLOG_SOURCES.postgis]") == ["modell", "PostGIS"]
    # The maps' marks: each place once, small; a highlighted line's places large and last (drawn on top);
    # without a place, the sensor's name.
    log = f"satelliteLog({{ sensorEvents: {sensor_events}, threats: {json.dumps(threats)} }}, {CLOCK})"
    marks = node(f"threatMarks({log})")
    assert [mark["name"] for mark in marks] == [
        "Bräddgivare DV1 Bergsåker", "Fläckebo", "Skönsmon", "Axholm", "Lågbo", "Ormdalen", "Skillberg", "Hönäs", "Näs",
    ] and not any(mark["latest"] for mark in marks)
    marks = node(f"(() => {{ const lines = {log}; return threatMarks(lines, new Set([satlogKey(lines.find((line) => line.text.startsWith('1 ort')))])); }})()")
    assert [(mark["name"], mark["latest"]) for mark in marks][-2:] == [("Näs", False), ("Fläckebo", True)]
    assert marks[0]["name"] == "Bräddgivare DV1 Bergsåker" and marks[0]["latitude"] == 62.42 and marks[0]["longitude"] == 17.36
    # A sensor that failed before it alarms marks nothing.
    failed = node(f"threatMarks(satelliteLog({{ events: [{{ kind: 'sensor_failure', target: 'dv-01', clock_utc: '2014-08-04T09:00:00Z' }}], "
                  f"sensorEvents: {sensor_events}, threats: {json.dumps(threats)} }}, {CLOCK}))")
    assert "Bräddgivare DV1 Bergsåker" not in [mark["name"] for mark in failed]


def test_a_threat_that_comes_in_while_playing_is_highlighted_for_a_few_seconds() -> None:
    threats = {"places": [{"clock_utc": "2014-08-04T08:00:00Z", "places": [{"name": "Axholm", "span": "2–10 h", "latitude": 59.9, "longitude": 16.0}]},
                          {"clock_utc": "2014-08-04T10:00:00Z", "places": [{"name": "Fläckebo", "span": "7–>24 h", "latitude": 59.95, "longitude": 16.3}]}]}
    steps = node(
        f"(() => {{ const threats = {json.dumps(threats)}; const at = (time) => satelliteLog({{ threats }}, Date.parse(time));"
        " const names = (step, lines) => threatMarks(lines, new Set(step.highlights.keys())).filter((mark) => mark.latest).map((mark) => mark.name);"
        " const out = []; let step = { highlights: new Map(), seen: new Set() };"
        # the load: a jump, nothing large
        " let lines = at('2014-08-04T09:00:00Z'); step = threatHighlights(step.highlights, step.seen, lines, 0, true, true); out.push(names(step, lines));"
        # Fläckebo comes in while playing: large
        " lines = at('2014-08-04T10:05:00Z'); step = threatHighlights(step.highlights, step.seen, lines, 1000, true, false); out.push(names(step, lines));"
        # still large a moment later, small after THREAT_HIGHLIGHT_MS
        " step = threatHighlights(step.highlights, step.seen, lines, 1000 + THREAT_HIGHLIGHT_MS - 1, true, false); out.push(names(step, lines));"
        " step = threatHighlights(step.highlights, step.seen, lines, 1000 + THREAT_HIGHLIGHT_MS, true, false); out.push(names(step, lines));"
        # a RESET or seek back and forth: not large again, also when paused
        " step = threatHighlights(step.highlights, step.seen, at('2014-08-04T09:00:00Z'), 20000, false, true);"
        " lines = at('2014-08-04T10:05:00Z'); step = threatHighlights(step.highlights, step.seen, lines, 21000, false, false); out.push(names(step, lines));"
        " return [out, THREAT_HIGHLIGHT_MS]; })()"
    )
    assert steps == [[[], ["Fläckebo"], ["Fläckebo"], [], []], 8000]


def test_only_new_lines_are_read_aloud_and_many_are_cut_short() -> None:
    def lines(*minutes: int) -> str:
        return json.dumps([{"atMs": CLOCK - m * MINUTE, "text": f"rad {m}", "source": "synthetic"} for m in sorted(minutes)])
    spoken = node(f"(() => {{ const heard = new Set({lines(50, 40)}.map(satlogKey)); "
                  f"return [spokenLines({lines(30, 40, 50)}, heard), spokenLines({lines(30, 40, 50)}, heard), "
                  f"spokenLines({lines(1, 2, 3, 4, 5, 30, 40, 50)}, heard)]; }})()")
    assert spoken == [[{"text": "rad 30", "voice": "alma"}], [],
                      [{"text": f"rad {m}", "voice": "alma"} for m in (3, 2, 1)] + [{"text": "och 2 händelser till", "voice": "alma"}]]
    # Satellite events take nst, the others alma; a satellite leaving the area is not read.
    mixed = [
        {"atMs": CLOCK - 1, "text": "Aqua (MODIS) lämnar Sundsvall", "source": "computed", "kind": "leave"},
        {"atMs": CLOCK - 2, "text": "Sentinel-1C tar bild över Sundsvall", "source": "landsat", "kind": "landsat"},
        {"atMs": CLOCK - 3, "text": "SATCOM nere – satellitdata köas", "source": "simulated", "kind": "satcom_failure"},
        {"atMs": CLOCK - 4, "text": "Aqua (MODIS) över Sundsvall", "source": "computed", "kind": "enter"},
    ]
    assert node(f"spokenLines({json.dumps(mixed)}, new Set())") == [
        {"text": "Aqua (MODIS) över Sundsvall", "voice": "nst"},
        {"text": "SATCOM nere – satellitdata köas", "voice": "alma"},
        {"text": "Sentinel-1C tar bild över Sundsvall", "voice": "nst"},
    ]
    monitor = (SCRIPT.parent / "monitor.js").read_text(encoding="utf-8")
    assert "if (scenarioState.jump !== heardJump) {" in monitor and 'post("/api/speak", { lines });' in monitor
    assert "speechSynthesis" not in monitor  # the backend speaks Swedish; Chrome had no Swedish voice
    assert "if (scenarioState.status?.speech) speak(spoken);" in monitor


def test_the_level_sensors_are_reported_once_per_scenario_day_while_any_alarms() -> None:
    def sensor(station: str, kind: str, confirms: bool = True, status: str = "ok", **values) -> dict:
        return {"kind": "level", "status": status, "confirms": confirms, "station": station, "station_kind": kind, **values}
    sensors = [sensor("Ringsjödammen övre", "level", from_record_cm=3), sensor("Ringsjödammen övre", "level", from_record_cm=3),
               sensor("Heåkra", "flow", percent=112), sensor("Ellinge", "flow", confirms=False, percent=77),
               sensor("Högsmölla", "flow", status="failed", percent=None), {"kind": "sewer", "status": "ok", "confirms": True}]
    assert node(f"levelReport({json.dumps(sensors)})") == (
        "Nivålarm från 3 nivågivare: Ringsjödammen övre 3 centimeter över tidigare högsta nivå. "
        "Heåkra 112 procent av tidigare högsta flöde.")
    assert node(f"levelReport({json.dumps(sensors[3:])})") is None
    day = 24 * HOUR
    steps = node(f"""(() => {{ let next = null; const out = [];
        for (const [clock, alarming, jumped] of [[0, true, false], [{day - 1}, true, false], [{day}, true, false],
             [{3 * day + 5}, true, false], [{3 * day + 6}, false, false], [{4 * day}, true, false], [{9 * day}, true, true]]) {{
          const due = levelReportDue(next, clock, alarming, jumped); next = due.next; out.push([due.speak, next]); }}
        return out; }})()""")
    assert steps == [[False, day], [False, day], [True, 2 * day], [True, 4 * day], [False, None], [False, 5 * day], [False, 10 * day]]
    monitor = (SCRIPT.parent / "monitor.js").read_text(encoding="utf-8")
    assert 'if (due.speak && scenarioState.playing) spoken.push({ text: report, voice: "alma" });' in monitor
    assert 'source.addEventListener("synthetic_sensors"' in monitor
