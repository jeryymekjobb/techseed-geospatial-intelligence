#!/usr/bin/env python3
"""Start the demos for the day: a menu of demos, then the chosen one, and back to the menu.

    .venv/bin/python -m tools.start_demo                    # the menu on the three screens
    .venv/bin/python -m tools.start_demo sundsvall2026      # straight to a demo

Without a name only mission control's window opens (tools/open_screens.py --menu), with
the menu "Techseed Geospatial Intelligence Demos" served here on the backend's port; the
other screens open once a demo is chosen. A click on a demo starts it, in order: the docker-compose.yml services with the scenario's map
tiles (it waits until the tiles service serves them), the backend for the scenario,
the simulated booth nodes (their lines go to data/node-sim.log) and the screens in
their places, at the scenario's starting time (or --at, with a name). BYT DEMO in
mission control stops the backend with MENU_EXIT and the menu comes back. Ctrl+C
stops the backend and the nodes; the screens and the services stay.

It stops at once when something already answers on the backend's port, such as a
backend left running, rather than start a second one.
"""

from __future__ import annotations

import argparse
import importlib
import os
import json
import socket
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from app.backend import offline_tiles
from app.backend.scenarios import AVAILABLE
from tools.check_demo import served_tiles_file

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
NODE_LOG = REPO_ROOT / "data" / "node-sim.log"
FRONTEND = REPO_ROOT / "app" / "frontend"
PORT = 8765
MENU_EXIT = 3  # the backend's exit code for BYT DEMO (TECHSEED_DEMO_MENU_EXIT)
MENU_TITLE = "Techseed Geospatial Intelligence Demos"


def scenario_settings(name: str) -> tuple[str, str]:
    """The scenario's map tiles file and playback start, without choosing it here."""
    module = importlib.import_module(f"app.backend.scenarios.{name}")
    return module.TILES_FILE, module.PLAYBACK_START.strftime("%Y-%m-%dT%H:%M:%SZ")


def demos() -> list[dict[str, str]]:
    """The menu's demos: each scenario's name, title and data label."""
    found = []
    for name in AVAILABLE:
        module = importlib.import_module(f"app.backend.scenarios.{name}")
        found.append({"name": name, "title": module.TITLE, "label": module.DATA_LABEL})
    return found


class MenuHandler(BaseHTTPRequestHandler):
    """The menu page (app/frontend/menu.html), the demos, and the choice of one."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the base class's name
        pass

    def send_body(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the demo's old pages ask for its API until their windows are replaced, and hang up

    def send_json(self, status: HTTPStatus, data: object) -> None:
        self.send_body(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        path = self.path.split("?", 1)[0]
        if path == "/api/demos":
            self.send_json(HTTPStatus.OK, {"title": MENU_TITLE, "demos": demos()})
        elif path == "/styles.css":
            self.send_body(HTTPStatus.OK, (FRONTEND / "styles.css").read_bytes(), "text/css; charset=utf-8")
        elif path in ("/", "/menu.html"):
            self.send_body(HTTPStatus.OK, (FRONTEND / "menu.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        if self.path != "/api/demo/start":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            name = json.loads(self.rfile.read(min(length, 1024)))["scenario"] if 0 < length <= 1024 else None
        except (ValueError, KeyError, TypeError):
            name = None
        if name not in AVAILABLE or self.server.chosen:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_demo"})
            return
        self.server.chosen = name
        self.send_json(HTTPStatus.ACCEPTED, {"scenario": name})
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def menu_server(port: int = PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), MenuHandler)
    server.daemon_threads = True
    server.chosen = None
    return server


def choose_demo() -> str:
    """Show the menu in mission control's window until a demo is chosen; its name."""
    server = menu_server()
    print(f"Menyn: {MENU_TITLE} i mission control – välj en demo (Ctrl+C avslutar).", flush=True)
    subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--menu", "--base-url", f"http://127.0.0.1:{PORT}"],
                   cwd=REPO_ROOT, check=False)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return server.chosen


def services_command() -> list[str]:
    return ["docker", "compose", "up", "-d", "tiles", "postgis", "mosquitto"]


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as probe:
        probe.settimeout(1.0)
        return probe.connect_ex((host, port)) == 0


def wait_until(check, seconds: float, what: str) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if check():
            return
        time.sleep(1.0)
    raise SystemExit(f"start_demo: {what} within {seconds:.0f} s")


def answers(url: str) -> bool:
    try:
        with urlopen(url, timeout=5):
            return True
    except (URLError, OSError):
        return False


def run_demo(name: str, at: str | None) -> int:
    """Start a demo and run it until the backend stops; its exit code (MENU_EXIT for BYT DEMO), 0 after Ctrl+C."""
    tiles, start = scenario_settings(name)
    base_url = f"http://127.0.0.1:{PORT}"
    print(f"1/4 Tjänsterna, med kartan {tiles} …", flush=True)
    subprocess.run(services_command(), cwd=REPO_ROOT, env={**os.environ, "TILES_FILE": tiles}, check=True)
    wait_until(lambda: served_tiles_file(offline_tiles.url_template()) == tiles, 90, f"the tiles service did not serve {tiles}")

    print(f"2/4 Backend för {name} …", flush=True)
    env = {**os.environ, "TECHSEED_SCENARIO": name, "TECHSEED_DEMO_MENU_EXIT": str(MENU_EXIT)}
    backend = subprocess.Popen([str(PYTHON), "-m", "app.backend.server", "--scenario", name, "--port", str(PORT)],
                               cwd=REPO_ROOT, env=env)
    nodes = None
    try:
        wait_until(lambda: backend.poll() is not None or answers(f"{base_url}/api/config"), 180, "the backend did not answer")
        if backend.poll() is not None:
            raise SystemExit(f"start_demo: the backend stopped (exit {backend.returncode})")

        print(f"3/4 Sensorerna i montern (simulerade; loggen i {NODE_LOG.relative_to(REPO_ROOT)}) …", flush=True)
        NODE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with NODE_LOG.open("a", encoding="utf-8") as log:
            nodes = subprocess.Popen([str(PYTHON), "-m", "tools.mqtt_node_sim", "--interval", "5"],
                                     cwd=REPO_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)

        print("4/4 Skärmarna …", flush=True)
        subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--base-url", base_url, "--at", at or start],
                       cwd=REPO_ROOT, check=False)
        print(f"Demon går: {name} på {base_url}. BYT DEMO i mission control ger menyn; Ctrl+C stoppar.", flush=True)
        backend.wait()
        if backend.returncode == MENU_EXIT:
            print("BYT DEMO: tillbaka till menyn …", flush=True)
            return MENU_EXIT
        print(f"start_demo: the backend stopped (exit {backend.returncode})")
        return backend.returncode or 1
    except KeyboardInterrupt:
        print("\nStoppar backend och sensorerna …")
        return 0
    finally:
        for process in (nodes, backend):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("scenario", nargs="?", choices=AVAILABLE, help="the demo to start (default: the menu)")
    parser.add_argument("--at", help="the main screen's starting time in UTC, with a demo's name (default: the scenario's)")
    args = parser.parse_args(argv)
    if port_in_use(PORT):
        parser.exit(1, f"start_demo: something already answers on port {PORT} – stop the running backend first (Ctrl+C in its terminal)\n")
    name, at = args.scenario, args.at
    try:
        while True:
            if name is None:
                name, at = choose_demo(), None
            code = run_demo(name, at)
            if code != MENU_EXIT:
                return code
            name = None
    except KeyboardInterrupt:
        print("\nAvslutar.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
