#!/usr/bin/env python3
"""Start a demo for the day: the services, the backend, the booth nodes and the three screens.

    .venv/bin/python -m tools.start_demo sundsvall2026      # or vastmanland2014

In order: the docker-compose.yml services with the scenario's map tiles (it waits until
the tiles service serves them), the backend for the scenario, the simulated booth nodes
(their lines go to data/node-sim.log) and the screens in their places
(tools/open_screens.py), at the scenario's starting time or --at. It then runs until
Ctrl+C, which stops the backend and the nodes; the screens and the services stay.

It stops at once when something already answers on the backend's port, such as a
backend left running, rather than start a second one.
"""

from __future__ import annotations

import argparse
import importlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from app.backend import offline_tiles
from app.backend.scenarios import AVAILABLE
from tools.check_demo import served_tiles_file

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
NODE_LOG = REPO_ROOT / "data" / "node-sim.log"
PORT = 8765


def scenario_settings(name: str) -> tuple[str, str]:
    """The scenario's map tiles file and starting time (its CHECK_START_UTC), without choosing it here."""
    module = importlib.import_module(f"app.backend.scenarios.{name}")
    return module.TILES_FILE, module.CHECK_START_UTC


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("scenario", choices=AVAILABLE)
    parser.add_argument("--at", help="the main screen's starting time in UTC (default: the scenario's)")
    args = parser.parse_args(argv)
    tiles, start = scenario_settings(args.scenario)
    base_url = f"http://127.0.0.1:{PORT}"
    if port_in_use(PORT):
        parser.exit(1, f"start_demo: something already answers on port {PORT} – stop the running backend first (Ctrl+C in its terminal)\n")

    print(f"1/4 Tjänsterna, med kartan {tiles} …", flush=True)
    subprocess.run(services_command(), cwd=REPO_ROOT, env={**os.environ, "TILES_FILE": tiles}, check=True)
    wait_until(lambda: served_tiles_file(offline_tiles.url_template()) == tiles, 90, f"the tiles service did not serve {tiles}")

    print(f"2/4 Backend för {args.scenario} …", flush=True)
    env = {**os.environ, "TECHSEED_SCENARIO": args.scenario}
    backend = subprocess.Popen([str(PYTHON), "-m", "app.backend.server", "--scenario", args.scenario, "--port", str(PORT)],
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
        subprocess.run([str(PYTHON), "-m", "tools.open_screens", "--base-url", base_url, "--at", args.at or start],
                       cwd=REPO_ROOT, check=False)
        print(f"Demon går: {args.scenario} på {base_url}. Tryck Ctrl+C för att stoppa backend och sensorerna.", flush=True)
        backend.wait()
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


if __name__ == "__main__":
    sys.exit(main())
