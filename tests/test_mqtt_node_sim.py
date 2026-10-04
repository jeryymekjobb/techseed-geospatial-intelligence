"""Tests for the node simulator (tools/mqtt_node_sim.py): its messages are what the
backend accepts from the real nodes, marked simulated. No broker is needed."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from app.backend import iot
from tools import mqtt_node_sim as sim

NOW = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)


def test_every_message_is_valid_for_the_backend_and_marked_simulated() -> None:
    rng = random.Random(1)
    for elapsed in [0, 300, 1800, 7200]:
        sent = sim.messages(elapsed, NOW, rng, sim.NODES, set())
        assert sorted(topic for topic, _ in sent) == sorted(f"techseed/{node}/{kind}" for node, kind in sim.NODES.items())
        for topic, payload in sent:
            node, kind, value, measured, simulated = iot.parse(topic, payload)
            assert simulated and measured == "2026-10-04T10:00:00Z"
            if kind == "temp":
                assert 20.5 <= value <= 24.5
            elif kind == "water":
                assert 39.0 <= value <= 45.0
            else:
                assert value in {"NORMAL", "ONLINE"}


def test_dropped_nodes_stay_silent() -> None:
    sent = sim.messages(0, NOW, random.Random(1), sim.NODES, {"booth-ntn", "booth-air"})
    assert sorted(topic for topic, _ in sent) == ["techseed/booth-temp/temp", "techseed/booth-water/water"]


def test_the_store_shows_simulated_nodes_as_not_real() -> None:
    store = iot.SensorStore()
    for topic, payload in sim.messages(0, NOW, random.Random(1), sim.NODES, set()):
        store.handle(topic, payload)
    sensors = store.snapshot()["sensors"]
    assert len(sensors) == 4 and all(item["real"] is False and item["online"] for item in sensors)
    assert json.loads(sim.messages(0, NOW, random.Random(1), {"booth-air": "air"}, set())[0][1]) == {
        "value": "NORMAL", "time_utc": "2026-10-04T10:00:00Z", "simulated": True,
    }
