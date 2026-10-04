"""Tests for the traceable assessment (app/backend/assessment.py): the evidence lines,
the rule-based score and the HTTP and stream interface, with small invented inputs
and with the 2014 data."""

from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from app.backend import assessment, lantmateriet, server
from app.backend.scenario_engine import ScenarioEngine

UTC = timezone.utc
T0 = datetime(2014, 8, 1, 12, tzinfo=UTC)
CENTRE = (59.9, 16.2)
WIND = {"times_utc": ["2014-08-01T00:00:00Z"], "points": [[59.9, 16.2]], "values": [[[4.0, 225, 20.0]]]}
FORECAST = [{"pass_utc": "2014-08-01T12:00:00Z", "front_centre": [59.9, 16.2],
             "model": {"towards": "NO", "head_km_per_h": {"central": 0.5}}}]
NO_SENSORS = {"sensors": []}


def detection(moment: datetime, lat: float, lon: float, confidence: str = "n", instrument: str = "VIIRS", frp: float = 5.0) -> dict:
    return {"acq_datetime_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"), "latitude": lat, "longitude": lon,
            "confidence": confidence, "instrument": instrument, "satellite": "SNPP", "frp": frp}


def evidence(result: dict) -> dict[str, dict]:
    return {item["key"]: item for item in result["evidence"]}


def test_before_any_detection_there_is_no_fire() -> None:
    result = assessment.Assessor([detection(T0, 59.9, 16.2)], WIND, FORECAST, CENTRE).at(T0 - timedelta(hours=1), NO_SENSORS)
    lines = evidence(result)
    assert (result["outcome"], result["score_pct"]) == ("No fire indicated", 0)
    assert lines["satellite"]["status"] == "miss" and lines["camera"]["status"] == "warn"
    assert "forecast" not in lines  # no pass yet


def test_one_detection_gives_a_possible_fire_pointing_at_it() -> None:
    result = assessment.Assessor([detection(T0, 59.91, 16.21)], WIND, FORECAST, CENTRE).at(T0, NO_SENSORS)
    lines = evidence(result)
    assert lines["satellite"]["status"] == "ok" and lines["satellite"]["ref"] == {"latitude": 59.91, "longitude": 16.21}
    assert lines["repeat"]["status"] == "miss" and lines["high_confidence"]["status"] == "miss"
    assert (result["outcome"], result["score_pct"]) == ("Possible fire", 50)


def test_repeat_high_confidence_and_iot_add_up() -> None:
    items = [
        detection(T0 - timedelta(hours=12), 59.900, 16.200),
        detection(T0, 59.903, 16.202, confidence="85", instrument="MODIS", frp=40.5),  # about 350 m away, next pass
    ]
    sensors = {"sensors": [
        {"id": "s-1", "name": "S 1", "latitude": 59.91, "longitude": 16.2, "status": "ok", "confirms": True, "smoke": "DETECTED", "temp_c": 31.5},
        {"id": "s-2", "name": "S 2", "latitude": 59.95, "longitude": 16.2, "status": "ok", "confirms": False, "smoke": "NONE", "temp_c": 20.1},
        {"id": "s-3", "name": "S 3", "latitude": 59.85, "longitude": 16.2, "status": "failed", "confirms": False, "smoke": None, "temp_c": None},
    ]}
    result = assessment.Assessor(items, WIND, FORECAST, CENTRE).at(T0, sensors)
    lines = evidence(result)
    assert [lines[key]["status"] for key in ["satellite", "repeat", "high_confidence", "iot:s-1", "iot:s-2", "iot:s-3"]] == [
        "ok", "ok", "ok", "ok", "miss", "warn"]
    assert lines["high_confidence"]["text"] == "Hög FIRMS-konfidens: 1 detektioner, högst 40,5 MW FRP"
    assert lines["iot:s-1"]["text"] == "IoT S 1: rök, 31,5 °C (syntetisk)"
    expected = 1 - (1 - 0.50) * (1 - 0.30) * (1 - 0.20) * (1 - 0.25)
    assert result["score_pct"] == round(expected * 100) == 79 and result["outcome"] == "Wildfire probable"
    # Context lines never change the score.
    assert lines["wind"]["status"] == lines["forecast"]["status"] == "info"
    assert lines["wind"]["weight"] == lines["forecast"]["weight"] == lines["camera"]["weight"] == 0
    assert lines["wind"]["text"].startswith("Vind 4,0 m/s från SV")


def test_detections_older_than_24_hours_no_longer_count() -> None:
    model = assessment.Assessor([detection(T0, 59.9, 16.2)], WIND, FORECAST, CENTRE)
    later = model.at(T0 + timedelta(hours=24, minutes=1), NO_SENSORS)
    assert evidence(later)["satellite"]["status"] == "warn" and later["score_pct"] == 0


def test_the_2014_assessment_rises_and_every_line_holds_together() -> None:
    model = server.assessor()
    start = datetime(2014, 7, 31, tzinfo=UTC)
    scores = []
    for hours in [0, 12, 24, 72, 120]:
        clock = start + timedelta(hours=hours)
        result = model.at(clock, server.synthetic_sensors().at(clock))
        scores.append(result["score_pct"])
        product = math.prod(1 - item["weight"] for item in result["evidence"])
        assert result["score_pct"] == round((1 - product) * 100)
        assert all(item["weight"] == 0 or item["status"] == "ok" for item in result["evidence"])
        assert all(item["ref"] is None or set(item["ref"]) == {"latitude", "longitude"} for item in result["evidence"])
    assert scores[0] == 0 and scores == sorted(scores) and scores[-1] >= 75


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


def test_http_endpoint_and_stream_follow_the_scenario(base_url: str) -> None:
    request = Request(f"{base_url}/api/scenario/command", data=json.dumps({"command": "seek", "at": "2014-08-04T12:00:00Z"}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    urlopen(request, timeout=10).close()

    with urlopen(f"{base_url}/api/assessment", timeout=30) as response:
        result = json.loads(response.read())
    assert result["clock_utc"] == "2014-08-04T12:00:00Z" and result["outcome"] == "Wildfire probable"
    assert result["score_label"] == assessment.SCORE_LABEL

    with urlopen(f"{base_url}/api/scenario/stream", timeout=30) as response:
        name = None
        for raw in response:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name == "assessment":
                assert json.loads(line[6:]) == result
                break
