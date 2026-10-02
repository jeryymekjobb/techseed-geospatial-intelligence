"""Tests for the GLO-30 fetcher, the terrain build command and the /terrain/ endpoint (no network or Docker needed)."""

from __future__ import annotations

import gzip
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from app.backend import lantmateriet, scenario, server
from tools import build_terrain, fetch_copernicus_dem


def test_tiles_cover_the_map_area_with_glo30_names() -> None:
    assert fetch_copernicus_dem.tiles_for(fetch_copernicus_dem.DEFAULT_BBOX) == [
        "Copernicus_DSM_COG_10_N59_00_E015_00_DEM",
        "Copernicus_DSM_COG_10_N59_00_E016_00_DEM",
        "Copernicus_DSM_COG_10_N60_00_E015_00_DEM",
        "Copernicus_DSM_COG_10_N60_00_E016_00_DEM",
    ]
    assert fetch_copernicus_dem.tile_name(-1, -71) == "Copernicus_DSM_COG_10_S01_00_W071_00_DEM"
    assert fetch_copernicus_dem.tile_url("X").endswith("/X/X.tif")
    with pytest.raises(ValueError):
        fetch_copernicus_dem.tiles_for("16,60,15,59")


def test_the_gui_shows_the_attribution_the_licence_requires() -> None:
    assert scenario.ATTRIBUTION["copernicus_dem"] == fetch_copernicus_dem.ATTRIBUTION


def test_build_script_cuts_the_area_and_writes_mesh_tiles_with_normals() -> None:
    script = build_terrain.build_script(["a.tif", "b.tif"], "15.5,59.55,16.8,60.3")

    assert "gdalbuildvrt -q -te 15.5 59.55 16.8 60.3 /data/terrain/area.vrt /data/dem/a.tif /data/dem/b.tif" in script
    assert "ctb-tile -q -f Mesh -C -N -o /data/terrain" in script
    assert "ctb-tile -q -f Mesh -C -N -l -o /data/terrain" in script


@pytest.fixture()
def terrain_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    terrain = tmp_path / "terrain"
    (terrain / "0" / "0").mkdir(parents=True)
    (terrain / "layer.json").write_text(json.dumps({"format": "quantized-mesh-1.0"}), encoding="utf-8")
    (terrain / "0" / "0" / "0.terrain").write_bytes(gzip.compress(b"mesh"))
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(server, "TERRAIN_DIR", terrain)
    handler = type("TestHandler", (server.Handler,), {"settings": lantmateriet.Settings(None, None, None, None)})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_terrain_endpoint_serves_layer_and_gzipped_tiles(terrain_url: str) -> None:
    with urlopen(f"{terrain_url}/terrain/layer.json", timeout=10) as response:
        assert json.loads(response.read())["format"] == "quantized-mesh-1.0"
    with urlopen(f"{terrain_url}/terrain/0/0/0.terrain?v=1.1.0", timeout=10) as response:
        assert response.headers["Content-Encoding"] == "gzip"
        assert response.headers["Content-Type"].startswith("application/vnd.quantized-mesh")
        assert gzip.decompress(response.read()) == b"mesh"
    with urlopen(f"{terrain_url}/api/config", timeout=10) as response:
        assert json.loads(response.read())["layers"]["terrain3d"] is True


@pytest.mark.parametrize("path", ["/terrain/../secret.json", "/terrain/%2e%2e/secret.json", "/terrain/0/0/1.terrain", "/terrain/0"])
def test_terrain_endpoint_refuses_other_paths(terrain_url: str, path: str) -> None:
    with pytest.raises(HTTPError) as raised:
        urlopen(f"{terrain_url}{path}", timeout=10)
    assert raised.value.code == 404


def test_config_reports_no_terrain_when_it_is_not_built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "TERRAIN_DIR", tmp_path / "missing")

    assert server.config(lantmateriet.Settings(None, None, None, None))["layers"]["terrain3d"] is False
