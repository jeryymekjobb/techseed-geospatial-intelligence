"""Owned native map/MQTT processes and read-only PostGIS checks; never use Docker.

PostgreSQL must already be installed, running and loaded for the selected scenario.
Only this launcher's Node/Mosquitto children are stopped. No database is created or
loaded here. Native runtime paths are supplied explicitly by the caller.

The broker listens on MQTT_PORT unless Options gives another port, for a computer where
something else already listens there (zenon Data Hub's Mosquitto, in the Windows test of
2026-10-22); the backend and the simulated booth nodes get the same port.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import json
import os
import re
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

from app.backend import postgres
from app.backend.scenarios import REPO_ROOT
from tools import start_native_mqtt, start_native_tiles


MQTT_PORT = 1883
TILES_PORT = 8081


@dataclass(frozen=True)
class Options:
    node_modules: Path
    node: str | None = None
    mosquitto: str | None = None
    mqtt_port: int = MQTT_PORT


def child_environment(name: str, mqtt_port: int = MQTT_PORT) -> dict[str, str]:
    return {**os.environ, "TECHSEED_DB_MODE": "native", "TECHSEED_SCENARIO": name,
            "OFFLINE_TILES_URL": f"http://127.0.0.1:{TILES_PORT}/styles/techseed/256/{{z}}/{{x}}/{{y}}.png",
            "IOT_MQTT_BROKER": f"127.0.0.1:{mqtt_port}"}


def check_database(name: str) -> None:
    settings = importlib.import_module(f"app.backend.scenarios.{name}")
    env = child_environment(name)
    result = subprocess.run(postgres.command(settings.DATABASE, environ=env),
                            input="SELECT PostGIS_Version();\n", text=True, encoding="utf-8",
                            env=postgres.environment(env), capture_output=True, timeout=15, check=False)
    if result.returncode or not result.stdout.strip():
        raise ValueError("Local PostGIS check failed; install, start and load the selected scenario separately")


def prepared(name: str, options: Options) -> tuple[dict, list[str], str]:
    settings = importlib.import_module(f"app.backend.scenarios.{name}")
    config = start_native_tiles.configuration(settings.TILES_FILE, options.node_modules)
    entry, _ = start_native_tiles.runtime_paths(options.node_modules)
    node = shutil.which(options.node or "node")
    broker = shutil.which(options.mosquitto or "mosquitto")
    if not node or not broker:
        raise ValueError("Native services require Node.js and Mosquitto; supply --node and --mosquitto if not on PATH")
    version = subprocess.run([node, "--version"], check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    if not re.fullmatch(r"v(?:20|22|24)\.\d+\.\d+", version):
        raise ValueError("Native TileServer GL requires Node.js 20, 22 or 24")
    return config, [node, str(entry)], broker


def port_busy(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def stop(process) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@contextmanager
def running(name: str, options: Options):
    config, node_entry, broker = prepared(name, options)
    mqtt_config = start_native_mqtt.configuration(options.mqtt_port)  # refuses a port outside 1-65535
    check_database(name)
    for port in (TILES_PORT, options.mqtt_port):
        if port_busy(port):
            raise ValueError(f"Native service port {port} is in use; no existing service was stopped")
    children = []
    with tempfile.TemporaryDirectory(prefix="techseed-native-services-") as scratch:
        tiles = Path(scratch) / "tiles.json"
        mqtt = Path(scratch) / "mosquitto.conf"
        tiles.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        mqtt.write_text(mqtt_config, encoding="utf-8")
        try:
            children.append(subprocess.Popen(start_native_tiles.command(node_entry[0], Path(node_entry[1]), tiles, TILES_PORT), cwd=REPO_ROOT))
            children.append(subprocess.Popen(start_native_mqtt.command(broker, mqtt), cwd=REPO_ROOT))
            deadline = time.monotonic() + 60
            while True:
                if any(child.poll() is not None for child in children):
                    raise ValueError("A native service exited before becoming ready")
                if port_busy(TILES_PORT) and port_busy(options.mqtt_port):
                    break
                if time.monotonic() >= deadline:
                    raise ValueError("Native services did not become ready within 60 s")
                time.sleep(0.25)
            yield child_environment(name, options.mqtt_port)
        finally:
            for child in reversed(children):
                stop(child)
