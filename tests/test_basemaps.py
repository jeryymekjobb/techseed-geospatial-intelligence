"""Tests for mission control's base maps (app/frontend/basemaps.js, the base maps in
/api/config and the base_maps command of app/backend/server.py)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backend import lantmateriet, meteosat, meteosat_cth, meteosat_frm, offline_tiles, server

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
ALL = [{"id": "topowebb", "label": "t", "only_2d": True}, {"id": "offline", "label": "o", "only_2d": False},
       {"id": "online", "label": "n", "only_2d": False}]


def basemaps(expression: str) -> object:
    code = (f"const m = require({json.dumps(str(FRONTEND / 'basemaps.js'))}); const all = {json.dumps(ALL)};"
            f"console.log(JSON.stringify({expression}));")
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_each_map_shows_the_first_ticked_base_map_it_has_and_the_default_is_today_s() -> None:
    assert basemaps("[m.defaultBaseMaps(all), m.defaultBaseMaps(all.filter((i) => i.id !== 'offline')), m.defaultBaseMaps([])]") == [
        ["offline"], ["online"], []]
    assert basemaps("[m.baseMapsShown(null, all), m.baseMapsShown(['online', 'topowebb'], all), m.baseMapsShown([], all)]") == [
        ["offline"], ["topowebb", "online"], []]
    # Topowebb only in 2D: the 3D globe takes the next ticked, or Natural Earth II alone (null).
    assert basemaps("[m.baseMapFor(['topowebb', 'online'], all, '2d'), m.baseMapFor(['topowebb', 'online'], all, '3d'),"
                    " m.baseMapFor(['topowebb'], all, '3d'), m.baseMapFor([], all, '2d')]") == ["topowebb", "online", None, None]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_caption_names_the_base_map_shown() -> None:
    def caption(base_map: object) -> str:
        code = (f"const m = require({json.dumps(str(FRONTEND / 'landsat.js'))});"
                f"console.log(m.viewCaption({{ scene: null, image: null, reason: 'off', choice: ['radar'], baseMap: {json.dumps(base_map)},"
                " mapData: {source: 'OpenStreetMap', date_utc: '2026-10-02T00:00:00Z'}, offlineTiles: true, formatTime: (t) => t, formatDate: (t) => t.slice(0, 10) }));")
        return subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout.strip()
    assert caption("offline") == "Visas: Karta – OpenStreetMap, data från 2026-10-02"
    assert caption("online") == "Visas: Karta – OpenStreetMap online"
    assert caption("topowebb") == "Visas: Karta – Lantmäteriet topowebb"
    assert caption("kommun") == "Visas: Karta – Sundsvalls kommun"
    assert caption(None) == "Visas: Karta – ingen baskarta vald i mission control (i 3D Natural Earth II)"


def test_the_config_lists_the_base_maps_that_can_be_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(offline_tiles, "available", lambda: True)
    with_topowebb = lantmateriet.Settings("user", "secret", "https://example.invalid/topowebb", None)
    assert with_topowebb.topowebb_enabled
    assert [item["id"] for item in server.base_maps(with_topowebb)] == ["topowebb", "offline", "online"]
    monkeypatch.setattr(offline_tiles, "available", lambda: False)
    assert [item["id"] for item in server.base_maps(lantmateriet.Settings(None, None, None, None))] == ["online"]


def test_the_map_layers_mission_control_lists_are_the_names_both_maps_give_them(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every fixed name in the catalogue is a layer name in the map that has it (map2d.js, map3d.js).
    sources = {dimension: (FRONTEND / f"map{dimension}.js").read_text(encoding="utf-8") for dimension in ("2d", "3d")}
    for item in server.map_layers(lantmateriet.Settings(None, None, None, None)):
        if "(modell)" in item["name"] and item["name"] not in ("Prognos (modell)",) or item["name"].startswith("Satelliter ("):
            continue  # WMS titles and the year are filled in at run time
        if item["name"] == offline_tiles.OVERLAY_LABEL:
            continue  # both maps take the road overlay's name from config.layers.road_overlay
        if item["name"] in (meteosat.LABEL, meteosat_frm.LABEL, meteosat_cth.LABEL):
            continue  # both maps take Meteosat's names from config.layers.meteosat and meteosat_frm
        for dimension in ("2d", "3d"):
            if item[f"default_{dimension}"] is not None:
                assert f'"{item["name"]}"' in sources[dimension], (item["name"], dimension)


def test_the_map_layer_catalog_assigns_filter_categories_including_radar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server.scenario, "WILDFIRE", True)
    monkeypatch.setattr(server.scenario, "TERRAIN_FILE", SimpleNamespace(is_file=lambda: False))
    monkeypatch.setattr(server.scenario, "WIND_FILE", SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(server, "radar", SimpleNamespace(layer=lambda: object()))
    monkeypatch.setattr(server, "satellites", SimpleNamespace(satellites=lambda: {"available": True}))
    monkeypatch.setattr(server, "ems", SimpleNamespace(perimeters=lambda: None))
    monkeypatch.setattr(server, "wms", SimpleNamespace(sources=lambda: []))

    items = server.map_layers(lantmateriet.Settings(None, None, None, None))
    categories = {item["name"]: item["category"] for item in items}
    assert categories["Hotspots"] == "space"
    assert categories[f"Satelliter ({server.scenario.PLAYBACK_START.year})"] == "space"
    assert categories["Syntetiska sensorer"] == "iot"
    assert categories["Svar på fråga"] == "infrastructure"
    assert categories["Vind (ERA5-Land)"] == "weather"
    assert categories["Nederbörd (SMHI radar)"] == "weather"


def test_the_weather_filter_hides_radar_and_restores_each_layer_choice() -> None:
    map2d = (FRONTEND / "map2d.js").read_text(encoding="utf-8")
    map3d = (FRONTEND / "map3d.js").read_text(encoding="utf-8")
    weather_2d = map2d.split('if (category === "weather") {', 1)[1].split("return;", 1)[0]
    weather_3d = map3d.split('if (category === "weather") {', 1)[1].split("return;", 1)[0]

    assert "setMapLayerVisible(radarOverlay, visible && radarVisible)" in weather_2d
    assert "windVisible" in weather_2d
    assert "radarLayer.show = visible && radarVisible" in weather_3d
    assert "windVisible" in weather_3d


def test_the_panel_s_choices_follow_the_kind_of_incident() -> None:
    import os
    import sys
    code = ("from app.backend import server; c = server.panel_choices();"
            "print(sorted(c), [o[0] for o in c.get('horizon', {}).get('options', [])], c.get('hydro_station', {}).get('default'))")
    def run(name: str) -> str:
        return subprocess.run([sys.executable, "-c", code], cwd=FRONTEND.parents[1], env={**os.environ, "TECHSEED_SCENARIO": name},
                              capture_output=True, text=True, check=True).stdout.strip()
    assert run("vastmanland2014") in ("['horizon', 'weather_station'] ['3', '6', '12', '24'] None", "['horizon'] ['3', '6', '12', '24'] None")
    skane = run("skane2024")  # data/ is not in the repository: without it there are no stations
    assert skane in ("['hydro_station', 'rain_station'] [] 2176:3", "[] [] None")
