"""Real IoT sensors over MQTT: the TechSeed nodes in the booth (TEMP, WATER, AIR, NTN).

The nodes publish JSON to `techseed/<node>/<kind>`, for example
`techseed/booth-temp/temp` with `{"value": 24.7, "time_utc": "2026-10-02T14:32:17Z"}`.
`SensorStore` keeps the latest valid reading per node and kind and says a node is
offline when it has been silent longer than the timeout. It needs no MQTT library,
so it can be tested without a broker; `start()` connects it to the broker with
paho-mqtt (app/requirements-iot.txt) and leaves the store `unavailable` without it.

These readings are live values from real nodes; they are not part of the 2014
replay, and the GUI keeps them apart from the synthetic sensors in the fire area.
A message with `"simulated": true` comes from tools/mqtt_node_sim.py; its reading
is kept with `real: false` so the GUI can say so.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

TOPIC_FILTER = "techseed/+/+"
TOPIC = re.compile(r"techseed/([a-z0-9_-]{1,32})/(temp|water|air|ntn)")
UNITS = {"temp": "°C", "water": "cm"}
# AIR and NTN report a state word, for example NORMAL, SMOKE, ONLINE.
STATE_WORD = re.compile(r"[A-Z][A-Z_]{0,15}")
MAX_PAYLOAD = 512
DEFAULT_TIMEOUT_S = 60.0


def utc_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Rejected(ValueError):
    pass


def parse(topic: str, payload: bytes) -> tuple[str, str, float | str, str | None, bool]:
    """Node, kind, value, the node's own measurement time and whether it is simulated, or Rejected."""
    match = TOPIC.fullmatch(topic)
    if not match:
        raise Rejected("unknown topic")
    node, kind = match.groups()
    if len(payload) > MAX_PAYLOAD:
        raise Rejected("payload too large")
    try:
        message = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Rejected("payload is not JSON") from exc
    if not isinstance(message, dict) or "value" not in message:
        raise Rejected("payload needs a value")
    value = message["value"]
    if kind in UNITS:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise Rejected(f"{kind} needs a finite number")
        value = float(value)
    elif not isinstance(value, str) or not STATE_WORD.fullmatch(value):
        raise Rejected(f"{kind} needs a state word such as NORMAL")
    measured = message.get("time_utc")
    if measured is not None:
        try:
            measured = utc_text(datetime.fromisoformat(str(measured).replace("Z", "+00:00")))
        except ValueError as exc:
            raise Rejected("invalid time_utc") from exc
    simulated = message.get("simulated", False)
    if not isinstance(simulated, bool):
        raise Rejected("simulated must be true or false")
    return node, kind, value, measured, simulated


class SensorStore:
    def __init__(
        self,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.timeout_s = timeout_s
        self.monotonic = monotonic
        self.now = now
        self.connection = "unavailable"  # unavailable, connecting, connected, disconnected
        self.detail = "IoT är inte startat."
        self.rejected = 0
        self._seq = 0
        self._readings: dict[tuple[str, str], dict[str, Any]] = {}
        self._seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def handle(self, topic: str, payload: bytes) -> dict[str, Any] | None:
        """Store a message; returns the reading, or None when it was rejected."""
        try:
            node, kind, value, measured, simulated = parse(topic, payload)
        except Rejected as exc:
            with self._lock:
                self.rejected += 1
            print(f"IoT: rejected message on {topic[:80]!r}: {exc}")
            return None
        with self._lock:
            self._seq += 1
            reading = {
                "seq": self._seq, "node": node, "kind": kind, "value": value, "unit": UNITS.get(kind),
                "measured_utc": measured, "received_utc": utc_text(self.now()), "real": not simulated,
            }
            self._readings[(node, kind)] = reading
            self._seen[(node, kind)] = self.monotonic()
            return dict(reading)

    def set_connection(self, connection: str, detail: str) -> None:
        with self._lock:
            self.connection, self.detail = connection, detail

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = self.monotonic()
            sensors = [
                {**reading, "online": now - self._seen[key] <= self.timeout_s}
                for key, reading in sorted(self._readings.items())
            ]
            return {
                "connection": self.connection, "detail": self.detail, "timeout_s": self.timeout_s,
                "rejected": self.rejected, "sensors": sensors,
            }


def client_id(prefix: str) -> str:
    """A client id of its own per process: the broker drops a client when another connects
    with the same id, so two backends (or a check next to a running demo) would keep
    pushing each other off."""
    return f"{prefix}-{os.getpid()}"


def start(store: SensorStore, host: str, port: int) -> None:
    """Connect the store to the broker in the background; reconnects by itself."""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        store.set_connection("unavailable", "paho-mqtt saknas (app/requirements-iot.txt).")
        return

    def on_connect(client: Any, _userdata: Any, _flags: Any, reason: Any, _properties: Any) -> None:
        if reason.is_failure:
            store.set_connection("disconnected", f"Brokern vägrade: {reason}.")
            return
        client.subscribe(TOPIC_FILTER, qos=0)
        store.set_connection("connected", f"Ansluten till {host}:{port}.")

    def on_disconnect(_client: Any, _userdata: Any, _flags: Any, reason: Any, _properties: Any) -> None:
        store.set_connection("disconnected", f"Frånkopplad från {host}:{port} ({reason}) – försöker igen.")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id("techseed-firemap"), clean_session=True)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = lambda _client, _userdata, message: store.handle(message.topic, message.payload)
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    store.set_connection("connecting", f"Ansluter till {host}:{port} …")
    client.connect_async(host, port, keepalive=30)
    client.loop_start()
