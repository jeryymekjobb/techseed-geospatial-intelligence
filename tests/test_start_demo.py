"""Tests for tools/start_demo.py (nothing is started)."""

from __future__ import annotations

import socket

from tools import start_demo


def test_each_scenario_starts_with_its_own_map_and_time() -> None:
    assert start_demo.scenario_settings("vastmanland2014") == ("vastmanland.mbtiles", "2014-08-04T09:30:00Z")
    assert start_demo.scenario_settings("sundsvall2026") == ("sundsvall.mbtiles", "2026-08-16T05:00:00Z")
    assert start_demo.services_command() == ["docker", "compose", "up", "-d", "tiles", "postgis", "mosquitto"]


def test_a_port_in_use_is_found() -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        busy = server.getsockname()[1]
        assert start_demo.port_in_use(busy)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    assert not start_demo.port_in_use(free)
