"""Tests for app/frontend/wind_barbs.js, run with Node.js when it is installed."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "wind_barbs.js"


def node(expression: str) -> object:
    code = f"const barbs = require({json.dumps(str(SCRIPT))}); console.log(JSON.stringify({expression}));"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_barb_counts_round_to_the_nearest_2_5_ms() -> None:
    cases = node("[0.5, 2.6, 4.1, 6.8, 12.3, 27].map(barbs.windBarbCounts)")
    assert cases == [
        {"pennants": 0, "longs": 0, "shorts": 0},
        {"pennants": 0, "longs": 0, "shorts": 1},
        {"pennants": 0, "longs": 1, "shorts": 0},
        {"pennants": 0, "longs": 1, "shorts": 1},
        {"pennants": 0, "longs": 2, "shorts": 1},
        {"pennants": 1, "longs": 0, "shorts": 1},
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_calm_is_a_ring_and_wind_is_an_arrow_with_strokes() -> None:
    calm, light, strong = node("[barbs.windBarbSvg(0.4), barbs.windBarbSvg(6.8), barbs.windBarbSvg(27)]")
    assert "<circle" in calm and "path" not in calm
    assert "M0,15 L0,-15" in light and "L9," in light and "L4.5," in light
    assert 'class="pennant"' in strong
