#!/usr/bin/env python3
"""Simulate the TechSeed IoT nodes in the booth over MQTT – the source of the booth nodes in the exhibition demo, and for tests.

Publishes like the real nRF91 nodes (TEMP, WATER, AIR, NTN): JSON to
`techseed/<node>/<kind>` in the format app/backend/iot.py accepts. Every message
carries `"simulated": true`, and the GUI then shows the node as simulated, not live.
`--drop <node>` keeps a node silent so the offline timeout can be tried.

    docker compose up -d mosquitto
    .venv/bin/python -m tools.mqtt_node_sim --interval 5

Needs paho-mqtt (app/requirements-iot.txt).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from datetime import datetime, timezone

# Node name -> kind, as the four booth boxes in the one-pager.
NODES = {"booth-temp": "temp", "booth-water": "water", "booth-air": "air", "booth-ntn": "ntn"}


def reading(kind: str, elapsed_s: float, rng: random.Random) -> float | str:
    """A plausible, slowly varying value; invented, not a model of anything."""
    if kind == "temp":
        return round(22.5 + 1.5 * math.sin(elapsed_s / 600.0) + rng.uniform(-0.2, 0.2), 1)
    if kind == "water":
        return round(42.0 + 2.0 * math.sin(elapsed_s / 900.0) + rng.uniform(-0.5, 0.5), 1)
    if kind == "air":
        return "NORMAL"
    return "ONLINE"


def messages(elapsed_s: float, now: datetime, rng: random.Random, nodes: dict[str, str], drop: set[str]) -> list[tuple[str, bytes]]:
    stamp = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        (f"techseed/{node}/{kind}", json.dumps({"value": reading(kind, elapsed_s, rng), "time_utc": stamp, "simulated": True}).encode())
        for node, kind in nodes.items() if node not in drop
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--broker", default="127.0.0.1:1883", help="MQTT broker as host:port")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between rounds")
    parser.add_argument("--nodes", nargs="+", choices=sorted(NODES), default=sorted(NODES), help="nodes to simulate")
    parser.add_argument("--drop", nargs="*", default=[], choices=sorted(NODES), help="nodes that stay silent")
    parser.add_argument("--rounds", type=int, default=0, help="stop after this many rounds (0: run until Ctrl-C)")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be positive")

    import paho.mqtt.client as mqtt

    host, _, port = args.broker.rpartition(":")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="techseed-node-sim")
    client.connect(host or "127.0.0.1", int(port))
    client.loop_start()
    rng = random.Random(args.seed)
    nodes = {node: NODES[node] for node in args.nodes}
    started = time.monotonic()
    sent = 0
    try:
        while not args.rounds or sent < args.rounds:
            for topic, payload in messages(time.monotonic() - started, datetime.now(timezone.utc), rng, nodes, set(args.drop)):
                client.publish(topic, payload, qos=1).wait_for_publish()
            sent += 1
            print(f"round {sent}: {len(nodes) - len(set(args.drop) & set(nodes))} nodes published")
            if not args.rounds or sent < args.rounds:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
