#!/usr/bin/env python3
"""Start the demos for the day: a menu of demos, then the chosen one, and back to the menu.

    .venv/bin/python -m tools.start_demo                    # the menu on the three screens
    .venv/bin/python -m tools.start_demo sundsvall2026      # straight to a demo
    .venv/bin/python -m tools.start_demo --kiosk            # the menu, with kiosk mode on

Without a name only mission control's window opens (tools/open_screens.py --menu), with
the menu "Techseed Geospatial Intelligence Demos" served here on the backend's port; the
other screens open once a demo is chosen. A click on a demo starts it, in order: the docker-compose.yml services with the scenario's map
tiles (it waits until the tiles service serves them), the backend for the scenario,
the simulated booth nodes (their lines go to data/node-sim.log) and the screens in
their places, at the scenario's starting time (or --at, with a name). BYT SCENARIO in
mission control stops the backend with MENU_EXIT and the menu comes back. STARTA OM DEMO
stops it with RESTART_EXIT: the screens close and the same scenario starts again from its
saved start. Ctrl+C stops the backend and the nodes; the screens and the services stay.

KIOSKLÄGE on the menu (or --kiosk) runs the demo without an operator: the backend gets
TECHSEED_DEMO_KIOSK=1 and loops the demo (app/backend/scenario_engine.py): it plays after the
scenario's summary, shows the closing view at the stop and starts again. The choice holds until
start_demo ends, through BYT SCENARIO and STARTA OM DEMO. In kiosk mode start_demo also keeps the
demo up: every WATCH_SECONDS it starts the booth's simulated nodes again if they have stopped and
opens a screen whose window has gone (a new mission control resets the demo, which then starts
from its beginning); a backend that stops by itself, or a demo that fails to start, is started
again after RETRY_SECONDS. Ctrl+C, BYT SCENARIO and STARTA OM DEMO work as without it.

It stops at once when something already answers on the backend's port, such as a
backend left running, rather than start a second one.

Docker remains the default. --services native --node-modules PATH explicitly uses
separately installed Node/TileServer GL and Mosquitto (--node and --mosquitto select
their executables). PostgreSQL/PostGIS must already be running and loaded; native
database options are documented in app/backend/postgres.py. Native map and broker
children are stopped on exit, restart and scenario change; PostgreSQL is untouched.
--browser edge (or TECHSEED_BROWSER=edge) selects Edge for every demo screen and
its restart/menu lifecycle. Without an explicit choice Chrome remains the default.
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
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from app.backend import offline_tiles, profiles
from app.backend.scenarios import AVAILABLE
from tools import open_screens
from tools.check_demo import served_tiles_file
from tools import browsers

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
NODE_LOG = REPO_ROOT / "data" / "node-sim.log"
FRONTEND = REPO_ROOT / "app" / "frontend"
PORT = 8765
MENU_EXIT = 3  # the backend's exit code for BYT SCENARIO (TECHSEED_DEMO_MENU_EXIT)
RESTART_EXIT = 4  # the backend's exit code for STARTA OM DEMO (TECHSEED_DEMO_RESTART_EXIT)
MENU_TITLE = "Techseed Geospatial Intelligence Demos"
# Kiosk mode: how often the nodes and screens are looked after, and the wait before a stopped demo starts again.
WATCH_SECONDS = 10.0
RETRY_SECONDS = 10.0


def scenario_settings(name: str) -> tuple[str, str]:
    """The scenario's map tiles file and the demo's start, without choosing it here: the start
    saved in the scenario's display profile (app/backend/profiles.py) when it lies in the
    scenario's period, else the scenario's playback start."""
    module = importlib.import_module(f"app.backend.scenarios.{name}")
    start = module.PLAYBACK_START.strftime("%Y-%m-%dT%H:%M:%SZ")
    window = (profiles.load(name, incident=module.INCIDENT) or {}).get("playback")
    if window:
        saved = datetime.fromisoformat(window["start_utc"].replace("Z", "+00:00"))
        if module.PLAYBACK_START <= saved < module.PLAYBACK_END:
            start = window["start_utc"]
    return module.TILES_FILE, start


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
            self.send_json(HTTPStatus.OK, {"title": MENU_TITLE, "demos": demos(), "kiosk": self.server.kiosk})
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
            body = json.loads(self.rfile.read(min(length, 1024))) if 0 < length <= 1024 else {}
            name, kiosk = body["scenario"], body.get("kiosk", self.server.kiosk)
        except (ValueError, KeyError, TypeError, AttributeError):
            name, kiosk = None, None
        if name not in AVAILABLE or not isinstance(kiosk, bool) or self.server.chosen:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_demo"})
            return
        self.server.chosen, self.server.kiosk = name, kiosk
        self.send_json(HTTPStatus.ACCEPTED, {"scenario": name, "kiosk": kiosk})
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def menu_server(port: int = PORT, kiosk: bool = False) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), MenuHandler)
    server.daemon_threads = True
    server.chosen = None
    server.kiosk = kiosk  # KIOSKLÄGE as the menu shows it, and as chosen with the demo
    return server


def browser_flags(browser: str) -> list[str]:
    return ["--browser", browser] if browser != "chrome" or os.environ.get("TECHSEED_BROWSER", "chrome") != "chrome" else []


def choose_demo(browser: str = "chrome", kiosk: bool = False) -> tuple[str, bool]:
    """Show the menu in mission control's window until a demo is chosen; its name and whether kiosk mode is on."""
    server = menu_server(kiosk=kiosk)
    print(f"Menyn: {MENU_TITLE} i mission control – välj en demo (Ctrl+C avslutar).", flush=True)
    subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--menu", "--base-url", f"http://127.0.0.1:{PORT}", *browser_flags(browser)],
                   cwd=REPO_ROOT, check=False)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return server.chosen, server.kiosk


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


def missing_screens(browser: str = "chrome") -> list[str]:
    """The demo's screens whose browser no longer runs (tools/open_screens.py)."""
    return [screen for screen in open_screens.SCREENS
            if subprocess.run(open_screens.running_command(screen, browser), capture_output=True, check=False, timeout=30).returncode != 0]


def look_after(nodes: subprocess.Popen, start_nodes, missing, reopen) -> subprocess.Popen:
    """Kiosk mode's check: start the nodes again if they have stopped, and open the screens that have gone;
    returns the nodes' process."""
    if nodes.poll() is not None:
        print(f"Kioskläge: sensorerna stannade (kod {nodes.returncode}) – startar dem igen", flush=True)
        nodes = start_nodes()
    gone = missing()
    if gone:
        print(f"Kioskläge: {', '.join(gone)} saknas – öppnar igen", flush=True)
        reopen(gone)
    return nodes


def run_demo(name: str, at: str | None, *, kiosk: bool = False, native_env: dict[str, str] | None = None, browser: str = "chrome") -> int:
    """Start a demo and run it until the backend stops; its exit code (MENU_EXIT for BYT SCENARIO, RESTART_EXIT for STARTA OM DEMO), 0 after Ctrl+C.
    In kiosk mode the backend loops the demo by itself."""
    tiles, start = scenario_settings(name)
    base_url = f"http://127.0.0.1:{PORT}"
    print(f"1/4 Tjänsterna, med kartan {tiles} …", flush=True)
    if native_env is None:
        subprocess.run(services_command(), cwd=REPO_ROOT, env={**os.environ, "TILES_FILE": tiles}, check=True)
    template = native_env["OFFLINE_TILES_URL"] if native_env is not None else offline_tiles.url_template()
    wait_until(lambda: served_tiles_file(template) == tiles, 90, f"the tiles service did not serve {tiles}")

    print(f"2/4 Backend för {name}{' i kioskläge' if kiosk else ''} …", flush=True)
    env = {**(os.environ if native_env is None else native_env), "TECHSEED_SCENARIO": name, "TECHSEED_DEMO_MENU_EXIT": str(MENU_EXIT),
           "TECHSEED_DEMO_RESTART_EXIT": str(RESTART_EXIT), "TECHSEED_DEMO_KIOSK": "1" if kiosk else "0"}
    backend = subprocess.Popen([str(PYTHON), "-m", "app.backend.server", "--scenario", name, "--port", str(PORT)],
                               cwd=REPO_ROOT, env=env)
    nodes = None
    try:
        wait_until(lambda: backend.poll() is not None or answers(f"{base_url}/api/config"), 180, "the backend did not answer")
        if backend.poll() is not None:
            raise SystemExit(f"start_demo: the backend stopped (exit {backend.returncode})")

        print(f"3/4 Sensorerna i montern (simulerade; loggen i {NODE_LOG.relative_to(REPO_ROOT)}) …", flush=True)
        NODE_LOG.parent.mkdir(parents=True, exist_ok=True)

        def start_nodes() -> subprocess.Popen:
            with NODE_LOG.open("a", encoding="utf-8") as log:
                return subprocess.Popen([str(PYTHON), "-m", "tools.mqtt_node_sim", "--interval", "5"],
                                        cwd=REPO_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)

        def reopen(screens: list[str]) -> None:
            subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--base-url", base_url, "--only", ",".join(screens),
                            *browser_flags(browser)], cwd=REPO_ROOT, check=False)

        nodes = start_nodes()

        print("4/4 Skärmarna …", flush=True)
        subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--base-url", base_url, "--at", at or start, *browser_flags(browser)],
                       cwd=REPO_ROOT, check=False)
        print(f"Demon går: {name} på {base_url}{' i kioskläge' if kiosk else ''}. BYT SCENARIO i mission control ger menyn, "
              "STARTA OM DEMO startar om; Ctrl+C stoppar.", flush=True)
        while True:
            try:
                backend.wait(timeout=WATCH_SECONDS if kiosk else None)
                break
            except subprocess.TimeoutExpired:
                nodes = look_after(nodes, start_nodes, lambda: missing_screens(browser), reopen)
        if backend.returncode == MENU_EXIT:
            print("BYT SCENARIO: tillbaka till menyn …", flush=True)
            return MENU_EXIT
        if backend.returncode == RESTART_EXIT:
            print("STARTA OM DEMO: skärmarna stängs och demon startar om …", flush=True)
            return RESTART_EXIT
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
    parser.add_argument("--services", choices=("docker", "native"), default="docker")
    parser.add_argument("--node-modules", type=Path, help="native TileServer GL runtime node_modules directory")
    parser.add_argument("--node", help="native Node.js executable")
    parser.add_argument("--mosquitto", help="native Mosquitto executable")
    parser.add_argument("--browser", choices=("chrome", "edge"))
    parser.add_argument("--kiosk", action="store_true", help="kiosk mode: the demo plays, shows its closing view and starts again by itself")
    args = parser.parse_args(argv)
    try:
        browser = browsers.choice(args.browser)
    except ValueError as exc:
        parser.error(str(exc))
    browser_options = {"browser": browser} if browser != "chrome" else {}
    if args.services == "native" and args.node_modules is None:
        parser.error("--services native requires --node-modules")
    if port_in_use(PORT):
        parser.exit(1, f"start_demo: something already answers on port {PORT} – stop the running backend first (Ctrl+C in its terminal)\n")
    name, at, kiosk = args.scenario, args.at, args.kiosk
    try:
        while True:
            if name is None:
                (name, kiosk), at = choose_demo(kiosk=kiosk, **browser_options), None
            kiosk_options = {"kiosk": True} if kiosk else {}
            try:
                if args.services == "native":
                    from tools import native_services
                    options = native_services.Options(args.node_modules, args.node, args.mosquitto)
                    # Kiosk mode starts the native services again with the demo, as the backend.
                    with native_services.running(name, options) as env:
                        code = run_demo(name, at, native_env=env, **kiosk_options, **browser_options)
                else:
                    code = run_demo(name, at, **kiosk_options, **browser_options)
            except (SystemExit, OSError, subprocess.SubprocessError) as exc:
                if not kiosk:
                    raise
                print(exc, flush=True)
                code = 1
            if kiosk and code not in (0, MENU_EXIT, RESTART_EXIT):
                # Kiosk mode: the demo stopped by itself or did not start; the same one again, from its saved start.
                print(f"Kioskläge: demon stannade – startar om {name} om {RETRY_SECONDS:.0f} s …", flush=True)
                subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--close", *browser_flags(browser)], cwd=REPO_ROOT, check=False)
                time.sleep(RETRY_SECONDS)
                at = None
                continue
            if code == RESTART_EXIT:
                # The same scenario again from its saved start, once its screens are closed.
                subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--close", *browser_flags(browser)], cwd=REPO_ROOT, check=False)
                at = None
                continue
            if code != MENU_EXIT:
                return code
            name = None
    except KeyboardInterrupt:
        print("\nAvslutar.")
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        if args.services != "native":
            raise
        print(f"start_demo: native services failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
