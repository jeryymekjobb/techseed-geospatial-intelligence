"""Tests for the offline tile proxy and the label layer (no tile service needed)."""

from __future__ import annotations

import pytest

from app.backend import offline_tiles, server


def test_tile_coordinates_are_checked_and_an_absent_service_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OFFLINE_TILES_URL", "http://127.0.0.1:9/{z}/{x}/{y}.png")  # nothing listens on port 9

    with pytest.raises(ValueError):
        offline_tiles.tile(3, 8, 0)
    with pytest.raises(offline_tiles.Unavailable):
        offline_tiles.tile(0, 0, 0, timeout=0.5)


def test_availability_is_probed_at_most_every_30_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(offline_tiles, "tile", lambda *args, **kwargs: calls.append(args) or (b"png", "image/png"))
    monkeypatch.setattr(offline_tiles, "_probe", {"at": -1e9, "ok": False})

    assert offline_tiles.available() and offline_tiles.available()
    assert len(calls) == 1


def test_the_road_overlay_is_the_same_tiles_in_the_overlay_style(monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    from pathlib import Path

    monkeypatch.delenv("OFFLINE_TILES_URL", raising=False)
    assert offline_tiles.url_template(overlay=True) == "http://127.0.0.1:8081/styles/techseed-overlay/256/{z}/{x}/{y}.png"
    monkeypatch.setattr(offline_tiles, "available", lambda: True)
    assert offline_tiles.overlay_layer(False) is None
    assert offline_tiles.overlay_layer(True)["label"] == "Vägnummer och järnvägstunnlar (OSM)"
    # The overlay draws only the main style's railway tunnels and road numbers, on a transparent background.
    tiles = Path(offline_tiles.__file__).resolve().parents[2] / "tiles"
    overlay = json.loads((tiles / "styles" / "techseed-overlay.json").read_text(encoding="utf-8"))
    main = {layer["id"]: layer for layer in json.loads((tiles / "styles" / "techseed.json").read_text(encoding="utf-8"))["layers"]}
    assert [layer["id"] for layer in overlay["layers"]] == ["railway-tunnel", "road-ref-major", "road-ref-minor"]
    assert all(layer == main[layer["id"]] for layer in overlay["layers"])
    assert "techseed-overlay" in json.loads((tiles / "config.json").read_text(encoding="utf-8"))["styles"]


def test_every_scenario_has_the_road_overlay_layer() -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    code = ("from app.backend import offline_tiles, scenario, server, lantmateriet\n"
            "offline_tiles.available = lambda: True\n"
            "names = [item['name'] for item in server.map_layers(lantmateriet.Settings(None, None, None, None))]\n"
            "print(scenario.ROAD_OVERLAY, offline_tiles.OVERLAY_LABEL in names)")
    root = Path(offline_tiles.__file__).resolve().parents[2]
    for name, expected in (("sundsvall2026", "True True"), ("kramfors2026", "True True")):
        out = subprocess.run([sys.executable, "-c", code], cwd=root, env={**os.environ, "TECHSEED_SCENARIO": name},
                             capture_output=True, text=True, check=True).stdout.strip()
        assert out == expected, (name, out)


def test_labels_hold_places_and_lakes_with_zoom_limits() -> None:
    features = server.labels()["features"]
    by_name = {feature["properties"]["name"]: feature["properties"] for feature in features}

    assert by_name["Virsbo"]["kind"] in server.LABEL_MIN_ZOOM
    assert by_name["Åmänningen"]["kind"] == "lake" and by_name["Åmänningen"]["min_zoom"] == 9
    assert all(feature["geometry"]["type"] == "Point" for feature in features)
    assert server._ring_area_km2([[16.0, 60.0], [16.0 + 1 / 55.66, 60.0], [16.0 + 1 / 55.66, 60.0 + 1 / 110.54], [16.0, 60.0 + 1 / 110.54]]) == pytest.approx(1.0, rel=0.01)


def test_offline_tile_build_commands() -> None:
    from pathlib import Path

    from tools import build_offline_tiles as build

    source = Path("/repo/data/osm/sweden-latest.osm.pbf")
    extract = build.extract_command(source, source.parent / "firemap-area.osm.pbf", "15.5,59.55,16.8,60.3")
    assert extract[:4] == ["docker", "run", "--rm", "-v"] and "osmium extract -b 15.5,59.55,16.8,60.3" in extract[-1]
    area = build.DATA / "osm" / "firemap-area.osm.pbf"
    tilemaker = build.tilemaker_command(area, build.DATA / "tiles" / "vastmanland.mbtiles", "15.5,59.55,16.8,60.3")
    assert tilemaker[tilemaker.index("--input") + 1] == "/data/osm/firemap-area.osm.pbf"
    assert tilemaker[tilemaker.index("--output") + 1] == "/data/tiles/vastmanland.mbtiles"
    assert tilemaker[tilemaker.index("--process") + 1] == "/techseed/process-techseed.lua"
    assert f"{build.REPO_ROOT / 'tiles'}:/techseed:ro" in tilemaker
    lua = (build.REPO_ROOT / "tiles" / "process-techseed.lua").read_text(encoding="utf-8")
    assert 'dofile("resources/process-openmaptiles.lua")' in lua and "RAILWAY_MINZOOM = 8" in lua
