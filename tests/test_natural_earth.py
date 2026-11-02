"""Tests for the 2D map's world outside the offline map (app/frontend/natural_earth.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")


def run(expression: str):
    code = (f"const m = require({json.dumps(str(FRONTEND / 'natural_earth.js'))});"
            f"console.log(JSON.stringify({expression}));")
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_web_mercator_rows_are_latitudes() -> None:
    assert run("m.mercatorLatitude(0.5)") == 0
    assert run("m.mercatorLatitude(0)") == pytest.approx(85.0511, abs=1e-3)
    assert run("m.mercatorLatitude(1)") == pytest.approx(-85.0511, abs=1e-3)
    pixel = run("m.mercatorPixel(m.mercatorLatitude(0.3), 0, 0, 256)")
    assert pixel["x"] == 128 and pixel["y"] == pytest.approx(0.3 * 256)


@needs_node
def test_a_tile_is_cut_at_the_map_area() -> None:
    bounds = "[[62.2, 17.0], [62.6, 17.6]]"
    # At zoom 4 the whole map area lies in one tile, a few pixels of it.
    clip = run(f"m.tileClip({{x: 8, y: 4, z: 4}}, 256, {bounds})")
    assert clip and 0 < clip["width"] < 15 and 0 < clip["height"] < 15
    # A tile beside it has none of the map area.
    assert run(f"m.tileClip({{x: 9, y: 4, z: 4}}, 256, {bounds})") is None
    # A tile well inside the map area keeps all of it.
    inside = run(f"(() => {{ const p = m.mercatorPixel(62.4, 17.3, 12, 256);"
                 f" return m.tileClip({{x: Math.floor(p.x / 256), y: Math.floor(p.y / 256), z: 12}}, 256, {bounds}); }})()")
    assert inside == {"left": 0, "top": 0, "width": 256, "height": 256}


def test_the_2d_map_loads_natural_earth_and_cuts_the_offline_map() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert html.index('src="/natural_earth.js"') < html.index('src="/map2d.js"')
    map2d = (FRONTEND / "map2d.js").read_text(encoding="utf-8")
    assert "naturalEarthLayer(" in map2d
    assert 'clippedTileLayer("/tiles/{z}/{x}/{y}.png", config.map_bounds' in map2d
    source = FRONTEND / "vendor" / "cesium-1.146.0" / "Assets" / "Textures" / "NaturalEarthII" / "2"
    if not source.parent.is_dir():
        pytest.skip("needs Cesium's own Natural Earth II (tools/fetch_web_vendor.py)")
    assert len(list(source.glob("*/*.jpg"))) == 32
