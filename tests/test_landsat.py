"""Tests for the Landsat 8 scene: the GDAL commands of tools/fetch_landsat_scene.py
(no network or Docker), the layer description and the /landsat/ endpoint."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from app.backend import landsat, lantmateriet, server
from tools import fetch_landsat_scene as fetch

PNG = b"\x89PNG\r\n\x1a\nfake"


def test_reflectance_is_turned_into_level2_numbers() -> None:
    assert fetch.dn_for(0.0) == 7273 and fetch.dn_for(0.25) == 16364 and fetch.dn_for(0.45) == 23636


def test_the_script_cuts_the_map_area_and_writes_both_composites() -> None:
    urls = {band: f"https://example.org/{band}.TIF?token=abc" for band in ["red", "green", "blue", "nir08", "swir22"]}
    script = fetch.warp_script(urls, "SCENE")
    assert script.count("gdalwarp ") == 5
    assert "-t_srs EPSG:4326 -te 15.85 59.75 16.45 60.08 -ts 1100 1220" in script
    assert "'/vsicurl/https://example.org/swir22.TIF?token=abc' swir22.tif" in script
    assert "gdalbuildvrt -q -separate natural.vrt red.tif green.tif blue.tif" in script
    assert "gdalbuildvrt -q -separate swir.vrt swir22.tif nir08.tif red.tif" in script
    assert "-scale 7273 16364 1 255 -a_nodata 0 -of PNG natural.vrt SCENE-natural.png" in script
    assert "-scale 7273 23636 1 255 -a_nodata 0 -of PNG swir.vrt SCENE-swir.png" in script
    assert script.splitlines()[-1].startswith("rm -f blue.tif")


def test_docker_verifies_tls_with_the_host_certificates(tmp_path: Path) -> None:
    command = fetch.docker_command("true", tmp_path)
    assert f"{fetch.HOST_CA_BUNDLE}:/etc/ssl/host-ca.crt:ro" in command and "CURL_CA_BUNDLE=/etc/ssl/host-ca.crt" in command
    assert not any("ALLOWED_EXTENSIONS" in part or "SSL_VERIFY" in part or "UNSAFESSL" in part for part in command)
    assert fetch.without_token("open /vsicurl/x.TIF?st=1&sig=abc failed", "st=1&sig=abc") == "open /vsicurl/x.TIF?<token> failed"


def write_scene(directory: Path, images: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SOURCE.json").write_text(json.dumps({
        "scene": "LC08_TEST", "acquired_utc": "2014-08-04T10:06:44Z", "cloud_cover_pct": 1.74,
        "bounds_west_south_east_north": [15.85, 59.75, 16.45, 60.08],
        "images": {"natural": {"file": "LC08_TEST-natural.png"}, "swir": {"file": "LC08_TEST-swir.png"}},
        "citation": "courtesy of the U.S. Geological Survey",
    }), encoding="utf-8")
    for name in images:
        (directory / f"LC08_TEST-{name}.png").write_bytes(PNG)


def test_the_layer_lists_only_images_that_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(landsat, "LANDSAT_DIR", tmp_path / "landsat")
    assert landsat.layer() is None
    write_scene(tmp_path / "landsat", ["swir"])
    layer = landsat.layer()
    assert layer["images"] == {"swir": "/landsat/LC08_TEST-swir.png"}
    assert layer["bounds"] == [[59.75, 15.85], [60.08, 16.45]] and layer["acquired_utc"] == "2014-08-04T10:06:44Z"
    assert layer["label"] == "Landsat 8 OLI 2014-08-04 10:06 UTC – riktig satellitbild"
    write_scene(tmp_path / "landsat", [])
    for name in ["natural", "swir"]:
        (tmp_path / "landsat" / f"LC08_TEST-{name}.png").unlink(missing_ok=True)
    assert landsat.layer() is None


@pytest.fixture()
def base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(landsat, "LANDSAT_DIR", tmp_path / "landsat")
    write_scene(tmp_path / "landsat", ["natural", "swir"])
    (tmp_path / "secret.png").write_bytes(PNG)
    handler = type("TestHandler", (server.Handler,), {"settings": lantmateriet.Settings(None, None, None, None)})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def status(url: str) -> int:
    try:
        with urlopen(url, timeout=10) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


def test_the_images_are_served_and_nothing_else(base_url: str) -> None:
    with urlopen(f"{base_url}/landsat/LC08_TEST-swir.png", timeout=10) as response:
        assert response.read() == PNG and response.headers["Content-Type"] == "image/png"
    with urlopen(f"{base_url}/api/config", timeout=10) as response:
        assert json.loads(response.read())["layers"]["landsat"]["scene"] == "LC08_TEST"
    for path in ["/landsat/SOURCE.json", "/landsat/%2e%2e/secret.png", "/landsat/missing.png"]:
        assert status(base_url + path) == 404, path
