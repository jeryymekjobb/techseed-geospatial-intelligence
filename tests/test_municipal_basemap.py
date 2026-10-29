"""Tests for the municipality's map kept locally as a base map (tools/fetch_municipal_basemap.py,
app/backend/municipal_basemap.py and its route in app/backend/server.py)."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from PIL import Image

from app.backend import lantmateriet, municipal_basemap, offline_tiles, server
from app.backend.scenario_engine import ScenarioEngine
from tools import fetch_municipal_basemap as fetch

BASEMAP = {"url": "https://example.invalid/wms", "layer": "Kartan", "label": "Sundsvalls kommun (Kartan)", "attribution": "Karta © test"}
BBOX = (16.9, 62.15, 17.8, 62.62)


def test_the_tiles_cover_the_box_and_the_blocks_hold_them() -> None:
    assert fetch.tile_range((-180.0, -85.0, 179.99, 85.0), 1) == (0, 0, 1, 1)
    x0, y0, x1, y1 = fetch.tile_range(BBOX, 12)
    assert (x0, y0, x1, y1) == (2240, 1127, 2250, 1138)
    blocks = fetch.meta_tiles(BBOX, 12)
    held = {tile for mx, my in blocks for tile in fetch.cut_positions(12, mx, my, (x0, y0, x1, y1))}
    assert held == {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    assert all(mx % fetch.META == 0 and my % fetch.META == 0 for mx, my in blocks)


def test_a_block_is_asked_with_its_margin_and_cut_into_tiles() -> None:
    url = fetch.getmap_url("https://example.invalid/wms", "Kartan", 1, 0, 0)
    side = fetch.META * fetch.TILE_PX + 2 * fetch.MARGIN_PX
    assert f"WIDTH={side}" in url and "CRS=EPSG%3A3857" in url and "LAYERS=Kartan" in url
    image = Image.new("RGBA", (side, side))
    for dx in range(fetch.META):  # each tile's top-left pixel says which tile it is
        for dy in range(fetch.META):
            image.putpixel((fetch.MARGIN_PX + dx * fetch.TILE_PX, fetch.MARGIN_PX + dy * fetch.TILE_PX), (dx, dy, 7, 255))
    tiles = fetch.cut(image, 5, 8, 4, (9, 4, 10, 6))
    assert sorted(tiles) == [(9, 4), (9, 5), (9, 6), (10, 4), (10, 5), (10, 6)]
    assert tiles[(10, 6)].getpixel((0, 0)) == (2, 2, 7, 255) and tiles[(10, 6)].size == (256, 256)


def test_the_fetch_writes_the_tiles_and_its_source_and_a_second_run_asks_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch.scenario, "MUNICIPAL_BASEMAP", BASEMAP)
    monkeypatch.setattr(fetch.scenario, "MUNICIPAL_BASEMAP_BBOX", BBOX)
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)
    side = fetch.META * fetch.TILE_PX + 2 * fetch.MARGIN_PX
    asked: list[str] = []
    monkeypatch.setattr(fetch, "fetch_image", lambda url: asked.append(url) or Image.new("RGBA", (side, side), (200, 220, 200, 255)))
    assert fetch.main(["--min-zoom", "8", "--max-zoom", "10", "--out", str(tmp_path)]) == 0
    assert len(asked) == 4 and len(list(tmp_path.rglob("*.png"))) == 2 + 6 + 12
    source = json.loads((tmp_path / "SOURCE.json").read_text(encoding="utf-8"))
    assert (source["layer"], source["min_zoom"], source["max_zoom"], source["bbox_west_south_east_north"]) == ("Kartan", 8, 10, list(BBOX))
    asked.clear()
    assert fetch.main(["--min-zoom", "8", "--max-zoom", "10", "--out", str(tmp_path)]) == 0
    assert asked == []


def test_a_map_white_outside_the_municipality_keeps_its_white_transparent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch.scenario, "MUNICIPAL_BASEMAP", {**BASEMAP, "white_outside": True})
    monkeypatch.setattr(fetch.scenario, "MUNICIPAL_BASEMAP_BBOX", BBOX)
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)
    side = fetch.META * fetch.TILE_PX + 2 * fetch.MARGIN_PX
    image = Image.new("RGBA", (side, side), (255, 255, 255, 255))
    image.paste((250, 250, 250, 255), (0, side - fetch.MARGIN_PX - 100, side, side))  # the municipality: near white stays
    monkeypatch.setattr(fetch, "fetch_image", lambda url: image)
    assert fetch.main(["--min-zoom", "8", "--max-zoom", "8", "--out", str(tmp_path)]) == 0
    alphas = {pixel[3] for path in tmp_path.rglob("*.png") for pixel in Image.open(path).getdata()}
    assert alphas == {0, 255} and json.loads((tmp_path / "SOURCE.json").read_text(encoding="utf-8"))["white_transparent"]
    # Tiles fetched before are made transparent where white without asking the service.
    old = tmp_path / "9" / "1" / "1.png"
    old.parent.mkdir(parents=True)
    Image.new("RGBA", (4, 4), (255, 255, 255, 255)).save(old)
    monkeypatch.setattr(fetch, "fetch_image", lambda url: pytest.fail("asked the service"))
    assert fetch.main(["--clear-white", "--out", str(tmp_path)]) == 0
    assert {pixel[3] for pixel in Image.open(old).getdata()} == {0}


def test_a_failed_request_leaves_no_source_so_the_map_is_not_shown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch.scenario, "MUNICIPAL_BASEMAP", BASEMAP)
    monkeypatch.setattr(fetch.scenario, "MUNICIPAL_BASEMAP_BBOX", BBOX)

    def refused(url: str) -> Image.Image:
        raise OSError("refused")
    monkeypatch.setattr(fetch, "fetch_image", refused)
    assert fetch.main(["--min-zoom", "8", "--max-zoom", "8", "--out", str(tmp_path)]) == 1
    assert not (tmp_path / "SOURCE.json").exists()


@pytest.fixture
def fetched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(municipal_basemap.scenario, "MUNICIPAL_BASEMAP", BASEMAP)
    monkeypatch.setattr(municipal_basemap.scenario, "MUNICIPAL_BASEMAP_DIR", tmp_path)
    (tmp_path / "SOURCE.json").write_text(json.dumps({"min_zoom": 8, "max_zoom": 16, "bbox_west_south_east_north": list(BBOX)}))
    (tmp_path / "12" / "2245").mkdir(parents=True)
    (tmp_path / "12" / "2245" / "1130.png").write_bytes(b"\x89PNG tile")
    return tmp_path


def test_the_backend_offers_the_map_only_once_fetched_and_first_among_the_base_maps(fetched: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(offline_tiles, "available", lambda: True)
    layer = municipal_basemap.layer()
    assert layer == {"id": "kommun", "label": "Sundsvalls kommun (Kartan)", "attribution": "Karta © test",
                     "url": "/basemap/kommun/{z}/{x}/{y}.png", "min_zoom": 8, "max_zoom": 16, "bounds": [[62.15, 16.9], [62.62, 17.8]]}
    assert [item["id"] for item in server.base_maps(lantmateriet.Settings(None, None, None, None))] == ["kommun", "offline", "online"]
    (fetched / "SOURCE.json").unlink()
    assert municipal_basemap.layer() is None
    assert [item["id"] for item in server.base_maps(lantmateriet.Settings(None, None, None, None))] == ["offline", "online"]


def test_a_scenario_without_the_municipality_s_map_has_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(municipal_basemap.scenario, "MUNICIPAL_BASEMAP", None)
    monkeypatch.setattr(municipal_basemap.scenario, "MUNICIPAL_BASEMAP_DIR", tmp_path)
    (tmp_path / "SOURCE.json").write_text(json.dumps({"min_zoom": 8, "max_zoom": 16, "bbox_west_south_east_north": list(BBOX)}))
    assert municipal_basemap.layer() is None and municipal_basemap.tile(12, 2245, 1130) is None


def test_the_route_serves_fetched_tiles_and_nothing_else(fetched: Path) -> None:
    (fetched.parent / "secret.png").write_bytes(b"secret")
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None), "control_token": None,
        "engine": ScenarioEngine(datetime(2014, 7, 31, tzinfo=timezone.utc), datetime(2014, 8, 15, tzinfo=timezone.utc)),
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/basemap/kommun"
    try:
        with urlopen(f"{base}/12/2245/1130.png", timeout=10) as response:
            assert response.read() == b"\x89PNG tile" and response.headers["Content-Type"] == "image/png"
        for path in ("/12/2245/1131.png", "/12/2245/x.png", "/../../secret.png", "/12/2245/1130.jpg", "/40/1/1.png"):
            with pytest.raises(HTTPError) as error:
                urlopen(f"{base}{path}", timeout=10)
            assert error.value.code == 404, path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_scenario_may_have_several_municipal_maps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Västerås stad's map and aerial photo; the photo has no names of its own. Mission control takes ids of letters only.
    maps = [{**BASEMAP, "id": "karta", "label": "Västerås stad (karta)", "dir": tmp_path / "karta"},
            {**BASEMAP, "id": "flygfoto", "label": "Västerås stad (flygfoto)", "dir": tmp_path / "flygfoto", "names": False}]
    monkeypatch.setattr(municipal_basemap.scenario, "MUNICIPAL_BASEMAPS", maps)
    monkeypatch.setattr(offline_tiles, "available", lambda: False)
    assert municipal_basemap.layers() == [] and municipal_basemap.layer() is None
    for item in maps:
        (item["dir"] / "12" / "2245").mkdir(parents=True)
        (item["dir"] / "12" / "2245" / "1130.png").write_bytes(item["id"].encode())
        (item["dir"] / "SOURCE.json").write_text(json.dumps({"min_zoom": 8, "max_zoom": 16, "bbox_west_south_east_north": list(BBOX)}), encoding="utf-8")
    layers = municipal_basemap.layers()
    assert [(item["id"], item["url"], item["names"]) for item in layers] == [
        ("karta", "/basemap/karta/{z}/{x}/{y}.png", True), ("flygfoto", "/basemap/flygfoto/{z}/{x}/{y}.png", False)]
    assert municipal_basemap.layer()["id"] == "karta"
    assert municipal_basemap.tile(12, 2245, 1130, "flygfoto") == b"flygfoto" and municipal_basemap.tile(12, 2245, 1130, "x") is None
    assert [item["id"] for item in server.base_maps(lantmateriet.Settings(None, None, None, None))] == ["karta", "flygfoto", "online"]


def test_each_of_several_maps_is_an_optional_step_and_check() -> None:
    from types import SimpleNamespace

    from tools import fetch_scenario, startup_check
    plan = {step.key: step for step in fetch_scenario.steps("vasteras-sep2023")}
    assert all(plan[f"municipal-basemap-{name}"].optional for name in ("vasteraskarta", "vasterasgra", "vasterasflygfoto"))
    assert plan["municipal-basemap-vasterasgra"].command[-2:] == ["--map", "vasterasgra"]
    settings = SimpleNamespace(TERRAIN_FILE=Path("/x/terrain.json"), TARGETS_FILE=Path("/x/targets.json"), WIND_FILE=None,
                               TLE_DIR=Path("/x/tle"), TLE_FILE_NAME="tle.json", TLE_SATELLITES={}, TILES_FILE="demo.mbtiles",
                               FIRMS_FILES=[], MUNICIPAL_BASEMAPS=[{"id": "karta", "label": "Västerås stad (karta)", "dir": Path("/x/karta")}])
    check = next(item for item in startup_check.data_checks(settings, Path("/x")) if item.name.endswith("karta/SOURCE.json"))
    assert not check.required and "optional" in check.detail
