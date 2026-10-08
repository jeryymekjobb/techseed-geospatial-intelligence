#!/usr/bin/env python3
"""Run the two-minute demo from mission control and report each step, for the exhibition PC.

Opens the 3D main screen, the satellite monitor and mission control in Chrome,
drives the demo in the operator guide's order - the flight to the fire, SPACE
VIEW, the detection sequence with NEXT, detections with Landsat and IoT, the IoT
switch, the assessment and questions, +60 MIN, a SATCOM outage with SYNC, GOD
VIEW with its filter - and checks that RESET brings the screens back within
5 seconds. It also measures the frame rate of the 3D view during playback.
With TECHSEED_SCENARIO=sundsvall2026 or skane2024 it runs the flood's manuscript instead:
the rain, the synthetic overflow or level sensors, the detection sequence from a Sentinel-1
acquisition, the flood assessment and questions, and a SATCOM outage that holds satellite
images back (with the tiles service serving the scenario's map and its database loaded).
What it expects - the place, the satellites, the sensors and the outcome - comes from the
scenario (its CHECK_ values).

Without --base-url it starts the backend and the simulated booth nodes itself
(with the local services of docker-compose.yml running); with --base-url it
checks a backend that already runs. --headed shows a normal browser window with
the real graphics card; headless Chrome renders WebGL in software, so its times
say little about the exhibition PC. Needs Playwright in .venv
(tools/requirements-record.txt) and Google Chrome.

    .venv/bin/python -m tools.check_demo --headed --out ~/demo-check
    TECHSEED_SCENARIO=sundsvall2026 .venv/bin/python -m tools.check_demo --headed --out ~/demo-check-sundsvall
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.backend import offline_tiles, scenario
from tools import open_screens

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
# Where the check starts on the scenario clock (for Västmanland a satellite pass and the Landsat scene follow within minutes).
START_UTC = scenario.CHECK_START_UTC
RESET_LIMIT_S = 5.0
# Below this the camera and satellites feel jerky. A rule of thumb, not measured at the
# exhibition, so a lower rate gives a warning and does not fail the check.
DEFAULT_MIN_FPS = 20.0
WAIT_MS = 60000
# Headless Chrome has no GPU; these flags give it WebGL in software, so the 3D view can start.
SOFTWARE_WEBGL = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
# The main screen and mission control are separate windows, as in the booth; Chrome must
# not pause or slow down the one that is not in front.
KEEP_BOTH_RUNNING = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                     "--disable-backgrounding-occluded-windows"]
# Conditions are polled at a fixed interval, not on animation frames.
POLL_MS = 100


@dataclass
class Step:
    name: str
    verdict: str
    detail: str
    seconds: float


@dataclass
class Report:
    base_url: str
    headed: bool
    started_utc: str
    computer: str = field(default_factory=platform.node)
    steps: list[Step] = field(default_factory=list)
    frames_per_second: float | None = None
    webgl_renderer: str | None = None
    canvas_px: str | None = None
    min_fps: float = DEFAULT_MIN_FPS
    javascript_errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.steps) and all(step.verdict == "GODKÄND" for step in self.steps) and not self.javascript_errors

    def skip_rest(self, names: list[str]) -> None:
        """After a failure the later steps would only time out; they are listed as not run."""
        self.steps += [Step(name, "EJ KÖRD", "ett tidigare steg misslyckades", 0.0) for name in names]

    def text(self) -> str:
        lines = [f"Demokontroll {self.started_utc} på {self.computer} mot {self.base_url} "
                 f"({'synligt fönster' if self.headed else 'headless'})"]
        lines.append(f"Grafik (WebGL i Chrome): {self.webgl_renderer or 'okänd'}; 3D-ytan {self.canvas_px or 'okänd'} pixlar")
        lines += [f"{step.verdict:9} {step.name} ({step.seconds:.1f} s): {step.detail}" for step in self.steps]
        fps = "ej mätt" if self.frames_per_second is None else f"{self.frames_per_second:.1f}"
        lines.append(f"Bilder per sekund i 3D under uppspelning: {fps}")
        if self.frames_per_second is not None and self.frames_per_second < self.min_fps:
            lines.append(f"VARNING: under {self.min_fps:.0f} bilder per sekund – kameran och satelliterna blir ryckiga")
        lines.append("JavaScript-fel: " + ("; ".join(self.javascript_errors) if self.javascript_errors else "inga"))
        lines.append("RESULTAT: " + ("GODKÄND" if self.passed else "UNDERKÄND"))
        return "\n".join(lines)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def backend_command(port: int) -> list[str]:
    return [str(PYTHON), "-m", "app.backend.server", "--port", str(port)]


def wait_for(url: str, seconds: float = 60.0) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=5):
                return
        except (URLError, ConnectionError, OSError):
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not answer within {seconds:.0f} s")


def screen_places() -> dict[str, open_screens.Window]:
    """Where tools/open_screens.py puts each screen on this computer's monitors; empty without xrandr."""
    try:
        listing = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True, check=False).stdout
        prop = subprocess.run(["xprop", "-root", "_GTK_WORKAREAS_D0"], capture_output=True, text=True, check=False).stdout
    except OSError:
        return {}
    found = open_screens.monitors(listing)
    if not found:
        return {}
    return {window.screen: window for window in open_screens.layout(open_screens.within_work_areas(found, open_screens.work_areas(prop)))}


def bounds(window: open_screens.Window) -> dict[str, Any]:
    """The window's place for Chrome's Browser.setWindowBounds."""
    return {"left": window.x, "top": window.y, "width": window.width, "height": window.height}


class Demo:
    """The browser pages and the commands the steps use. In a visible window (`places` given, from
    screen_places()) each screen is put where tools/open_screens.py puts it and fills its window,
    as at the exhibition; headless they have fixed sizes."""

    def __init__(self, browser: Any, base_url: str, out: Path, errors: list[str],
                 places: dict[str, open_screens.Window] | None = None) -> None:
        self.base_url, self.out = base_url, out
        places = places or {}
        sizes = {"main": (1600, 900), "control": (1024, 900), "monitor": (1200, 900)}

        def page_for(screen: str) -> Any:
            # One browser context each: separate windows, all active.
            if screen not in places:
                width, height = sizes[screen]
                return browser.new_context(viewport={"width": width, "height": height}).new_page()
            page = browser.new_context(no_viewport=True).new_page()
            session = page.context.new_cdp_session(page)
            window_id = session.send("Browser.getWindowForTarget")["windowId"]
            session.send("Browser.setWindowBounds", {"windowId": window_id, "bounds": {"windowState": "normal"}})
            session.send("Browser.setWindowBounds", {"windowId": window_id, "bounds": bounds(places[screen])})
            return page

        self.monitor = page_for("monitor")
        self.main = page_for("main")
        self.control = page_for("control")
        for name, page in [("huvudskärm", self.main), ("mission control", self.control), ("satellitbevakning", self.monitor)]:
            page.on("pageerror", lambda exc, name=name: errors.append(f"{name}: {exc}"))
            page.on("console", lambda msg, name=name: errors.append(f"{name}: {msg.text}") if msg.type == "error" else None)

    def button(self, label: str) -> Any:
        return self.control.get_by_role("button", name=label, exact=True)

    def command(self, body: dict[str, Any]) -> None:
        request = Request(f"{self.base_url}/api/scenario/command", data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        urlopen(request, timeout=10).close()

    def text(self, element_id: str) -> str:
        return self.main.inner_text(f"#{element_id}")

    def shot(self, name: str) -> None:
        self.main.screenshot(path=str(self.out / f"{name}.png"))


def served_tiles_file(template: str) -> str | None:
    """The file the tiles service (tileserver-gl) serves, from its data.json; None when it does not answer."""
    parts = urlsplit(template)
    try:
        with urlopen(f"{parts.scheme}://{parts.netloc}/data.json", timeout=5) as response:
            sources = json.loads(response.read())
    except (URLError, OSError, ValueError):
        return None
    return sources[0].get("basename") if sources else None


def opening(demo: Demo) -> str:
    # The offline map must be the scenario's: another file gives an empty map round the incident.
    served = served_tiles_file(offline_tiles.url_template())
    if served is None:
        raise RuntimeError("kartjänsten svarar inte – kör docker compose up -d tiles")
    if served != scenario.TILES_FILE:
        raise RuntimeError(f"kartjänsten visar {served}, scenariot behöver {scenario.TILES_FILE} – "
                           f"kör TILES_FILE={scenario.TILES_FILE} docker compose up -d tiles")
    # A playback left running would pass 11:48 during the flight, before step 2 waits for it.
    demo.command({"command": "pause"})
    demo.main.goto(f"{demo.base_url}/3d.html?at={START_UTC}&fly=1")
    try:
        demo.main.wait_for_selector("body[data-ready=true]", timeout=WAIT_MS)
    except Exception as exc:
        # The page says why it did not start, for example that WebGL is missing.
        raise RuntimeError(f"sidan startade inte: {demo.text('stream-status') or 'ingen statustext'}") from exc
    demo.main.wait_for_selector("body[data-flight=arrived]", timeout=WAIT_MS)
    demo.control.goto(f"{demo.base_url}/control.html")
    demo.monitor.goto(f"{demo.base_url}/monitor.html")
    demo.control.wait_for_function("document.getElementById('scenario-status').children.length > 0", timeout=WAIT_MS, polling=POLL_MS)
    if not scenario.WILDFIRE:
        demo.main.wait_for_function("document.getElementById('rain-values').textContent.includes('Senaste timmen')", timeout=WAIT_MS, polling=POLL_MS)
    demo.shot("1-opening")
    shown = demo.text('counts') if scenario.WILDFIRE else 'regnet visas: ' + demo.text('rain-values').replace(chr(10), ' ')
    # The flood maps come from services outside the demo: a silent one is reported, not failed.
    with urlopen(f"{demo.base_url}/api/config", timeout=10) as response:
        silent = [source["attribution"] for source in json.loads(response.read())["layers"].get("wms") or [] if not source["available"]]
    warning = f"; VARNING: svarar inte: {', '.join(silent)}" if silent else ""
    return f"kameraresan klar; karta {served}; {shown}{warning}"


def space_view(demo: Demo) -> str:
    demo.button("SPACE VIEW").click()
    demo.command({"command": "speed", "speed": 60})
    before = demo.text("counts")
    demo.button("PLAY").click()
    demo.main.wait_for_function("document.getElementById('satellite-list').children.length >= 5", timeout=WAIT_MS, polling=POLL_MS)
    # The VIIRS pass at 09:48 brings new detections about 18 s into the playback.
    demo.main.wait_for_function(f"document.getElementById('counts').textContent !== {json.dumps(before)}", timeout=WAIT_MS, polling=POLL_MS)
    demo.shot("2-space-view")
    after = demo.text("counts")
    demo.button("SPACE VIEW").click()
    demo.main.wait_for_function("!document.getElementById('satellite-section').classList.contains('space-view')", timeout=WAIT_MS, polling=POLL_MS)
    return f"{before} -> {after}"


def detection_sequence(demo: Demo) -> str:
    demo.button("SATELLITE DETECTION").click()
    demo.control.wait_for_function("document.getElementById('detection-step').textContent.startsWith('Steg 1/6')", timeout=WAIT_MS, polling=POLL_MS)
    demo.main.wait_for_function("!document.getElementById('detection-card').hidden", timeout=WAIT_MS, polling=POLL_MS)
    demo.monitor.wait_for_function("Boolean(document.body.dataset.mark)", timeout=WAIT_MS, polling=POLL_MS)
    passed = demo.text("detection-pass")
    demo.shot("3-detection-acquired")
    for step in range(2, 7):
        demo.button("NÄSTA ▸").click()
        demo.control.wait_for_function(f"document.getElementById('detection-step').textContent.startsWith('Steg {step}/6')",
                                       timeout=WAIT_MS, polling=POLL_MS)
    demo.main.wait_for_function("!document.getElementById('detection-rules').hidden", timeout=WAIT_MS, polling=POLL_MS)
    outcome = demo.text("detection-outcome")
    rules = demo.main.eval_on_selector_all("#detection-rule-list li", "els => els.length")
    assert outcome == "Vegetationsbrand" and rules == 5, (outcome, rules)
    demo.shot("3-detection-correlate")
    demo.button("NÄSTA ▸").click()
    demo.main.wait_for_function("document.getElementById('detection-card').hidden", timeout=WAIT_MS, polling=POLL_MS)
    demo.monitor.wait_for_function("!document.body.dataset.mark", timeout=WAIT_MS, polling=POLL_MS)
    demo.button("PLAY").click()  # the sequence paused the playback
    return f"{passed}: {outcome}, {rules} regler; kortet och markeringen borta efter sista steget"


def detections(demo: Demo) -> str:
    demo.command({"command": "speed", "speed": 3600})
    image = json.dumps(scenario.CHECK_IMAGE)
    demo.main.wait_for_function(f"document.getElementById('landsat-note').textContent.startsWith({image})", timeout=WAIT_MS, polling=POLL_MS)
    # The playback slows down around the passes, so 14:00 comes within the minute but 15:00 may not.
    demo.main.wait_for_function("document.getElementById('sim-time').textContent.includes(' 14:')", timeout=WAIT_MS, polling=POLL_MS)
    demo.button("PAUSE").click()
    nodes = demo.main.eval_on_selector_all("#real-sensors li", "els => els.map(e => e.textContent)")
    assert len(nodes) == 4 and all("simulerad" in line or "live" in line for line in nodes), nodes
    demo.shot("3-detections")
    return f"{demo.text('sim-time')}; {demo.text('iot-confirms')}; Landsat synlig; {len(nodes)} monternoder"


def iot_switch(demo: Demo) -> str:
    demo.button("IOT PÅ/AV").click()
    demo.main.wait_for_function("document.getElementById('real-sensors').textContent.includes('IoT avstängt')", timeout=WAIT_MS, polling=POLL_MS)
    off = demo.text("iot-confirms")
    demo.button("IOT PÅ/AV").click()
    demo.main.wait_for_function("document.querySelectorAll('#real-sensors li').length === 4", timeout=WAIT_MS, polling=POLL_MS)
    return f"av: {off}; på igen med 4 monternoder"


def assessment(demo: Demo) -> str:
    outcome = demo.text("assessment-outcome")
    demo.control.get_by_role("button", name="Why do you believe there is a fire?").click()
    # The answer starts with the assessment's outcome.
    demo.main.wait_for_function(f"document.getElementById('answer-text').textContent.startsWith({json.dumps(outcome)})",
                                timeout=WAIT_MS, polling=POLL_MS)
    demo.control.get_by_role("button", name="Show infrastructure within 5 km of the incident").click()
    demo.main.wait_for_function("document.getElementById('answer-text').textContent.startsWith('Inom 5 km')", timeout=WAIT_MS, polling=POLL_MS)
    assert outcome == scenario.CHECK_OUTCOME, outcome
    demo.shot("4-assessment")
    return f"{outcome}; {demo.text('answer-text')[:80]}"


def plus60(demo: Demo) -> str:
    demo.button("+60 MIN").click()
    demo.main.wait_for_function("document.getElementById('forecast-horizon').value === '3'", timeout=WAIT_MS, polling=POLL_MS)
    demo.button("+60 MIN").click()
    demo.main.wait_for_function("document.getElementById('forecast-horizon').value !== '3'", timeout=WAIT_MS, polling=POLL_MS)
    return "horisonten 3 h och tillbaka"


def satcom(demo: Demo) -> str:
    before = demo.text("counts")
    demo.command({"command": "speed", "speed": 3600})  # detections come within seconds at 1 hour/s
    demo.button("SATCOM FAILURE").click()
    demo.button("PLAY").click()
    demo.main.wait_for_function("/ [1-9][0-9]* detektioner köade/.test(document.getElementById('satcom-queue').textContent)", timeout=WAIT_MS, polling=POLL_MS)
    demo.button("PAUSE").click()
    queue, during = demo.text("satcom-queue"), demo.text("counts")
    assert during == before, (before, during)
    demo.button("SATCOM FAILURE").click()
    demo.main.wait_for_function("document.getElementById('satcom-sync').children.length > 0", timeout=WAIT_MS, polling=POLL_MS)
    demo.shot("6-sync")
    return f"{queue}; efter SYNC {demo.text('counts')}"


def god_view(demo: Demo) -> str:
    demo.button("GOD VIEW").click()
    # The filter's categories are rows in mission control's box of map layers.
    demo.control.uncheck("#map-layers input[data-category=weather]")
    demo.main.wait_for_function("!document.getElementById('god-filter').hidden"
                                " && document.getElementById('god-filter').textContent.includes('☐ Weather')", timeout=WAIT_MS, polling=POLL_MS)
    demo.shot("7-god-view")
    demo.button("GOD VIEW").click()
    demo.main.wait_for_function("document.getElementById('god-filter').hidden", timeout=WAIT_MS, polling=POLL_MS)
    return "filterlistan visades, Weather dold"


def reset(demo: Demo) -> str:
    pressed = time.time()
    demo.button("RESET").click()
    demo.main.wait_for_function("""() => document.getElementById('counts').textContent.startsWith('0 ')
        && document.getElementById('scenario-status').textContent.includes('Inga händelser')
        && document.getElementById('god-filter').hidden
        && document.getElementById('satcom-queue').textContent === ''
        && document.getElementById('detection-card').hidden""", timeout=WAIT_MS, polling=50)
    main_ready = time.time() - pressed
    demo.control.wait_for_function("document.getElementById('event-log').children.length === 0", timeout=WAIT_MS, polling=50)
    both_ready = time.time() - pressed
    demo.shot("8-reset")
    assert both_ready <= RESET_LIMIT_S, f"{both_ready:.2f} s, kravet är {RESET_LIMIT_S:.0f} s"
    return f"huvudskärmen {main_ready:.2f} s, båda skärmarna {both_ready:.2f} s"


# The flood (scenarios sundsvall2026 and skane2024): the same screens with its rain, sensors and questions.


def flood_space_view(demo: Demo) -> str:
    demo.button("SPACE VIEW").click()
    demo.command({"command": "speed", "speed": 60})
    demo.button("PLAY").click()
    demo.main.wait_for_function(f"document.getElementById('satellite-list').children.length >= {len(scenario.TLE_SATELLITES)}",
                                timeout=WAIT_MS, polling=POLL_MS)
    demo.main.wait_for_function("document.getElementById('satellite-section').classList.contains('space-view')", timeout=WAIT_MS, polling=POLL_MS)
    demo.shot("2-space-view")
    demo.button("PAUSE").click()
    demo.button("SPACE VIEW").click()
    demo.main.wait_for_function("!document.getElementById('satellite-section').classList.contains('space-view')", timeout=WAIT_MS, polling=POLL_MS)
    return f"{demo.main.eval_on_selector_all('#satellite-list li', 'els => els.length')} satelliter i listan"


def flood_detection_sequence(demo: Demo) -> str:
    demo.button("SATELLITE DETECTION").click()
    demo.control.wait_for_function("document.getElementById('detection-step').textContent.startsWith('Steg 1/6')", timeout=WAIT_MS, polling=POLL_MS)
    demo.main.wait_for_function("!document.getElementById('detection-card').hidden", timeout=WAIT_MS, polling=POLL_MS)
    demo.monitor.wait_for_function("Boolean(document.body.dataset.mark)", timeout=WAIT_MS, polling=POLL_MS)
    passed = demo.text("detection-pass")
    assert passed.startswith("SAR ·"), passed
    for step in range(2, 7):
        demo.button("NÄSTA ▸").click()
        demo.control.wait_for_function(f"document.getElementById('detection-step').textContent.startsWith('Steg {step}/6')",
                                       timeout=WAIT_MS, polling=POLL_MS)
    demo.main.wait_for_function("!document.getElementById('detection-rules').hidden", timeout=WAIT_MS, polling=POLL_MS)
    outcome = demo.text("detection-outcome")
    rules = demo.main.eval_on_selector_all("#detection-rule-list li", "els => els.length")
    assert outcome == "Översvämning trolig" and rules == 4, (outcome, rules)
    demo.shot("3-detection-correlate")
    demo.button("NÄSTA ▸").click()
    demo.main.wait_for_function("document.getElementById('detection-card').hidden", timeout=WAIT_MS, polling=POLL_MS)
    demo.monitor.wait_for_function("!document.body.dataset.mark", timeout=WAIT_MS, polling=POLL_MS)
    return f"{passed}: {outcome}, {rules} regler; kortet och markeringen borta efter sista steget"


def flood_rain_and_sensors(demo: Demo) -> str:
    demo.command({"command": "seek", "at": scenario.CHECK_PEAK_UTC})
    demo.main.wait_for_function(f"document.getElementById('iot-confirms').textContent.startsWith('IoT bekräftar {scenario.CHECK_SENSORS}')",
                                timeout=WAIT_MS, polling=POLL_MS)
    nodes = demo.main.eval_on_selector_all("#real-sensors li", "els => els.map(e => e.textContent)")
    assert len(nodes) == 4 and all("simulerad" in line or "live" in line for line in nodes), nodes
    demo.shot("4-rain")
    return f"{demo.text('sim-time')}; {demo.text('rain-values').replace(chr(10), ' ')}; {demo.text('iot-confirms')}; {len(nodes)} monternoder"


def flood_assessment(demo: Demo) -> str:
    from app.backend import spatial

    outcome = json.dumps(scenario.CHECK_OUTCOME)
    demo.main.wait_for_function(f"document.getElementById('assessment-outcome').textContent === {outcome}", timeout=WAIT_MS, polling=POLL_MS)
    demo.control.get_by_role("button", name="Why do you believe there is a flood?").click()
    demo.main.wait_for_function(f"document.getElementById('answer-text').textContent.startsWith({outcome})", timeout=WAIT_MS, polling=POLL_MS)
    demo.control.get_by_role("button", name=spatial.QUESTIONS["buildings_100y"]["question"]).click()
    within = json.dumps(f"byggnader inom {scenario.FLOOD_AREA_WORD}")
    demo.main.wait_for_function(f"document.getElementById('answer-text').textContent.includes({within})", timeout=WAIT_MS, polling=POLL_MS)
    demo.shot("5-assessment")
    return f"{demo.text('assessment-outcome')}; {demo.text('answer-text')[:80]}"


def flood_satcom(demo: Demo) -> str:
    # From the scenario's evening, so only the clock's slow-down round the next radar acquisition lies before it.
    demo.command({"command": "seek", "at": scenario.CHECK_SATCOM_UTC})
    demo.command({"command": "speed", "speed": 10800})
    demo.button("SATCOM FAILURE").click()
    demo.button("PLAY").click()
    demo.main.wait_for_function("/ [1-9][0-9]* satellitbild(er)? köade/.test(document.getElementById('satcom-queue').textContent)", timeout=WAIT_MS, polling=POLL_MS)
    demo.button("PAUSE").click()
    queue = demo.text("satcom-queue")
    demo.button("SATCOM FAILURE").click()
    demo.main.wait_for_function("document.getElementById('satcom-sync').textContent.includes('radarbild')", timeout=WAIT_MS, polling=POLL_MS)
    demo.shot("6-sync")
    return f"{queue}; SYNC: {demo.text('satcom-sync').splitlines()[0]}"


WEBGL_RENDERER = """() => {
  const gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl");
  if (!gl) return null;
  const info = gl.getExtension("WEBGL_debug_renderer_info");
  return info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
}"""


CANVAS_SIZE = """() => {
  const canvas = document.querySelector("#map canvas");
  return canvas ? `${canvas.width}x${canvas.height}` : null;
}"""


FIRE_STEPS: list[tuple[str, Callable[[Demo], str]]] = [
    ("1 Öppning: jorden till branden", opening),
    ("2 SPACE VIEW och RETURN TO INCIDENT", space_view),
    ("3 SATELLITE DETECTION och NÄSTA", detection_sequence),
    ("4 Detektioner, Landsat och IoT", detections),
    ("5 IOT PÅ/AV", iot_switch),
    ("6 Bedömning och frågor", assessment),
    ("7 +60 MIN", plus60),
    ("8 SATCOM FAILURE och SYNC", satcom),
    ("9 GOD VIEW med filter", god_view),
    ("10 RESET inom 5 s", reset),
]
FLOOD_STEPS: list[tuple[str, Callable[[Demo], str]]] = [
    (f"1 Öppning: jorden till {scenario.INCIDENT_PLACE}", opening),
    ("2 SPACE VIEW och RETURN TO INCIDENT", flood_space_view),
    ("3 SATELLITE DETECTION och NÄSTA", flood_detection_sequence),
    (f"4 Regn och {scenario.SENSOR_WORDS['sensors']}", flood_rain_and_sensors),
    ("5 IOT PÅ/AV", iot_switch),
    ("6 Bedömning och frågor", flood_assessment),
    ("7 SATCOM FAILURE och SYNC", flood_satcom),
    ("8 GOD VIEW med filter", god_view),
    ("9 RESET inom 5 s", reset),
]
# The manuscript of the scenario chosen by TECHSEED_SCENARIO (the backend it starts gets the same).
STEPS = FIRE_STEPS if scenario.WILDFIRE else FLOOD_STEPS


def frames_per_second(demo: Demo, seconds: float = 3.0) -> float:
    """Animation frames the 3D view draws per second while the scenario plays at 1 minute/s."""
    demo.main.bring_to_front()
    demo.command({"command": "speed", "speed": 60})
    demo.command({"command": "play"})
    try:
        return demo.main.evaluate("""(ms) => new Promise((resolve) => {
          let frames = 0; const start = performance.now();
          const tick = (now) => { frames += 1; if (now - start < ms) requestAnimationFrame(tick); else resolve(frames * 1000 / (now - start)); };
          requestAnimationFrame(tick);
        })""", seconds * 1000)
    finally:
        demo.command({"command": "pause"})
        demo.command({"command": "speed", "speed": 3600})  # back to the demo's speed


def run(base_url: str, out: Path, headed: bool, min_fps: float = DEFAULT_MIN_FPS) -> Report:
    from playwright.sync_api import sync_playwright

    report = Report(base_url, headed, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), min_fps=min_fps)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        args = KEEP_BOTH_RUNNING + ([] if headed else SOFTWARE_WEBGL)
        browser = playwright.chromium.launch(channel="chrome", headless=not headed, args=args)
        places = screen_places() if headed else {}
        if headed and not places:
            print("Fönstren kunde inte placeras (xrandr hittade inga skärmar); de öppnas där Chrome vill.")
        demo = Demo(browser, base_url, out, report.javascript_errors, places)
        for index, (name, action) in enumerate(STEPS):
            started = time.time()
            try:
                report.steps.append(Step(name, "GODKÄND", action(demo), time.time() - started))
            except Exception as exc:  # noqa: BLE001 - every failure belongs in the report
                detail = f"{type(exc).__name__}: {exc}".split("\nCall log:")[0]
                report.steps.append(Step(name, "UNDERKÄND", detail[:300], time.time() - started))
                report.skip_rest([later for later, _ in STEPS[index + 1:]])
                break
            if index == 0:
                try:
                    report.webgl_renderer = demo.main.evaluate(WEBGL_RENDERER)
                    report.canvas_px = demo.main.evaluate(CANVAS_SIZE)
                except Exception:  # noqa: BLE001 - the renderer is information only
                    report.webgl_renderer = None
            if action in (detections, flood_rain_and_sensors):  # after the step the playback runs in
                try:
                    report.frames_per_second = frames_per_second(demo)
                except Exception:  # noqa: BLE001 - the measurement is optional
                    report.frames_per_second = None
        browser.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base-url", help="check a backend that already runs, for example http://127.0.0.1:8765")
    parser.add_argument("--headed", action="store_true", help="show the browser window (real graphics)")
    parser.add_argument("--out", type=Path, default=Path("demo-check"), help="directory for the report and screenshots")
    parser.add_argument("--min-fps", type=float, default=DEFAULT_MIN_FPS, help="warn below this 3D frame rate")
    args = parser.parse_args(argv)
    processes: list[subprocess.Popen[bytes]] = []
    try:
        base_url = args.base_url
        if not base_url:
            port = free_port()
            base_url = f"http://127.0.0.1:{port}"
            processes.append(subprocess.Popen(backend_command(port), cwd=REPO_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            processes.append(subprocess.Popen([str(PYTHON), "-m", "tools.mqtt_node_sim", "--interval", "2"], cwd=REPO_ROOT,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait_for(f"{base_url}/api/config")
        report = run(base_url.rstrip("/"), args.out, args.headed, args.min_fps)
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
    text = report.text()
    print(text)
    (args.out / "report.txt").write_text(text + "\n", encoding="utf-8")
    (args.out / "report.json").write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
