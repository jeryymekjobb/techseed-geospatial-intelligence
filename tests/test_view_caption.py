"""Tests for the flood's depth legend (app/frontend/flood_legend.js), in Node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")


def node(script: str, expression: str) -> object:
    code = f"const m = require({json.dumps(str(FRONTEND / script))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def test_the_depth_legend_has_the_municipality_s_seven_classes_and_shows_with_a_depth_layer() -> None:
    classes = node("flood_legend.js", "DEPTH_CLASSES")
    assert [(item["color"], item["text"]) for item in classes] == [
        ("#17DB2E", "0,1–0,2 m"), ("#80FF01", "0,2–0,3 m"), ("#FBFF01", "0,3–0,4 m"), ("#FFC001", "0,4–0,5 m"),
        ("#FF7C01", "0,5–1 m"), ("#DE1E22", "1–2 m"), ("#680404", "mer än 2 m"),
    ]
    shown = node("flood_legend.js", "[depthLegendShown(['SundsvallsKommun:100-ar_maxvattendjup']), "
                 "depthLegendShown(['SundsvallsKommun:100-ar_maxvattenhastighet', '13']), depthLegendShown([])]")
    assert shown == [True, False, False]
