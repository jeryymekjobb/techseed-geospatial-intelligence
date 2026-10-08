"""Tests for mission control's base maps (app/frontend/basemaps.js, the base maps in
/api/config and the base_maps command of app/backend/server.py)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.backend import lantmateriet, offline_tiles, server

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
    assert caption(None) == "Visas: Karta – ingen baskarta vald i mission control (i 3D Natural Earth II)"


def test_the_config_lists_the_base_maps_that_can_be_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(offline_tiles, "available", lambda: True)
    with_topowebb = lantmateriet.Settings("user", "secret", "https://example.invalid/topowebb", None)
    assert with_topowebb.topowebb_enabled
    assert [item["id"] for item in server.base_maps(with_topowebb)] == ["topowebb", "offline", "online"]
    monkeypatch.setattr(offline_tiles, "available", lambda: False)
    assert [item["id"] for item in server.base_maps(lantmateriet.Settings(None, None, None, None))] == ["online"]
