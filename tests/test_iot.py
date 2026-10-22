"""Tests for the real IoT nodes over MQTT (app/backend/iot.py): parsing, validation,
the offline timeout and the HTTP and stream interface. No broker is needed; the
messages are handed to the store as the MQTT client would."""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

import pytest

from app.backend import iot, lantmateriet, server
from app.backend.scenario_engine import ScenarioEngine

NOW = datetime(2026, 10, 2, 14, 32, 17, tzinfo=timezone.utc)


class FakeTime:
    def __init__(self) -> None:
        self.now = 500.0

    def __call__(self) -> float:
        return self.now


def store() -> tuple[iot.SensorStore, FakeTime]:
    fake = FakeTime()
    return iot.SensorStore(timeout_s=60, monotonic=fake, now=lambda: NOW), fake


def message(value: object, **extra: object) -> bytes:
    return json.dumps({"value": value, **extra}).encode()


def test_valid_readings_are_kept_per_node_and_kind() -> None:
    sensors, _ = store()

    temp = sensors.handle("techseed/booth-temp/temp", message(24.7, time_utc="2026-10-02T14:32:00Z"))
    sensors.handle("techseed/booth-water/water", message(42))
    sensors.handle("techseed/booth-air/air", message("NORMAL"))
    sensors.handle("techseed/booth-ntn/ntn", message("ONLINE"))
    latest = sensors.handle("techseed/booth-temp/temp", message(25.1))

    assert temp == {
        "seq": 1, "node": "booth-temp", "kind": "temp", "value": 24.7, "unit": "°C",
        "measured_utc": "2026-10-02T14:32:00Z", "received_utc": "2026-10-02T14:32:17Z", "real": True,
    }
    assert latest["seq"] == 5 and latest["measured_utc"] is None
    snapshot = sensors.snapshot()
    assert [(item["node"], item["kind"], item["value"]) for item in snapshot["sensors"]] == [
        ("booth-air", "air", "NORMAL"), ("booth-ntn", "ntn", "ONLINE"),
        ("booth-temp", "temp", 25.1), ("booth-water", "water", 42.0),
    ]
    assert all(item["online"] and item["real"] for item in snapshot["sensors"])
    assert snapshot["rejected"] == 0


@pytest.mark.parametrize("topic, payload", [
    ("other/booth-temp/temp", message(24.7)),
    ("techseed/booth-temp/humidity", message(50)),
    ("techseed/Booth Temp/temp", message(24.7)),
    ("techseed/booth-temp/temp", b"24.7 C"),
    ("techseed/booth-temp/temp", message("warm")),
    ("techseed/booth-temp/temp", b'{"value": NaN}'),
    ("techseed/booth-temp/temp", message(True)),
    ("techseed/booth-temp/temp", json.dumps([24.7]).encode()),
    ("techseed/booth-temp/temp", message(24.7, time_utc="yesterday")),
    ("techseed/booth-air/air", message("smoke <b>")),
    ("techseed/booth-air/air", message(3)),
    ("techseed/booth-temp/temp", message("x" * 600)),
    ("techseed/booth-temp/temp", message(24.7, simulated="yes")),
])
def test_invalid_messages_are_rejected_and_counted(topic: str, payload: bytes) -> None:
    sensors, _ = store()

    assert sensors.handle(topic, payload) is None
    assert sensors.snapshot()["sensors"] == [] and sensors.snapshot()["rejected"] == 1


def test_simulated_messages_are_kept_as_not_real() -> None:
    sensors, _ = store()

    assert sensors.handle("techseed/booth-temp/temp", message(22.4, simulated=True))["real"] is False
    assert sensors.handle("techseed/booth-water/water", message(42, simulated=False))["real"] is True


def test_a_silent_node_goes_offline_and_comes_back() -> None:
    sensors, fake = store()

    sensors.handle("techseed/booth-temp/temp", message(24.7))
    fake.now += 60
    assert sensors.snapshot()["sensors"][0]["online"]
    fake.now += 1
    assert not sensors.snapshot()["sensors"][0]["online"]
    sensors.handle("techseed/booth-temp/temp", message(24.9))
    assert sensors.snapshot()["sensors"][0]["online"]


def test_without_paho_the_store_says_iot_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "paho", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", None)
    sensors, _ = store()

    iot.start(sensors, "127.0.0.1", 1883)
    snapshot = sensors.snapshot()
    assert snapshot["connection"] == "unavailable" and "paho-mqtt" in snapshot["detail"]


@pytest.fixture()
def served():
    # The stream computes the assessment every tick; build it first, as main() does, so the
    # first ticks are not slowed down by the forecast.
    server.assessor()
    sensors, fake = store()
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None),
        "engine": ScenarioEngine(datetime(2014, 7, 31, tzinfo=timezone.utc), datetime(2014, 8, 15, tzinfo=timezone.utc)),
        "sensors": sensors,
        "control_token": None,
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", sensors, fake
    httpd.shutdown()
    httpd.server_close()


def stream_events(url: str, until: callable, limit: int = 40) -> list[tuple[str, dict]]:
    events = []
    with urlopen(url, timeout=10) as response:
        name = None
        for raw in response:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[6:])))
                if until(events) or len(events) >= limit:
                    return events
    return events


def test_http_sensors_endpoint(served) -> None:
    base_url, sensors, _ = served
    sensors.handle("techseed/booth-temp/temp", message(24.7))

    with urlopen(f"{base_url}/api/sensors", timeout=10) as response:
        snapshot = json.loads(response.read())
    assert snapshot["connection"] == "unavailable" and snapshot["timeout_s"] == 60
    assert [(item["node"], item["value"], item["online"]) for item in snapshot["sensors"]] == [("booth-temp", 24.7, True)]


def test_the_stream_sends_each_reading_once_and_health_changes(served) -> None:
    base_url, sensors, fake = served
    sensors.handle("techseed/booth-temp/temp", message(24.7))
    received: list[tuple[str, dict]] = []
    synced = threading.Event()

    def follow() -> None:
        def until(events: list[tuple[str, dict]]) -> bool:
            if any(name == "sync" for name, _ in events):
                synced.set()
            return any(name == "sensor_health" for name, _ in events)
        received.extend(stream_events(f"{base_url}/api/scenario/stream", until))

    thread = threading.Thread(target=follow, daemon=True)
    thread.start()
    assert synced.wait(5)
    threading.Event().wait(0.6)  # a couple of ticks
    sensors.handle("techseed/booth-water/water", message(42))
    threading.Event().wait(0.6)
    fake.now += 61  # both nodes silent too long
    thread.join(10)

    readings = [data for name, data in received if name == "sensor"]
    assert [(item["node"], item["seq"]) for item in readings] == [("booth-temp", 1), ("booth-water", 2)]
    health = [data for name, data in received if name == "sensor_health"]
    assert health and all(item["online"] is False for item in health)


def test_every_process_has_its_own_client_id() -> None:
    import os

    assert iot.client_id("techseed-firemap") == f"techseed-firemap-{os.getpid()}"


@pytest.fixture
def own_broker():
    """A Mosquitto of the test's own, on a free port, so the test's node never reaches the shared broker
    on port 1883 and a backend listening there (a running demo, or the demo check) would not list it."""
    import shutil
    import socket
    import subprocess
    import time
    import uuid
    from pathlib import Path

    if not shutil.which("docker"):
        pytest.skip("needs Docker for a broker of the test's own")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    name = f"techseed-test-mosquitto-{uuid.uuid4().hex[:8]}"
    config = Path(__file__).resolve().parents[1] / "mosquitto" / "mosquitto.conf"
    started = subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:1883",
                              "-v", f"{config}:/mosquitto/config/mosquitto.conf:ro", "eclipse-mosquitto:2"],
                             capture_output=True, text=True, check=False, timeout=60)
    if started.returncode != 0:
        pytest.skip(f"could not start a broker of the test's own: {started.stderr.strip()[:200]}")
    try:
        deadline = time.time() + 20
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if time.time() > deadline:
                    pytest.skip("the test's own broker did not answer")
                time.sleep(0.2)
        yield port
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True, check=False, timeout=60)


@pytest.mark.skipif(not __import__("importlib").util.find_spec("paho"), reason="needs paho-mqtt")
def test_two_backends_both_receive_the_nodes(own_broker: int) -> None:
    import time

    import paho.mqtt.client as mqtt
    # Two stores in two "processes": give the second its own id as a second process would.
    first, second = iot.SensorStore(), iot.SensorStore()
    original = iot.client_id
    iot.start(first, "127.0.0.1", own_broker)
    iot.client_id = lambda prefix: original(prefix) + "-second"
    try:
        iot.start(second, "127.0.0.1", own_broker)
    finally:
        iot.client_id = original
    deadline = time.time() + 10
    while time.time() < deadline and not (first.connection == second.connection == "connected"):
        time.sleep(0.1)
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=original("test-publisher"))
    publisher.connect("127.0.0.1", own_broker)
    publisher.loop_start()
    publisher.publish("techseed/test-node/temp", message(21.5), qos=1).wait_for_publish()
    publisher.loop_stop()
    publisher.disconnect()
    # Only this test publishes on its own broker; look for its node by name all the same.
    def test_value(store: iot.SensorStore) -> object:
        return next((sensor["value"] for sensor in store.snapshot()["sensors"] if sensor["node"] == "test-node"), None)

    deadline = time.time() + 10
    while time.time() < deadline and not (test_value(first) is not None and test_value(second) is not None):
        time.sleep(0.1)
    assert first.connection == second.connection == "connected"
    assert test_value(first) == test_value(second) == 21.5
