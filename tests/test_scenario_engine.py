"""Tests for the shared scenario clock and its HTTP interface."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app.backend import lantmateriet, server
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


def test_invalid_commands_are_refused() -> None:
    scenario, _ = engine()

    for name, kwargs in [("dance", {}), ("seek", {}), ("seek", {"at": "soon"}), ("speed", {"speed": 5})]:
        with pytest.raises(CommandError):
            scenario.command(name, **kwargs)


def test_events_are_stored_with_the_scenario_time_and_add_up_to_a_status() -> None:
    scenario, fake = engine()

    assert scenario.snapshot()["status"] == {
        "satcom_up": True, "plus60": False, "god_view": False, "power_failure": False,
        "failed_sensors": [], "closed_roads": [],
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
        "satcom_up": False, "plus60": True, "god_view": True, "power_failure": False,
        "failed_sensors": ["sensor-17"], "closed_roads": ["road-66"],
    }
    # Toggles switch back, and SATCOM can be restored.
    scenario.command("plus60")
    scenario.command("satcom_restore")
    status = scenario.command("power_failure")["status"]
    assert status["satcom_up"] and not status["plus60"] and status["god_view"] and status["power_failure"]


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
    late = first_events(f"{base_url}/api/scenario/stream", 2)
    assert late[0][0] == "sync" and late[0][1]["state"]["status"]["failed_sensors"] == ["sensor-17"]
    assert late[1][0] == "state"


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
