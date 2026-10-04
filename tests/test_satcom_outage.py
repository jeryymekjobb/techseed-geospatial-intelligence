"""Tests for the simulated SATCOM outage: detections held back and queued while it
lasts, the assessment using only what arrived before it, and the SYNC summary when
the link is back."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from app.backend import assessment, lantmateriet, server
from app.backend.scenario_engine import ScenarioEngine

UTC = timezone.utc
T0 = datetime(2014, 8, 1, 12, tzinfo=UTC)
WIND = {"times_utc": ["2014-08-01T00:00:00Z"], "points": [[59.9, 16.2]], "values": [[[4.0, 225, 20.0]]]}


def detection(moment: datetime, lat: float, lon: float, instrument: str = "VIIRS") -> dict:
    return {"acq_datetime_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"), "latitude": lat, "longitude": lon,
            "confidence": "n", "instrument": instrument, "satellite": "SNPP", "frp": 5.0}


# A square front at T0, then two passes that widen it to the east.
ITEMS = [detection(T0, 59.89, 16.19), detection(T0, 59.89, 16.21), detection(T0, 59.91, 16.21), detection(T0, 59.91, 16.19),
         detection(T0 + timedelta(hours=2), 59.90, 16.23), detection(T0 + timedelta(hours=2), 59.91, 16.23, "MODIS"),
         detection(T0 + timedelta(hours=4), 59.90, 16.25)]


def model() -> assessment.Assessor:
    return assessment.Assessor(ITEMS, WIND, [], (59.9, 16.2))


def test_the_outage_summary_lists_the_passes_and_the_growth() -> None:
    summary = model().outage(T0 + timedelta(minutes=1), T0 + timedelta(hours=5))
    assert summary["from_utc"] == "2014-08-01T12:01:00Z" and summary["to_utc"] == "2014-08-01T17:00:00Z"
    assert summary["passes"] == [
        {"time_utc": "2014-08-01T14:00:00Z", "detections": 2, "instruments": ["MODIS", "VIIRS"]},
        {"time_utc": "2014-08-01T16:00:00Z", "detections": 1, "instruments": ["VIIRS"]},
    ]
    assert summary["detections"] == 3 and summary["area_increase_pct"] > 100
    empty = model().outage(T0 + timedelta(minutes=1), T0 + timedelta(minutes=30))
    assert empty["passes"] == [] and empty["area_increase_pct"] is None


def test_during_an_outage_only_earlier_detections_count() -> None:
    clock = T0 + timedelta(hours=5)
    normal = model().at(clock, {"sensors": []})
    cut = model().at(clock, {"sensors": []}, satellite_until=T0 + timedelta(minutes=1))
    assert "7 FIRMS-detektioner" in normal["evidence"][0]["text"]
    warning, satellite = cut["evidence"][0], cut["evidence"][1]
    assert warning["key"] == "satcom" and warning["status"] == "warn" and warning["weight"] == 0
    assert warning["text"] == "Satellitdata otillgänglig sedan 2014-08-01T12:01:00Z (simulerat avbrott) – 3 detektioner köade"
    assert "4 FIRMS-detektioner i 1 passager" in satellite["text"]


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


def command(base_url: str, body: dict) -> dict:
    request = Request(f"{base_url}/api/scenario/command", data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def test_the_stream_holds_back_queues_and_syncs(base_url: str) -> None:
    down, later = "2014-08-03T00:00:00Z", "2014-08-03T12:00:00Z"
    command(base_url, {"command": "seek", "at": down})
    command(base_url, {"command": "satcom_failure"})
    command(base_url, {"command": "seek", "at": later})
    expected = server.features_between(server.parse_utc(down), server.parse_utc(later))
    assert expected  # the 2014 data has detections in these twelve hours

    received: list[tuple[str, dict]] = []
    synced = threading.Event()

    def follow() -> None:
        with urlopen(f"{base_url}/api/scenario/stream", timeout=30) as response:
            name = None
            for raw in response:
                line = raw.decode("utf-8").rstrip("\n")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    received.append((name, json.loads(line[6:])))
                    if name == "satcom_queue":
                        synced.set()
                    cleared = name == "satcom_queue" and line == 'data: {"since_utc": null, "queued": 0}'
                    if cleared and sum(1 for event, _ in received if event == "hotspot") >= len(expected):
                        return

    thread = threading.Thread(target=follow, daemon=True)
    thread.start()
    assert synced.wait(30)
    sync = next(data for name, data in received if name == "sync")
    assert all(item["properties"]["acq_datetime_utc"] <= down for item in sync["features"])
    queue = next(data for name, data in received if name == "satcom_queue")
    assert queue == {"since_utc": down, "queued": len(expected)}

    command(base_url, {"command": "satcom_restore"})
    thread.join(30)
    names = [name for name, _ in received]
    summary = next(data for name, data in received if name == "satcom_sync")
    assert summary["from_utc"] == down and summary["to_utc"] == later and summary["detections"] == len(expected)
    restore = next(index for index, (name, data) in enumerate(received) if name == "scenario_event" and data["kind"] == "satcom_restore")
    assert restore < names.index("satcom_sync")  # the SYNC is shown after the restore event
    assert [data for name, data in received if name == "hotspot"] == expected
    assert received[-1] == ("satcom_queue", {"since_utc": None, "queued": 0})


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_queue_and_sync_texts() -> None:
    script = Path(__file__).resolve().parents[1] / "app" / "frontend" / "scenario_events.js"
    summary = {"passes": [{"time_utc": "2014-08-03T01:48:00Z", "detections": 37, "instruments": ["MODIS", "VIIRS"]}], "area_increase_pct": 17}
    expression = (f'[queueText({{since_utc: "2014-08-03T00:00:00Z", queued: 37}}), queueText({{since_utc: null, queued: 0}}), '
                  f'syncBanner({json.dumps(summary)}).title, syncLines({json.dumps(summary)}).map((line) => line.text)]')
    code = f"const s = require({json.dumps(str(script))}); with (s) {{ console.log(JSON.stringify({expression})); }}"
    queued, quiet, title, lines = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert queued == "EDGE PROCESSING – 37 detektioner köade sedan 00:00 UTC (simulerat avbrott)" and quiet == ""
    assert title == "SYNC – 1 NEW EVENTS"
    assert lines == ["08-03 01:48 UTC – 37 nya detektioner (MODIS, VIIRS)", "Brandfrontens yta ökade 17 %"]
