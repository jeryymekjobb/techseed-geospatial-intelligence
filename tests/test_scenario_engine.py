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
