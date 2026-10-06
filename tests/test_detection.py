"""Tests for phase 2, detection from space: the pass a sequence is built on, the operator
stepping through it, and the rule-based classification (app/backend/detection.py)."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app.backend import detection, lantmateriet, server
from app.backend.scenario_engine import DETECTION_STEPS, CommandError, ScenarioEngine

UTC = timezone.utc
START, END = datetime(2014, 7, 31, tzinfo=UTC), datetime(2014, 8, 15, tzinfo=UTC)


def passes() -> detection.Detections:
    return server.firms_passes()


def test_the_next_pass_is_the_first_real_one_after_the_clock() -> None:
    first = passes().next_pass(START)
    assert first == {"pass_utc": "2014-07-31T11:50:00Z", "satellite": "Aqua", "instrument": "MODIS", "detections": 1,
                     "max_frp_mw": 33.3, "strongest": first["strongest"], "centre": first["centre"]}
    assert passes().next_pass(detection.parse_utc("2014-08-04T09:30:00Z"))["pass_utc"] == "2014-08-04T09:35:00Z"
    assert passes().next_pass(detection.parse_utc("2014-08-14T00:00:00Z")) is None
    assert len(passes().passes) == 48


def test_the_classification_says_vegetation_fire_while_the_fire_spreads() -> None:
    summary = passes().next_pass(detection.parse_utc("2014-08-04T09:30:00Z"))
    result = detection.classify(passes(), summary)
    assert result["outcome"] == "Vegetationsbrand" and result["counts"] == {"Vegetationsbrand": 3, "Industri": 0}
    assert [rule["category"] for rule in result["rules"]] == ["Vegetationsbrand"] * 3 + ["Industri"] * 2
    # Rules and counts, no invented probability per category.
    assert set(result) == {"outcome", "rules", "counts", "label"} and "ingen sannolikhet" in result["label"]


def test_a_spot_that_keeps_burning_without_growth_counts_for_industry() -> None:
    summary = passes().next_pass(detection.parse_utc("2014-08-09T00:00:00Z"))
    rules = {rule["text"].split(" ")[0]: rule for rule in detection.classify(passes(), summary)["rules"]}
    assert rules["Samma"]["holds"] and rules["Samma"]["category"] == "Industri"


def test_a_tie_or_no_rule_holding_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    summary = passes().next_pass(START)
    monkeypatch.setattr(detection, "land_cover_at", lambda lat, lon: None)  # no land cover
    monkeypatch.setattr(detection, "industrial_buildings", lambda: [(summary["centre"]["latitude"], summary["centre"]["longitude"])])
    result = detection.classify(passes(), summary)
    # FIRMS type 0 for vegetation, the building for industry: one each.
    assert result["counts"] == {"Vegetationsbrand": 1, "Industri": 1} and result["outcome"] == "Okänd"


def test_the_operator_steps_through_the_sequence_and_reset_ends_it() -> None:
    engine = ScenarioEngine(START, END)
    engine.command("play")
    state = engine.command("satellite_detection", at="2014-08-04T09:35:00Z")
    assert state["status"]["detection"] == {"pass_utc": "2014-08-04T09:35:00Z", "step": 0, "name": "acquired", "steps": 6}
    assert state["clock_utc"] == "2014-08-04T09:33:00Z" and state["playing"] is False
    assert engine.command("next")["status"]["detection"]["name"] == "anomaly"
    engine.command("next")
    zoom = engine.command("next")
    assert zoom["status"]["detection"]["name"] == "zoom" and zoom["clock_utc"] == "2014-08-04T09:41:00Z"
    engine.command("next")
    assert engine.command("next")["status"]["detection"]["name"] == DETECTION_STEPS[-1]
    assert engine.command("next")["status"]["detection"] is None  # past the last step
    with pytest.raises(CommandError):
        engine.command("next")
    engine.command("satellite_detection", at="2014-08-04T09:35:00Z")
    assert engine.command("reset")["status"]["detection"] is None


def test_a_detection_without_a_pass_time_is_just_an_event() -> None:
    engine = ScenarioEngine(START, END)
    state = engine.command("satellite_detection")
    assert state["status"]["detection"] is None and state["events"][-1]["kind"] == "satellite_detection"


@pytest.fixture()
def base_url():
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None), "engine": ScenarioEngine(START, END), "control_token": None,
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def command(base_url: str, body: dict) -> tuple[int, dict]:
    request = Request(f"{base_url}/api/scenario/command", data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_mission_control_starts_the_sequence_on_the_next_pass(base_url: str) -> None:
    command(base_url, {"command": "seek", "at": "2014-08-04T09:30:00Z"})
    status, state = command(base_url, {"command": "satellite_detection"})
    assert status == 200 and state["status"]["detection"]["pass_utc"] == "2014-08-04T09:35:00Z"
    with urlopen(f"{base_url}/api/detection", timeout=10) as response:
        info = json.loads(response.read())
    assert info["pass"]["satellite"] == "Terra" and info["classification"]["outcome"] == "Vegetationsbrand"
    command(base_url, {"command": "reset"})
    with urlopen(f"{base_url}/api/detection", timeout=10) as response:
        assert json.loads(response.read()) is None
    command(base_url, {"command": "seek", "at": "2014-08-14T00:00:00Z"})
    status, error = command(base_url, {"command": "satellite_detection"})
    assert status == 400 and "no satellite pass" in error["detail"]
