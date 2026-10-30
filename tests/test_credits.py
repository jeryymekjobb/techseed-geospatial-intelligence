"""Tests for the map's source credits out of the map picture (app/frontend/credits.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"


def listed(text: str) -> str:
    code = (f"const m = require({json.dumps(str(FRONTEND / 'credits.js'))});"
            f"console.log(JSON.stringify(m.listedCredit({json.dumps(text)})));")
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_openstreetmaps_variants_are_one_source_in_the_list() -> None:
    link = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
    variants = {listed(text) for text in (link, "© OpenStreetMap contributors", "© OpenStreetMap contributors (ODbL)")}
    assert len(variants) == 1 and "(ODbL)" in variants.pop()
    assert listed("© Sundsvalls kommun") == "© Sundsvalls kommun"


def test_both_maps_draw_their_credits_through_credits_js() -> None:
    for page in ("index.html", "3d.html"):
        html = (FRONTEND / page).read_text(encoding="utf-8")
        assert html.index('src="/credits.js"') < html.index('src="/panel.js"')
    map2d = (FRONTEND / "map2d.js").read_text(encoding="utf-8")
    assert "attributionControl: false" in map2d and "creditBox(this._container)" in map2d
    map3d = (FRONTEND / "map3d.js").read_text(encoding="utf-8")
    assert 'viewer.bottomContainer.style.display = "none"' in map3d and "creditBox()" in map3d
    for source in (map2d, map3d):
        assert "setShortCredits(municipalMaps.filter" in source
    panel = (FRONTEND / "panel.js").read_text(encoding="utf-8")
    assert panel.count("creditList()") == 2  # the summary and the closing view
