"""Tests for the synthetic sensors in the fire area (app/backend/sensor_sim.py), with a
small invented fire and wind field, and with the real 2014 data through the backend."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from app.backend import lantmateriet, sensor_sim, server
from app.backend.scenario_engine import ScenarioEngine

UTC = timezone.utc
T0 = datetime(2014, 8, 1, 12, tzinfo=UTC)
CENTRE = (59.9, 16.2)
# A fire square of about 1.1 km x 1.1 km at the centre, then one that grows north.
EARLY = [(T0, 59.895, 16.19), (T0, 59.895, 16.21), (T0, 59.905, 16.21), (T0, 59.905, 16.19)]
LATER = [(T0 + timedelta(hours=6), 59.95, 16.20)]


def wind(blows_from: int, temp: float = 20.0) -> dict:
    return {"times_utc": ["2014-08-01T00:00:00Z"], "points": [[59.9, 16.2]], "values": [[[5.0, blows_from, temp]]]}


def sensors(monkeypatch: pytest.MonkeyPatch, positions, blows_from: int = 180) -> sensor_sim.SyntheticSensors:
    monkeypatch.setattr(sensor_sim, "SENSORS", positions)
    return sensor_sim.SyntheticSensors(EARLY + LATER, wind(blows_from), CENTRE)


def by_id(result: dict) -> dict[str, dict]:
    return {item["id"]: item for item in result["sensors"]}


def test_before_the_first_detection_nothing_confirms(monkeypatch: pytest.MonkeyPatch) -> None:
    result = sensors(monkeypatch, (("s-1", "S 1", 59.9, 16.2),)).at(T0 - timedelta(minutes=1))
    item = result["sensors"][0]
    assert item["distance_km"] is None and item["smoke"] == "NONE" and item["temp_c"] == 20.0
    assert (result["confirms"], result["operating"]) == (0, 1)


def test_heat_falls_with_the_distance_to_the_front(monkeypatch: pytest.MonkeyPatch) -> None:
    # Wind from the south blows smoke north; these sensors lie west, east and inside.
    result = by_id(sensors(monkeypatch, (
        ("inside", "", 59.900, 16.200), ("west-2km", "", 59.900, 16.155), ("east-5km", "", 59.900, 16.300),
    )).at(T0))

    assert result["inside"]["distance_km"] == 0.0 and result["inside"]["temp_c"] == 45.0
    assert result["inside"]["smoke"] == "DETECTED" and result["inside"]["confirms"]
    west, east = result["west-2km"], result["east-5km"]
    assert 1.9 < west["distance_km"] < 2.1
    heat = sensor_sim.HEAT_MAX_C * math.exp(-west["distance_km"] * 1000 / sensor_sim.HEAT_SCALE_M)
    assert west["temp_c"] == pytest.approx(20.0 + heat, abs=0.1)
    assert west["confirms"] and west["smoke"] == "NONE"  # heat over CONFIRM_HEAT_C
    assert not east["confirms"] and east["smoke"] == "NONE" and east["temp_c"] < 21.0


def test_smoke_is_detected_downwind_only(monkeypatch: pytest.MonkeyPatch) -> None:
    positions = (("north-4km", "", 59.94, 16.20), ("south-4km", "", 59.86, 16.20))
    from_south = by_id(sensors(monkeypatch, positions, blows_from=180).at(T0))
    from_north = by_id(sensors(monkeypatch, positions, blows_from=0).at(T0))

    assert from_south["north-4km"]["smoke"] == "DETECTED" and from_south["south-4km"]["smoke"] == "NONE"
    assert from_north["south-4km"]["smoke"] == "DETECTED" and from_north["north-4km"]["smoke"] == "NONE"


def test_the_front_grows_with_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    model = sensors(monkeypatch, (("north", "", 59.94, 16.20),), blows_from=90)
    before = model.at(T0)["sensors"][0]
    after = model.at(T0 + timedelta(hours=6))["sensors"][0]
    assert after["distance_km"] < before["distance_km"] and after["temp_c"] > before["temp_c"]


def test_failed_sensors_have_no_values_and_do_not_count(monkeypatch: pytest.MonkeyPatch) -> None:
    model = sensors(monkeypatch, (("a", "", 59.900, 16.200), ("b", "", 59.900, 16.205)))
    result = model.at(T0, failed=["a", None])
    items = by_id(result)
    assert items["a"] == {**items["a"], "status": "failed", "temp_c": None, "smoke": None, "confirms": False}
    assert items["b"]["status"] == "ok" and items["b"]["confirms"]
    assert (result["confirms"], result["operating"]) == (1, 1)
    assert all(item["synthetic"] for item in result["sensors"])


def test_placed_sensors_are_computed_like_the_fixed_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    model = sensors(monkeypatch, (("a", "", 59.900, 16.200),))
    placed = [{"id": "placed-1", "name": "Sensor P1", "latitude": 59.900, "longitude": 16.205},
              {"id": "placed-2", "name": "Sensor P2", "latitude": 59.900, "longitude": 16.300}]
    result = model.at(T0, failed=["placed-2"], placed=placed)
    items = by_id(result)
    assert [item["id"] for item in result["sensors"]] == ["a", "placed-1", "placed-2"]
    assert not items["a"]["placed"] and items["placed-1"]["placed"] and items["placed-1"]["confirms"]
    assert items["placed-2"]["status"] == "failed"
    assert (result["confirms"], result["operating"]) == (2, 2)


def test_the_2014_fire_reaches_the_sensors_one_after_another() -> None:
    model = server.synthetic_sensors()
    counts = [model.at(datetime(2014, 7, 31, tzinfo=UTC) + timedelta(days=day))["confirms"] for day in range(10)]
    assert counts[0] == 0 and counts[-1] == len(sensor_sim.SENSORS)
    assert counts == sorted(counts) and len(set(counts)) > 2


@pytest.fixture()
def base_url():
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None),
        "engine": ScenarioEngine(datetime(2014, 7, 31, tzinfo=UTC), datetime(2014, 8, 15, tzinfo=UTC)),
        "control_token": None,
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def command(base_url: str, body: dict) -> None:
    request = Request(f"{base_url}/api/scenario/command", data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    urlopen(request, timeout=10).close()


def test_http_endpoint_and_stream_follow_the_scenario(base_url: str) -> None:
    command(base_url, {"command": "seek", "at": "2014-08-05T12:00:00Z"})
    command(base_url, {"command": "sensor_failure", "target": "sensor-17"})

    with urlopen(f"{base_url}/api/sensors/synthetic", timeout=10) as response:
        result = json.loads(response.read())
    assert result["clock_utc"] == "2014-08-05T12:00:00Z" and result["label"] == sensor_sim.LABEL
    assert by_id(result)["sensor-17"]["status"] == "failed"
    assert result["operating"] == len(sensor_sim.SENSORS) - 1

    with urlopen(f"{base_url}/api/scenario/stream", timeout=10) as response:
        name = None
        for raw in response:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name == "synthetic_sensors":
                assert json.loads(line[6:]) == result
                break


def node_sensors(expression: str) -> object:
    script = Path(__file__).resolve().parents[1] / "app" / "frontend" / "sensors.js"
    code = f"const s = require({json.dumps(str(script))}); with (s) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_sensor_texts_keep_real_and_synthetic_apart() -> None:
    real = node_sensors('realSensorLine({node: "booth-temp", kind: "temp", value: 24.7, unit: "°C", online: true})')
    silent = node_sensors('realSensorLine({node: "booth-ntn", kind: "ntn", value: "ONLINE", unit: null, online: false})')
    assert real == {"level": "ok", "text": "TECHSEED TEMP booth-temp: 24,7 °C · live"}
    assert silent == {"level": "alert", "text": "TECHSEED NTN booth-ntn: ONLINE · OFFLINE"}
    simulated = node_sensors('realSensorLine({node: "booth-air", kind: "air", value: "NORMAL", unit: null, online: true, real: false})')
    assert simulated == {"level": "ok", "text": "TECHSEED AIR booth-air: NORMAL · simulerad"}

    hot = {"name": "Sensor 17", "status": "ok", "temp_c": 46.2, "smoke": "DETECTED", "distance_km": 0.85, "confirms": True}
    inside = {**hot, "distance_km": 0}
    failed = {**hot, "status": "failed", "temp_c": None, "smoke": None, "distance_km": None, "confirms": False}
    assert node_sensors(f"syntheticSensorText({json.dumps(hot)})") == "Sensor 17: 46,2 °C, Smoke DETECTED, 0,85 km från fronten (syntetisk)"
    assert node_sensors(f"syntheticSensorText({json.dumps(inside)})").endswith("i brandområdet (syntetisk)")
    assert node_sensors(f"syntheticSensorText({json.dumps(failed)})") == "Sensor 17: SENSOR FAILURE (syntetiskt)"
    assert node_sensors(f"[syntheticState({json.dumps(hot)}), syntheticState({json.dumps(failed)})]") == ["confirms", "failed"]
    assert node_sensors('confirmsText({confirms: 2, operating: 3})') == "IoT bekräftar 2/3 (syntetiska sensorer)"
    assert node_sensors('connectionText({connection: "unavailable", detail: "paho-mqtt saknas.", sensors: []})') == "IoT: paho-mqtt saknas."


def test_the_sensors_changes_are_listed_for_the_log(base_url: str) -> None:
    with urlopen(f"{base_url}/api/sensors/synthetic/events", timeout=30) as response:
        result = json.loads(response.read())
    events = result["events"]
    assert result["step_minutes"] == 10 and events
    assert [item["clock_utc"] for item in events] == sorted(item["clock_utc"] for item in events)
    for sensor in {item["sensor"] for item in events}:
        changes = [item["confirms"] for item in events if item["sensor"] == sensor]
        # Each sensor starts confirming first, and then alternates.
        assert changes == [index % 2 == 0 for index in range(len(changes))]
    assert {item["kind"] for item in events} == {"fire"}
    # A change is where the model's state differs from the sample before it.
    first = events[0]
    moment = server.parse_utc(first["clock_utc"])
    state = {item["id"]: item["confirms"] for item in server.synthetic_sensors().at(moment)["sensors"]}
    before = {item["id"]: item["confirms"] for item in server.synthetic_sensors().at(moment - server.SENSOR_EVENT_STEP)["sensors"]}
    assert state[first["sensor"]] and not before[first["sensor"]]
