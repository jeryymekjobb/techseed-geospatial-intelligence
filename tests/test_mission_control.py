"""Tests for mission control (control.html, control.js) and the event texts both screens
share (scenario_events.js): the buttons send only commands the scenario engine knows,
every event has a text, and the texts are checked with Node.js when it is installed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from app.backend import lantmateriet, server
from app.backend.scenario_engine import DETECTION_STEPS, EVENT_KINDS, FILTERS, MAX_SPEED, MIN_SPEED

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
CLOCK_COMMANDS = {"play", "pause", "reset", "speed", "next"}


def test_the_buttons_send_only_commands_the_engine_knows() -> None:
    html = (FRONTEND / "control.html").read_text(encoding="utf-8")
    commands = set(re.findall(r'data-command="(\w+)"', html)) | set(re.findall(r'data-toggle-off="(\w+)"', html))
    # place_sensor comes from the main screen's map, not from a button.
    # seek is VISA ALLA, camera FLYG TILL and ÖVERSIKT, clear_answer RENSA SVARET (the questions are made from
    # /api/questions); speed is sent by ANVÄND with the list's value (control.js).
    assert commands == set(EVENT_KINDS) - {"place_sensor", "filter"} | CLOCK_COMMANDS - {"speed"} | {"seek", "camera", "clear_answer"}
    for target in re.findall(r'data-target="([^"]+)"', html):
        assert re.fullmatch(r"[a-z0-9_-]{1,64}", target)
    assert 'data-command="filter"' not in html
    assert html.count('id="map-layers"') == 1
    assert html.index('data-image="auto"') < html.index('id="map-layers"') < html.index('id="image-types"')
    control = (FRONTEND / "control.js").read_text(encoding="utf-8")
    assert "for (const category of FILTER_CATEGORIES)" in control
    assert 'send("filter", input.dataset.category)' in control
    # The speeds are a list with ANVÄND (control.js), as on the main screen.
    speeds = [float(value) for value in re.findall(r'<option value="([0-9.]+)">', html.split('id="speed-pick"', 1)[1].split("</select>", 1)[0])]
    assert speeds == [60.0, 600.0, 1800.0, 3600.0, 10800.0] and all(MIN_SPEED <= value <= MAX_SPEED for value in speeds)


def test_every_event_kind_has_a_text() -> None:
    source = (FRONTEND / "scenario_events.js").read_text(encoding="utf-8")
    block = source.split("const EVENT_TEXTS = {", 1)[1].split("};", 1)[0]
    assert set(re.findall(r"^  (\w+):", block, flags=re.MULTILINE)) == set(EVENT_KINDS)


def test_every_screen_loads_the_shared_texts_before_its_own_script() -> None:
    for page in ["index.html", "3d.html", "control.html"]:
        html = (FRONTEND / page).read_text(encoding="utf-8")
        follower = "/panel.js" if page != "control.html" else "/control.js"
        for shared in ["/scenario_events.js", "/sensors.js"]:
            assert f'<script src="{shared}"></script>' in html
            assert html.index(shared) < html.index(follower)


def test_mission_control_resets_once_after_document_config_and_initial_sync_are_ready() -> None:
    source = (FRONTEND / "control.js").read_text(encoding="utf-8")
    assert 'let documentLoaded = document.readyState === "complete"' in source
    assert "let startupConfigReady = false" in source
    assert "let startupSyncReady = false" in source
    assert "let startupResetSent = false" in source
    gate = source.index("if (!documentLoaded || !startupConfigReady || !startupSyncReady || startupResetSent) return")
    reset = source.index('send("reset")', gate)
    seek = source.index('send("seek", null, null, startupAt)', reset)
    assert gate < reset < seek
    assert 'startupAt && startupAt !== config.playback.start_utc' in source
    assert 'if (event.type === "sync" && !startupSyncReady)' in source
    config_complete = source.index("startupConfigReady = true")
    assert source.index("resetAfterMissionControlLoad();", config_complete) > config_complete


def test_the_demos_start_and_stop_are_set_in_swedish_time_and_sent_with_anvand_tider() -> None:
    html = (FRONTEND / "control.html").read_text(encoding="utf-8")
    for element in ['id="window-start" type="datetime-local"', 'id="window-end" type="datetime-local"', 'id="apply-window"']:
        assert html.count(element) == 1
    source = (FRONTEND / "control.js").read_text(encoding="utf-8")
    assert 'send("playback_window", `${first}/${last}`)' in source
    assert "setupWindow();" in source and "showWindow(scenarioState);" in source


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_window_fields_convert_between_utc_and_swedish_time() -> None:
    source = (FRONTEND / "control.js").read_text(encoding="utf-8")
    helpers = source[source.index("const wallClock"):source.index("function showWindow")]
    code = helpers + (
        "console.log(JSON.stringify([wallTime('2026-08-14T00:00:00Z'), utcFromWallTime('2026-08-14T02:00'),"
        " wallTime('2024-01-20T00:00:00Z'), utcFromWallTime('2024-01-20T01:00'), utcFromWallTime('')]));"
    )
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert result == ["2026-08-14T02:00", "2026-08-14T00:00:00Z", "2024-01-20T01:00", "2024-01-20T00:00:00Z", None]


def test_the_satellite_image_buttons_and_spara_profil_are_in_the_left_column() -> None:
    html = (FRONTEND / "control.html").read_text(encoding="utf-8")
    left = html.split('<section class="control-clock">', 1)[1].split("</section>", 1)[0]
    for element in ['data-command="satellite_detection"', 'id="next"', 'id="detection-step"', 'data-image="off"',
                    'data-image="auto"', 'id="image-pick"', 'id="show-pick"', 'id="image-shown"',
                    'id="save-profile"', 'id="profile-note"']:
        assert left.count(element) == 1, element
    assert left.index('id="show-all"') < left.index("<h2>Satellitbilder</h2>") < left.index('id="save-profile"')
    # The flood's rain gauge is chosen in the left column too, above Satellitbilder; the other choices stay under Kartan.
    assert left.index('id="show-all"') < left.index('id="left-choices"') < left.index("<h2>Satellitbilder</h2>")
    assert html.count('id="panel-choices"') == 1 and 'id="panel-choices"' not in left
    source = (FRONTEND / "control.js").read_text(encoding="utf-8")
    assert 'const LEFT_CHOICES = ["rain_station"];' in source


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_spara_profil_is_marked_while_the_settings_differ_from_the_profile() -> None:
    source = (FRONTEND / "control.js").read_text(encoding="utf-8")
    compare = source[source.index("function profileUnsaved"):source.index("// SPARA PROFIL is red")]
    config = {
        "incident": "flood",
        "playback": {"start_utc": "2026-08-14T00:00:00Z", "end_utc": "2026-08-23T00:00:00Z",
                     "data_start_utc": "2026-08-14T00:00:00Z", "data_end_utc": "2026-08-23T00:00:00Z",
                     "default_speed": 600},
        "layers": {
            "landsat": {"names": {"radar": "Radar", "natural": "Naturliga färger"}},
            "base_maps": [{"id": "offline"}, {"id": "online"}],
            "map_layers": [{"name": "Nederbörd (SMHI radar)", "default_2d": True, "default_3d": True},
                           {"name": "Terräng (OSM)", "default_2d": True, "default_3d": False}],
        },
    }
    untouched = {"start_utc": "2026-08-14T00:00:00Z", "end_utc": "2026-08-23T00:00:00Z", "speed": 600,
                 "status": {"image_types": None, "base_maps": None, "map_layers": {}, "speech": True}}
    cases = [
        (None, untouched),  # no profile, nothing changed
        (None, {**untouched, "status": {**untouched["status"], "map_layers": {"Terräng (OSM)": True}}}),
        (None, {**untouched, "end_utc": "2026-08-20T00:00:00Z"}),
        ({"image_types": None, "base_maps": ["offline"], "map_layers": {"Nederbörd (SMHI radar)": True, "Terräng (OSM)": False},
          "playback": None}, untouched),  # saved as it is now
        ({"image_types": ["natural"], "base_maps": None, "map_layers": None, "playback": None}, untouched),
        ({"image_types": None, "base_maps": None, "map_layers": None,
          "playback": {"start_utc": "2026-08-16T00:00:00Z", "end_utc": "2026-08-20T00:00:00Z"}},
         {**untouched, "start_utc": "2026-08-16T00:00:00Z", "end_utc": "2026-08-20T00:00:00Z"}),
        (None, {**untouched, "speed": 60}),  # another speed than the default
        (None, {**untouched, "status": {**untouched["status"], "speech": False}}),  # reading aloud switched off
        ({"image_types": None, "base_maps": None, "map_layers": None, "playback": None, "speed": 60},
         {**untouched, "speed": 60}),  # the saved speed
    ]
    code = (
        f"const landsat = require({json.dumps(str(FRONTEND / 'landsat.js'))});"
        f"const basemaps = require({json.dumps(str(FRONTEND / 'basemaps.js'))});"
        "const { imageTypesShown } = landsat; const { baseMapsShown } = basemaps;"
        + compare
        + f"const config = {json.dumps(config)};"
        + f"console.log(JSON.stringify({json.dumps(cases)}.map(([profile, state]) => profileUnsaved(config, profile, state))));"
    )
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert result == [False, True, True, False, True, False, True, True, False]


def node(expression: str) -> object:
    code = (
        f"const events = require({json.dumps(str(FRONTEND / 'scenario_events.js'))});"
        f"with (events) {{ console.log(JSON.stringify({expression})); }}"
    )
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


QUIET = {"satcom_up": True, "plus60": False, "god_view": False, "space_view": False, "power_failure": False, "failed_sensors": [], "closed_roads": [],
         "satcom_down_since": None, "last_outage": None, "hidden_layers": [], "iot": True, "placed_sensors": [], "detection": None}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_status_lines_mark_synthetic_events() -> None:
    assert node(f"statusLines({json.dumps(QUIET)})") == []
    busy = {**QUIET, "satcom_up": False, "failed_sensors": ["sensor-17"], "closed_roads": [None], "power_failure": True, "god_view": True}
    lines = node(f"statusLines({json.dumps(busy)})")
    assert [line["level"] for line in lines] == ["alert", "alert", "alert", "alert", "info"]
    assert lines[0]["text"] == "SATELLITE DATA UNAVAILABLE (simulerat avbrott)"
    assert all("syntetiskt" in line["text"] for line in lines[1:4])
    assert "sensor-17" in lines[1]["text"] and "väg" in lines[2]["text"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_banners_say_whether_a_toggle_was_switched_on_or_off() -> None:
    on = node(f'eventBanner({{kind: "god_view", target: null}}, {json.dumps({**QUIET, "god_view": True})})')
    off = node(f'eventBanner({{kind: "god_view", target: null}}, {json.dumps(QUIET)})')
    sensor = node(f'eventBanner({{kind: "sensor_failure", target: "sensor-17"}}, {json.dumps(QUIET)})')
    assert on["title"] == "GOD VIEW" and off["title"] == "RETURN TO INCIDENT"
    assert sensor["title"] == "SENSOR FAILURE sensor-17" and "Syntetiskt" in sensor["detail"]
    assert node(f'eventBanner({{kind: "plus60", target: null}}, {json.dumps(QUIET)})')["title"] == "+60 MIN AV"


@pytest.fixture()
def base_url():
    handler = type("TestHandler", (server.Handler,), {"settings": lantmateriet.Settings(None, None, None, None)})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_the_backend_serves_mission_control(base_url: str) -> None:
    for path, kind in [("/control.html", "text/html"), ("/control.js", "javascript"), ("/scenario_events.js", "javascript"), ("/sensors.js", "javascript")]:
        with urlopen(f"{base_url}{path}", timeout=10) as response:
            assert response.status == 200 and kind in response.headers["Content-Type"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_filter_names_every_category_and_marks_the_missing_ones() -> None:
    categories = node("FILTER_CATEGORIES")
    assert [item["id"] for item in categories if not item.get("missing")] == list(FILTERS)
    assert [item["label"] for item in categories if item.get("missing")] == ["Maritime", "Aviation", "Emergency"]
    hidden = {**QUIET, "hidden_layers": ["weather", "space"]}
    assert node(f"statusLines({json.dumps(hidden)})")[-1] == {"level": "info", "text": "Dolda lager: Space, Weather"}
    banner = node(f'eventBanner({{kind: "filter", target: "weather"}}, {json.dumps(hidden)})')
    assert banner == {"title": "FILTER WEATHER", "detail": "Lagret döljs."}
    assert node(f'eventBanner({{kind: "filter", target: "iot"}}, {json.dumps(hidden)})')["detail"] == "Lagret visas."
    assert node('eventText({kind: "filter", target: "space"})')["title"] == "FILTER SPACE"
    assert node('eventText({kind: "sensor_failure", target: "sensor-17"})')["title"] == "SENSOR FAILURE sensor-17"



@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_iot_switch_says_whether_it_was_switched_off_or_on() -> None:
    off = {**QUIET, "iot": False}
    assert node(f'eventBanner({{kind: "iot", target: null}}, {json.dumps(off)})')["title"] == "IOT AV"
    assert node(f'eventBanner({{kind: "iot", target: null}}, {json.dumps(QUIET)})')["title"] == "IOT PÅ"
    assert node(f"statusLines({json.dumps(off)})") == [{"level": "alert", "text": "IoT avstängt – inga sensorer räknas"}]


def test_the_detection_steps_match_the_engine() -> None:
    source = (FRONTEND / "scenario_events.js").read_text(encoding="utf-8")
    block = source.split("const DETECTION_STEPS = [", 1)[1].split("];", 1)[0]
    assert tuple(re.findall(r'name: "(\w+)"', block)) == DETECTION_STEPS


DETECTION = {
    "pass_utc": "2014-08-04T01:36:00Z", "step": 0, "name": "acquired", "steps": 6,
    "pass": {"pass_utc": "2014-08-04T01:36:00Z", "satellite": "SNPP", "instrument": "VIIRS", "detections": 154, "max_frp_mw": 6.96,
             "strongest": {"latitude": 59.89, "longitude": 16.14}, "centre": {"latitude": 59.86, "longitude": 16.21}},
    "classification": {"outcome": "Vegetationsbrand", "counts": {"Vegetationsbrand": 3, "Industri": 0}, "label": "",
                       "rules": [{"category": "Vegetationsbrand", "holds": True}] * 3 + [{"category": "Industri", "holds": False}] * 2},
}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_detection_texts_say_what_is_real_and_what_is_synthetic() -> None:
    steps = node("detectionSteps(1)")
    assert [item["state"] for item in steps] == ["done", "current", "todo", "todo", "todo", "todo"]
    assert [item["real"] for item in steps] == [True, False, False, True, False, True]
    def detail(name: str, iot: str | None = None) -> str:
        return node(f"detectionDetail({json.dumps({**DETECTION, 'name': name})}, {json.dumps(iot)})")
    assert detail("acquired") == "VIIRS på Suomi NPP passerar över branden 01:36 UTC – verklig passage ur FIRMS 2014."
    assert "inte bilderna ombord 2014" in detail("anomaly") and detail("downlink").startswith("Illustrativt")
    assert detail("zoom") == "154 detektioner, starkast 6,96 MW – verkliga FIRMS-data."
    assert detail("iot", "IoT bekräftar 2/3 (syntetiska sensorer)").endswith("IoT bekräftar 2/3 (syntetiska sensorer).")
    assert detail("correlate") == "Vegetationsbrand – 3 av 3 regler för vegetationsbrand och 0 av 2 för industri håller."
    assert node("detectionStepLine(null)") == "Ingen sekvens – tryck SATELLITE DETECTION."
    assert node('detectionStepLine({step: 1, steps: 6})') == "Steg 2/6: Anomali upptäckt ombord (syntetiskt)"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_a_placed_sensor_is_named_as_on_the_map_and_listed_as_synthetic() -> None:
    event = '{kind: "place_sensor", target: "placed-2", latitude: 59.9, longitude: 16.2}'
    assert node(f"eventText({event})")["title"] == "IOT-SENSOR PLACERAD P2"
    placed = {**QUIET, "placed_sensors": [{"id": "placed-1", "name": "Sensor P1"}, {"id": "placed-2", "name": "Sensor P2"}]}
    assert node(f"statusLines({json.dumps(placed)})") == [{"level": "info", "text": "Placerade sensorer: P1, P2 (syntetiska)"}]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_fire_s_texts_take_the_year_from_the_scenario_clock() -> None:
    info = {"name": "acquired", "pass": {"kind": "wildfire", "instrument": "VIIRS", "satellite": "N20", "pass_utc": "2018-07-17T11:20:00Z"},
            "classification": {"counts": {}, "rules": []}}
    code = (f"const m = require({json.dumps(str(FRONTEND / 'scenario_events.js'))}); console.log(JSON.stringify([m.detectionDetail({json.dumps(info)}, null), "
            "m.eventText({kind: 'space_view', clock_utc: '2018-07-17T11:00:00Z'}).detail]));")
    acquired, space = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert acquired == "VIIRS på NOAA-20 passerar över branden 11:20 UTC – verklig passage ur FIRMS 2018."
    assert space == "Satelliternas läge 2018, beräknat ur banelement."


def test_the_buttons_that_apply_a_choice_are_red_while_it_is_not_applied() -> None:
    source = (FRONTEND / "control.js").read_text(encoding="utf-8")
    assert 'function markPending(id, pending) {\n  $(id).disabled = !pending;\n  $(id).classList.toggle("unsaved", pending);' in source
    for button in ("apply-speed", "show-pick", "apply-window"):
        assert f'markPending("{button}", true)' in source or f'markPending("{button}", {"pendingSpeed" if button == "apply-speed" else "pendingPick"} !== null)' in source
        assert f'$("{button}").disabled' not in source  # only through markPending
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    assert ".control button.unsaved { border-color: #ff8a80; background: var(--accent); }" in css
