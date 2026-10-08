"""Tests for the map adapters: the 2D and 3D maps implement the same interface for panel.js,
and the 3D helpers are checked with Node.js (stubbed Cesium) when it is installed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
# The calls panel.js makes on state.map.
INTERFACE = {
    "wantsLabels", "addAttribution", "addTerrain", "addLabels", "addStations", "clearHotspots", "addHotspot",
    "hotspotCount", "restyleHotspots", "setupWind", "showWind", "setupForecast", "drawForecast", "finish", "showGodView", "drawSyntheticSensors", "focusOn", "drawQueryResult", "setCategoryVisible", "drawSatellites", "flashSatellite", "highlightSatellite", "onContextMenu", "showSpaceView", "setupLandsat", "showLandsat",
    "labelStations", "markRain", "addWms", "onWmsChange", "setupRadar", "showRadar", "setupEms", "drawEms",
    "setBaseMap",
}


def adapter_methods(name: str) -> set[str]:
    source = (FRONTEND / name).read_text(encoding="utf-8")
    return set(re.findall(r"^ {4}(\w+)(?:\(|: )", source, flags=re.MULTILINE))


def test_panel_uses_only_the_interface_and_both_maps_implement_it() -> None:
    used = set(re.findall(r"state\.map\.(\w+)\(", (FRONTEND / "panel.js").read_text(encoding="utf-8")))
    assert used == INTERFACE
    assert INTERFACE <= adapter_methods("map2d.js")
    assert INTERFACE <= adapter_methods("map3d.js")


def node(expression: str) -> object:
    stub = """
const vm = require("vm"), fs = require("fs");
const context = {
  Cesium: { HeightReference: { CLAMP_TO_GROUND: 1 }, Math: { toRadians: (d) => d * Math.PI / 180 } },
  document: { createElement: () => ({ set textContent(t) { this.innerHTML = t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); } }) },
  encodeURIComponent, Map, Number,
};
vm.createContext(context);
for (const file of ["wind_barbs.js", "map3d.js"]) vm.runInContext(fs.readFileSync(DIR + file, "utf8"), context);
"""
    code = f"const DIR = {json.dumps(str(FRONTEND) + '/')};{stub}console.log(JSON.stringify(vm.runInContext({json.dumps(expression)}, context)));"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_label_limits_shrink_with_the_leaflet_zoom() -> None:
    town, farm = node("[distanceForZoom(7), distanceForZoom(13)]")
    assert 250_000 < town < 400_000
    assert 4_000 < farm < 6_000


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_rotation_turns_clockwise_from_north_like_the_2d_map() -> None:
    east, south = node("[northRotation(90), northRotation(180)]")
    assert east == pytest.approx(-1.5708, abs=1e-4)
    assert south == pytest.approx(-3.1416, abs=1e-4)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_barb_images_are_stand_alone_svg_with_inlined_styles_and_cached() -> None:
    image, same, calm = node("[barbImage(6.8), barbImage(6.9), barbImage(0.2)]")
    svg = unquote(image.split(",", 1)[1])
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" ')
    assert "<style>" in svg and "M0,15 L0,-15" in svg
    assert image == same and image != calm


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_osm_names_are_escaped_before_they_reach_the_info_box() -> None:
    assert node('escapeText("<b>Sjö & Å</b>")') == "&lt;b&gt;Sjö &amp; Å&lt;/b&gt;"


def test_the_3d_wms_layers_ask_for_maps_only_as_the_backend_forwards() -> None:
    source = (FRONTEND / "map3d.js").read_text(encoding="utf-8")
    provider = source[source.index("new Cesium.WebMapServiceImageryProvider("):]
    assert "enablePickFeatures: false" in provider[:provider.index("}));")]  # a click would send GetFeatureInfo, refused with 400
