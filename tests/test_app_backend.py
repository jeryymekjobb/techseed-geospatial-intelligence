"""Tests for the fire-map backend. The FIRMS files are the committed archive extracts."""

from __future__ import annotations

import base64
import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from app.backend import lantmateriet, server

UTC = timezone.utc


def item(moment: str) -> dict[str, object]:
    return {"acq_datetime_utc": moment, "latitude": 59.9, "longitude": 16.2, "instrument": "VIIRS", "frp": 1.0, "source_file": "x.csv"}


def test_playback_sends_detections_in_time_order_between_clock_ticks() -> None:
    items = (item("2014-07-31T11:50:00Z"), item("2014-07-31T12:44:00Z"), item("2014-08-01T00:52:00Z"))
    start = datetime(2014, 7, 31, 12, 0, tzinfo=UTC)
    end = datetime(2014, 8, 1, 12, 0, tzinfo=UTC)

    events = list(server.playback_events(items, start, end, speed=6 * 3600, tick=1.0))

    names = [name for name, _ in events]
    # The detection before `from` is not sent again; one tick covers six hours.
    assert names == ["hotspot", "clock", "clock", "hotspot", "clock", "clock", "end"]
    assert events[0][1]["properties"]["acq_datetime_utc"] == "2014-07-31T12:44:00Z"
    assert "source_file" not in events[0][1]["properties"]
    assert events[1][1] == {"sim_time_utc": "2014-07-31T18:00:00Z"}
    assert events[-1][1] == {"sim_time_utc": "2014-08-01T12:00:00Z"}


def test_real_detections_cover_the_fire_and_nothing_else() -> None:
    detections = server.detections()

    assert len(detections) == 1727
    assert detections[0]["acq_datetime_utc"] == "2014-07-31T11:50:00Z"
    assert all(59.82 < item["latitude"] < 60.02 and 16.0 < item["longitude"] < 16.31 for item in detections)


def test_config_disables_lantmateriet_without_credentials() -> None:
    settings = lantmateriet.Settings(None, None, "https://example.test/{z}/{x}/{y}", "https://example.test/wms", "boundaries")

    layers = server.config(settings)["layers"]

    assert layers["lantmateriet_topowebb"] is False
    assert layers["lantmateriet_fastighet"] is False
    assert layers["lantmateriet_fastighet_layers"] == ""


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers = {"Content-Type": "image/png"}

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_lantmateriet_proxy_authenticates_and_forwards_only_getmap() -> None:
    settings = lantmateriet.Settings("user", "secret", "https://lm.test/topowebb/{z}/{y}/{x}.png", "https://lm.test/wms?x=1", "gränser")
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(b"png")

    with patch("app.backend.lantmateriet.urlopen", side_effect=fake_urlopen):
        assert lantmateriet.topowebb_tile(settings, 10, 560, 290) == (b"png", "image/png")
        lantmateriet.fastighet_map(settings, {"request": "GetMap", "layers": "gränser", "bbox": "1,2,3,4"})

    assert requests[0].full_url == "https://lm.test/topowebb/10/290/560.png"
    assert requests[0].headers["Authorization"] == "Basic " + base64.b64encode(b"user:secret").decode()
    assert requests[1].full_url.startswith("https://lm.test/wms?x=1&REQUEST=GetMap")
    with pytest.raises(ValueError):
        lantmateriet.fastighet_map(settings, {"request": "GetFeatureInfo"})
    with pytest.raises(ValueError):
        lantmateriet.fastighet_map(settings, {"request": "GetMap", "url": "https://elsewhere.test"})


def test_lantmateriet_errors_do_not_reveal_credentials() -> None:
    settings = lantmateriet.Settings("user", "secret", "https://lm.test/{z}/{x}/{y}", None)
    error = HTTPError("https://lm.test/1/2/3", 401, "Unauthorized", {}, None)

    with patch("app.backend.lantmateriet.urlopen", side_effect=error):
        with pytest.raises(lantmateriet.UpstreamError) as raised:
            lantmateriet.topowebb_tile(settings, 1, 2, 3)

    assert raised.value.status == 401
    assert "secret" not in repr(raised.value)
    with pytest.raises(lantmateriet.NotConfigured):
        lantmateriet.fastighet_map(settings, {"request": "GetMap"})


@pytest.fixture()
def base_url():
    handler = type("TestHandler", (server.Handler,), {"settings": lantmateriet.Settings(None, None, None, None)})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url: str) -> tuple[int, bytes]:
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def test_http_api_serves_gui_data_and_refuses_paths_outside_the_frontend(base_url: str) -> None:
    status, body = get(f"{base_url}/api/hotspots")
    collection = json.loads(body)
    assert status == 200 and len(collection["features"]) == 1727 and collection["daily"]
    assert get(f"{base_url}/")[0] == 200
    assert get(f"{base_url}/vendor/leaflet-1.9.4/leaflet.js")[0] == 200
    assert get(f"{base_url}/%2e%2e/AGENTS.md")[0] == 404
    assert get(f"{base_url}/lm/topowebb/1/2/3.png") == (503, b'{"error": "lantmateriet_not_configured", "service": "topowebb"}')
    terrain = json.loads(get(f"{base_url}/api/layers/terrain")[1])
    assert terrain["metadata"]["attribution"].startswith("© OpenStreetMap contributors")


def test_http_stream_sends_server_sent_events_until_the_end(base_url: str) -> None:
    with patch.object(server, "TICK_SECONDS", 0.0), patch("app.backend.server.time.sleep"):
        status, body = get(f"{base_url}/api/stream?speed=345600&from=2014-08-09T00:00:00Z")

    text = body.decode("utf-8")
    assert status == 200
    assert text.count("event: hotspot") == 4  # two VIIRS detections each on 2014-08-09 and 2014-08-10
    assert text.rstrip().endswith('data: {"sim_time_utc": "2014-08-15T00:00:00Z"}')
    assert get(f"{base_url}/api/stream?speed=fast")[0] == 400
