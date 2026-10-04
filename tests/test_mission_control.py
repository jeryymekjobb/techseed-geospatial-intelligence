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
from app.backend.scenario_engine import EVENT_KINDS

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
CLOCK_COMMANDS = {"play", "pause", "reset"}


def test_the_buttons_send_only_commands_the_engine_knows() -> None:
    html = (FRONTEND / "control.html").read_text(encoding="utf-8")
    commands = set(re.findall(r'data-command="(\w+)"', html)) | set(re.findall(r'data-toggle-off="(\w+)"', html))
    assert commands == set(EVENT_KINDS) | CLOCK_COMMANDS
    for target in re.findall(r'data-target="([^"]+)"', html):
        assert re.fullmatch(r"[a-z0-9_-]{1,64}", target)


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


def node(expression: str) -> object:
    code = (
        f"const events = require({json.dumps(str(FRONTEND / 'scenario_events.js'))});"
        f"with (events) {{ console.log(JSON.stringify({expression})); }}"
    )
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


QUIET = {"satcom_up": True, "plus60": False, "god_view": False, "power_failure": False, "failed_sensors": [], "closed_roads": [],
         "satcom_down_since": None, "last_outage": None}


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
