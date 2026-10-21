"""Tests for the shared scenario clock and its HTTP interface."""

from __future__ import annotations

import importlib
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app.backend import lantmateriet, server
from app.backend.scenarios import AVAILABLE
from app.backend.scenario_engine import CommandError, ScenarioEngine

START = datetime(2014, 7, 31, tzinfo=timezone.utc)
END = datetime(2014, 8, 15, tzinfo=timezone.utc)


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def engine() -> tuple[ScenarioEngine, FakeTime]:
    fake = FakeTime()
    return ScenarioEngine(START, END, monotonic=fake, speed=3600), fake


def test_clock_advances_only_while_playing() -> None:
    scenario, fake = engine()

    fake.now += 10
    assert scenario.snapshot()["clock_utc"] == "2014-07-31T00:00:00Z"
    scenario.command("play")
    fake.now += 10  # 10 s at 1 h/s
    assert scenario.snapshot()["clock_utc"] == "2014-07-31T10:00:00Z"
    scenario.command("pause")
    fake.now += 10
    assert scenario.snapshot()["clock_utc"] == "2014-07-31T10:00:00Z"


def test_seek_reset_speed_and_end() -> None:
    scenario, fake = engine()

    jump = scenario.snapshot()["jump"]
    assert scenario.command("seek", at="2014-08-04T12:00:00Z")["clock_utc"] == "2014-08-04T12:00:00Z"
    assert scenario.snapshot()["jump"] == jump + 1
    scenario.command("speed", speed=86400)
    scenario.command("play")
    fake.now += 100  # far past the end
    state = scenario.snapshot()
    assert state["clock_utc"] == "2014-08-15T00:00:00Z" and state["finished"] and not state["playing"]
    # Play after the end starts again from the beginning.
    assert scenario.command("play")["clock_utc"] == "2014-07-31T00:00:00Z"
    assert scenario.command("reset")["playing"] is False
    assert scenario.command("seek", at="2010-01-01T00:00:00Z")["clock_utc"] == "2014-07-31T00:00:00Z"


@pytest.mark.parametrize("name", AVAILABLE)
def test_startup_reset_clears_the_selected_scenario(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    selected = importlib.import_module(f"app.backend.scenarios.{name}")
    profile = {"image_types": ["radar", "natural"], "base_maps": ["online"],
               "map_layers": {"Nederbörd (SMHI radar)": True}}
    scenario = ScenarioEngine(selected.PLAYBACK_START, selected.PLAYBACK_END, profile=lambda: profile)
    scenario.command("seek", at=(selected.PLAYBACK_START + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"))
    scenario.command("satcom_failure")
    scenario.command("image", target="off")
    scenario.command("image_types", target="off")
    scenario.command("choose", target="horizon=12")
    monkeypatch.setattr(server.Handler, "engine", scenario)

    server.reset_scenario_for_startup()

    state = scenario.snapshot()
    assert state["clock_utc"] == selected.PLAYBACK_START.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert not state["playing"] and state["events"] == []
    assert state["status"]["satcom_up"] and state["status"]["image"] == "auto"
    assert state["status"]["image_types"] == profile["image_types"]
    assert state["status"]["base_maps"] == profile["base_maps"]
    assert state["status"]["map_layers"] == profile["map_layers"]
    assert state["status"]["choices"] == {}


def test_invalid_commands_are_refused() -> None:
    scenario, _ = engine()

    for name, kwargs in [("dance", {}), ("seek", {}), ("seek", {"at": "soon"}), ("speed", {"speed": 5})]:
        with pytest.raises(CommandError):
            scenario.command(name, **kwargs)


def test_events_are_stored_with_the_scenario_time_and_add_up_to_a_status() -> None:
    scenario, fake = engine()

    assert scenario.snapshot()["status"] == {
        "satcom_up": True, "plus60": False, "god_view": False, "space_view": False, "power_failure": False,
        "failed_sensors": [], "closed_roads": [], "satcom_down_since": None, "last_outage": None, "hidden_layers": [], "iot": True, "placed_sensors": [], "detection": None, "image": "auto",
        "image_types": None, "base_maps": None, "speech": True, "view": None, "camera": {"target": None, "seq": 0}, "map_layers": {}, "choices": {}, "question": {"id": None, "seq": 0},
    }
    scenario.command("seek", at="2014-08-04T12:00:00Z")
    scenario.command("satellite_detection")
    scenario.command("satcom_failure")
    scenario.command("sensor_failure", target="sensor-17")
    scenario.command("sensor_failure", target="sensor-17")
    scenario.command("road_closed", target="road-66")
    scenario.command("plus60")
    state = scenario.command("god_view")

    assert [event["kind"] for event in state["events"]] == [
        "satellite_detection", "satcom_failure", "sensor_failure", "sensor_failure", "road_closed", "plus60", "god_view",
    ]
    assert [event["seq"] for event in state["events"]] == [1, 2, 3, 4, 5, 6, 7]
    assert all(event["clock_utc"] == "2014-08-04T12:00:00Z" for event in state["events"])
    assert state["status"] == {
        "satcom_up": False, "plus60": True, "god_view": True, "space_view": False, "power_failure": False,
        "failed_sensors": ["sensor-17"], "closed_roads": ["road-66"],
        "satcom_down_since": "2014-08-04T12:00:00Z", "last_outage": None, "hidden_layers": [], "iot": True, "placed_sensors": [], "detection": None, "image": "auto",
        "image_types": None, "base_maps": None, "speech": True, "view": None, "camera": {"target": None, "seq": 0}, "map_layers": {}, "choices": {}, "question": {"id": None, "seq": 0},
    }
    # Toggles switch back, and SATCOM can be restored.
    scenario.command("plus60")
    scenario.command("satcom_restore")
    status = scenario.command("power_failure")["status"]
    assert status["satcom_up"] and not status["plus60"] and status["god_view"] and status["power_failure"]


def test_an_outage_keeps_its_start_and_end() -> None:
    scenario, fake = engine()

    scenario.command("seek", at="2014-08-04T12:00:00Z")
    scenario.command("satcom_failure")
    scenario.command("play")
    fake.now += 2  # 2 h at 1 h/s
    scenario.command("satcom_failure")  # pressed again: the outage keeps its start
    assert scenario.snapshot()["status"]["satcom_down_since"] == "2014-08-04T12:00:00Z"
    fake.now += 1
    status = scenario.command("satcom_restore")["status"]
    assert status["satcom_up"] and status["satcom_down_since"] is None
    assert status["last_outage"] == {"from_utc": "2014-08-04T12:00:00Z", "to_utc": "2014-08-04T15:00:00Z"}
    # A restore without an outage changes nothing.
    assert scenario.command("satcom_restore")["status"]["last_outage"] == status["last_outage"]


def test_filters_hide_and_show_categories_until_reset() -> None:
    scenario, _ = engine()

    scenario.command("filter", target="weather")
    scenario.command("filter", target="space")
    assert scenario.snapshot()["status"]["hidden_layers"] == ["weather", "space"]
    assert scenario.command("filter", target="weather")["status"]["hidden_layers"] == ["space"]
    for bad in [None, "maritime", "aviation", "emergency", "forecast"]:
        with pytest.raises(CommandError):
            scenario.command("filter", target=bad)
    assert scenario.command("reset")["status"]["hidden_layers"] == []


def test_the_clock_slows_down_in_a_slow_window_and_speeds_up_after() -> None:
    from datetime import timedelta

    from app.backend.scenario_engine import DEFAULT_SPEED, SLOW_SPEED

    assert DEFAULT_SPEED == 600 and SLOW_SPEED == 60
    scenario, fake = engine()  # 1 hour/s
    window = (START + timedelta(hours=1), START + timedelta(hours=1, minutes=8))
    scenario.set_slow_windows([window])
    scenario.command("play")
    fake.now += 1  # 1 h at full speed reaches the window
    state = scenario.snapshot()
    assert state["clock_utc"] == "2014-07-31T01:00:00Z" and state["slowed"] and state["effective_speed"] == 60
    fake.now += 4  # 4 s at 1 min/s inside the window
    assert scenario.snapshot()["clock_utc"] == "2014-07-31T01:04:00Z"
    fake.now += 4 + 1  # the rest of the window, then 1 s at full speed again
    state = scenario.snapshot()
    assert state["clock_utc"] == "2014-07-31T02:08:00Z" and not state["slowed"] and state["effective_speed"] == 3600


def test_a_high_speed_cannot_jump_over_a_slow_window() -> None:
    from datetime import timedelta

    scenario, fake = engine()
    scenario.command("speed", speed=4 * 86400)  # four days per second
    scenario.set_slow_windows([(START + timedelta(days=1), START + timedelta(days=1, minutes=8)),
                               (START + timedelta(days=1, minutes=5), START + timedelta(days=1, minutes=10))])  # overlapping
    scenario.command("play")
    fake.now += 1
    # One real second: a quarter second to reach the merged 10-minute window, which takes 10 s at 1 min/s.
    assert scenario.snapshot()["clock_utc"] == "2014-08-01T00:00:45Z"


def test_iot_is_switched_off_and_on_and_back_on_after_reset() -> None:
    scenario, _ = engine()

    assert scenario.snapshot()["status"]["iot"] is True
    assert scenario.command("iot")["status"]["iot"] is False
    assert scenario.command("iot")["status"]["iot"] is True
    scenario.command("iot")
    assert scenario.command("reset")["status"]["iot"] is True


def test_events_take_the_time_of_the_running_clock() -> None:
    scenario, fake = engine()

    scenario.command("play")
    fake.now += 5  # 5 s at 1 h/s
    assert scenario.command("satellite_detection")["events"][-1]["clock_utc"] == "2014-07-31T05:00:00Z"


def test_reset_clears_the_events_but_keeps_the_sequence_rising() -> None:
    scenario, _ = engine()

    scenario.command("satcom_failure")
    scenario.command("god_view")
    jump = scenario.snapshot()["jump"]
    state = scenario.command("reset")
    assert state["events"] == [] and state["status"]["satcom_up"] and not state["status"]["god_view"]
    assert state["jump"] == jump + 1
    assert scenario.command("plus60")["events"][0]["seq"] == 3


def test_invalid_event_targets_are_refused_and_the_list_is_bounded() -> None:
    scenario, _ = engine()

    for target in ["", "Sensor 17", "x" * 65, "../etc"]:
        with pytest.raises(CommandError):
            scenario.command("sensor_failure", target=target)
    assert scenario.snapshot()["events"] == []
    for _ in range(150):
        scenario.command("satellite_detection")
    events = scenario.snapshot()["events"]
    assert len(events) == 100 and events[-1]["seq"] == 150


def test_the_image_choice_is_shared_kept_out_of_the_events_and_reset() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["image"] == "auto"
    for choice in ["off", "LC08_L2SP_194018_20140804_02_T1|ndmi", "auto", "S1C_20260816T052132|radarwater"]:
        assert scenario.command("image", target=choice)["status"]["image"] == choice
    for choice in [None, "", "x|", "a|b|c", "../x|swir", "LC08|NDMI"]:
        with pytest.raises(CommandError):
            scenario.command("image", target=choice)
    assert scenario.snapshot()["events"] == []  # a setting, not an event with a banner
    assert scenario.command("reset")["status"]["image"] == "auto"


def test_the_ticked_image_types_are_shared_kept_out_of_the_events_and_reset() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["image_types"] is None  # the screens' default
    assert scenario.command("image_types", target="radar,natural,radar")["status"]["image_types"] == ["radar", "natural"]
    assert scenario.command("image_types", target="")["status"]["image_types"] == []  # none ticked: the map
    for types in [None, "Radar", "radar,", ",radar", "radar;natural"]:
        with pytest.raises(CommandError):
            scenario.command("image_types", target=types)
    assert scenario.snapshot()["events"] == []
    assert scenario.command("reset")["status"]["image_types"] is None


@pytest.fixture()
def base_url():
    fake = FakeTime()
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None),
        "engine": ScenarioEngine(START, END, monotonic=fake, speed=3600),
        "control_token": "secret",
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def post(url: str, body: dict, token: str | None = "secret") -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Control-Token"] = token
    request = Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def first_events(url: str, count: int) -> list[tuple[str, dict]]:
    events = []
    with urlopen(url, timeout=10) as response:
        name = None
        for raw in response:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[6:])))
                if len(events) >= count:
                    return events
    return events


def test_commands_need_the_token_and_change_the_shared_state(base_url: str) -> None:
    assert post(f"{base_url}/api/scenario/command", {"command": "play"}, token=None)[0] == 403
    assert post(f"{base_url}/api/scenario/command", {"command": "dance"})[0] == 400
    status, state = post(f"{base_url}/api/scenario/command", {"command": "seek", "at": "2014-08-04T12:00:00Z"})
    assert status == 200 and state["clock_utc"] == "2014-08-04T12:00:00Z"
    with urlopen(f"{base_url}/api/scenario", timeout=10) as response:
        assert json.loads(response.read())["clock_utc"] == "2014-08-04T12:00:00Z"


def test_every_screen_gets_the_same_sync(base_url: str) -> None:
    post(f"{base_url}/api/scenario/command", {"command": "seek", "at": "2014-08-01T00:00:00Z"})

    first = first_events(f"{base_url}/api/scenario/stream", 1)[0]
    second = first_events(f"{base_url}/api/scenario/stream", 1)[0]

    assert first[0] == second[0] == "sync"
    assert first[1]["state"]["clock_utc"] == second[1]["state"]["clock_utc"] == "2014-08-01T00:00:00Z"
    assert len(first[1]["features"]) == len(second[1]["features"]) > 0
    assert all(item["properties"]["acq_datetime_utc"] <= "2014-08-01T00:00:00Z" for item in first[1]["features"])


def test_events_reach_every_screen(base_url: str) -> None:
    first = first_events(f"{base_url}/api/scenario/stream", 1)[0]
    assert first[0] == "sync" and first[1]["state"]["events"] == []

    status, state = post(f"{base_url}/api/scenario/command", {"command": "sensor_failure", "target": "sensor-17"})
    assert status == 200 and state["status"]["failed_sensors"] == ["sensor-17"]
    assert post(f"{base_url}/api/scenario/command", {"command": "sensor_failure", "target": "Sensor 17"})[0] == 400

    # A screen that connects now gets the event in its sync, not again as a scenario_event.
    late = first_events(f"{base_url}/api/scenario/stream", 4)
    assert late[0][0] == "sync" and late[0][1]["state"]["status"]["failed_sensors"] == ["sensor-17"]
    assert "state" in [name for name, _ in late] and "scenario_event" not in [name for name, _ in late]


def test_a_following_screen_gets_new_events_once(base_url: str) -> None:
    received: list[tuple[str, dict]] = []
    done = threading.Event()

    def follow() -> None:
        with urlopen(f"{base_url}/api/scenario/stream", timeout=10) as response:
            name = None
            for raw in response:
                line = raw.decode("utf-8").rstrip("\n")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    received.append((name, json.loads(line[6:])))
                    if name == "sync":
                        done.set()
                    if sum(1 for event, _ in received if event == "state") >= 6:
                        return

    thread = threading.Thread(target=follow, daemon=True)
    thread.start()
    assert done.wait(5)
    post(f"{base_url}/api/scenario/command", {"command": "satcom_failure"})
    thread.join(10)

    events = [data for name, data in received if name == "scenario_event"]
    assert [event["kind"] for event in events] == ["satcom_failure"]
    assert received[-1][1]["status"]["satcom_up"] is False


def test_the_backend_slows_down_around_every_firms_pass_and_the_landsat_scene() -> None:
    from datetime import timedelta

    windows = server.slow_windows()
    passes = {server.parse_utc(item["acq_datetime_utc"]) for item in server.detections()}
    assert len(windows) >= len(passes) == 48
    assert all(end - start == timedelta(minutes=8) for start, end in windows)
    first = min(passes)
    assert (first - timedelta(minutes=2), first + timedelta(minutes=6)) in windows


def test_with_iot_off_no_sensor_reaches_the_screens_or_the_assessment() -> None:
    scenario, _ = engine()
    scenario.command("seek", at="2014-08-05T12:00:00Z")
    on = scenario.snapshot()
    off = scenario.command("iot")
    assert server.synthetic_at(on)["operating"] == 3
    assert server.synthetic_at(off) == {"label": server.sensor_sim.LABEL, "sensors": [], "confirms": 0, "operating": 0, "disabled": True}
    with_iot, without_iot = server.assessment_at(on), server.assessment_at(off)
    keys = [item["key"] for item in without_iot["evidence"]]
    assert "iot" in keys and not any(key.startswith("iot:") for key in keys)
    assert without_iot["score_pct"] < with_iot["score_pct"]


def test_placed_sensors_are_numbered_inside_the_area_and_cleared_by_reset() -> None:
    scenario = ScenarioEngine(START, END, area=(59.75, 60.08, 15.85, 16.45))
    scenario.command("place_sensor", latitude=59.9123456, longitude=16.2)
    state = scenario.command("place_sensor", latitude=59.95, longitude=16.1)
    assert state["status"]["placed_sensors"] == [
        {"id": "placed-1", "name": "Sensor P1", "latitude": 59.91235, "longitude": 16.2},
        {"id": "placed-2", "name": "Sensor P2", "latitude": 59.95, "longitude": 16.1},
    ]
    assert state["events"][-1] == {**state["events"][-1], "kind": "place_sensor", "target": "placed-2", "latitude": 59.95}
    for kwargs in [{}, {"latitude": 59.9}, {"latitude": 61.0, "longitude": 16.2}, {"latitude": float("nan"), "longitude": 16.2}]:
        with pytest.raises(CommandError):
            scenario.command("place_sensor", **kwargs)
    for index in range(8):
        scenario.command("place_sensor", latitude=59.9, longitude=16.0 + index / 100)
    with pytest.raises(CommandError, match="at most 10"):
        scenario.command("place_sensor", latitude=59.9, longitude=16.3)
    assert scenario.command("reset")["status"]["placed_sensors"] == []


def test_a_sensor_is_placed_through_the_http_api(base_url: str) -> None:
    status, state = post(f"{base_url}/api/scenario/command", {"command": "place_sensor", "latitude": 59.9, "longitude": 16.2})
    assert status == 200 and state["status"]["placed_sensors"][0]["name"] == "Sensor P1"
    assert post(f"{base_url}/api/scenario/command", {"command": "place_sensor", "latitude": "north", "longitude": 16.2})[0] == 400


def test_byt_demo_needs_the_token_and_start_demo(base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert post(f"{base_url}/api/demo/menu", {}, token=None)[0] == 403
    monkeypatch.delenv("TECHSEED_DEMO_MENU_EXIT", raising=False)
    status, body = post(f"{base_url}/api/demo/menu", {})
    assert status == 409 and body["error"] == "no_demo_menu"
    monkeypatch.setenv("TECHSEED_DEMO_MENU_EXIT", "3")
    assert post(f"{base_url}/api/demo/menu", {}) == (202, {"menu": True})  # the backend then stops with exit code 3


def test_starta_om_demo_stops_with_its_own_code(base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert post(f"{base_url}/api/demo/restart", {}, token=None)[0] == 403
    monkeypatch.delenv("TECHSEED_DEMO_RESTART_EXIT", raising=False)
    status, body = post(f"{base_url}/api/demo/restart", {})
    assert status == 409 and body["error"] == "no_demo_restart"
    monkeypatch.setenv("TECHSEED_DEMO_RESTART_EXIT", "4")
    assert post(f"{base_url}/api/demo/restart", {}) == (202, {"restart": True})  # the backend then stops with exit code 4


def test_the_ticked_base_maps_are_shared_and_reset() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["base_maps"] is None  # the screens' default
    assert scenario.command("base_maps", target="online,offline")["status"]["base_maps"] == ["online", "offline"]
    assert scenario.command("base_maps", target="")["status"]["base_maps"] == []
    with pytest.raises(CommandError):
        scenario.command("base_maps", target="Offline")
    assert scenario.command("reset")["status"]["base_maps"] is None


def test_the_camera_requests_are_counted_so_screens_fly_only_on_a_new_one() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["camera"] == {"target": None, "seq": 0}
    assert scenario.command("camera", target="incident")["status"]["camera"] == {"target": "incident", "seq": 1}
    assert scenario.command("camera", target="incident")["status"]["camera"] == {"target": "incident", "seq": 2}
    assert scenario.command("camera", target="home")["status"]["camera"] == {"target": "home", "seq": 3}
    with pytest.raises(CommandError):
        scenario.command("camera", target="moon")
    assert scenario.snapshot()["events"] == []  # a camera move, not an event with a banner


def test_map_layers_are_switched_by_name_for_every_screen_and_reset() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["map_layers"] == {}  # each map as it starts
    scenario.command("map_layer_on", target="Terräng (OSM)")
    assert scenario.command("map_layer_off", target="Vind (ERA5-Land)")["status"]["map_layers"] == {"Terräng (OSM)": True, "Vind (ERA5-Land)": False}
    with pytest.raises(CommandError):
        scenario.command("map_layer_on", target=None)
    assert scenario.snapshot()["events"] == []
    assert scenario.command("reset")["status"]["map_layers"] == {}


def test_the_panel_s_choices_are_shared_and_reset() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["choices"] == {}
    scenario.command("choose", target="horizon=12")
    assert scenario.command("choose", target="hydro_station=2176:3")["status"]["choices"] == {"horizon": "12", "hydro_station": "2176:3"}
    for target in [None, "horizon", "=12", "horizon=1 2", "Horizon=12"]:
        with pytest.raises(CommandError):
            scenario.command("choose", target=target)
    assert scenario.snapshot()["events"] == []
    assert scenario.command("reset")["status"]["choices"] == {}


def test_a_question_is_put_to_every_screen_counted_and_cleared() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["question"] == {"id": None, "seq": 0}
    assert scenario.command("ask", target="why_fire")["status"]["question"] == {"id": "why_fire", "seq": 1}
    assert scenario.command("ask", target="why_fire")["status"]["question"] == {"id": "why_fire", "seq": 2}  # asked again: anew
    assert scenario.command("clear_answer")["status"]["question"] == {"id": None, "seq": 3}
    scenario.command("ask", target="near_overflow")
    assert scenario.command("reset")["status"]["question"] == {"id": None, "seq": 5}
    with pytest.raises(CommandError):
        scenario.command("ask", target="Why?")
    assert scenario.snapshot()["events"] == []


def test_the_playback_s_length_counts_the_slow_windows() -> None:
    scenario, _ = engine()
    state = scenario.snapshot()
    start, end = (datetime.fromisoformat(state[key].replace("Z", "+00:00")) for key in ("start_utc", "end_utc"))
    plain = (end - start).total_seconds() / state["speed"]
    assert state["playback_seconds"] >= round(plain)
    scenario.set_slow_windows([(start + timedelta(hours=1), start + timedelta(hours=2))])
    slowed = scenario.snapshot()["playback_seconds"]
    expected = plain - 3600 / state["speed"] + 3600 / min(state["speed"], 60.0)
    assert slowed == round(expected) or state["speed"] <= 60


def test_the_main_screen_s_view_is_chosen_from_mission_control_and_kept_by_reset() -> None:
    scenario, _ = engine()
    assert scenario.snapshot()["status"]["view"] is None  # not chosen: every screen stays where it was opened
    assert scenario.command("view", target="2d")["status"]["view"] == "2d"
    assert scenario.command("reset")["status"]["view"] == "2d"  # RESET keeps it, like the speed
    with pytest.raises(CommandError):
        scenario.command("view", target="4d")
