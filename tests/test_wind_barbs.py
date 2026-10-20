"""Tests for app/frontend/wind_barbs.js, run with Node.js when it is installed."""

from __future__ import annotations

import csv
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



@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_wind_arrows_thin_out_from_the_middle_of_the_grid() -> None:
    # Points of ERA5-Land's 0.1° grid round a middle at 62.0 N, 17.0 E, with the CSV's floating-point noise.
    zooms = node("[[62.0, 17.0], [62.8, 16.2], [62.4, 17.4], [61.8, 17.2], [62.1, 17.0], [61.7, 16.9]]"
                 ".map(([lat, lon]) => barbs.windMinZoom(lat, lon, [620, 170]))")
    assert zooms == [0, 0, 7, 8, 9, 9]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_about_a_quarter_of_the_arrows_stay_per_zoom_step_out() -> None:
    counts = node("(() => { const points = []; for (let i = 0; i < 32; i += 1) for (let j = 0; j < 32; j += 1)"
                  " points.push([60 + i / 10, 15 + j / 10]);"
                  " const middle = barbs.windGridMiddle(points);"
                  " const zooms = points.map(([lat, lon]) => barbs.windMinZoom(lat, lon, middle));"
                  " return [middle, [9, 8, 7, 6].map((zoom) => zooms.filter((min) => zoom >= min).length)]; })()")
    assert counts == [[616, 166], [1024, 256, 64, 16]]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_every_scenario_keeps_a_wind_arrow_at_every_zoom() -> None:
    root = SCRIPT.parents[2]
    # The scenarios' ERA5-Land grids, where they are fetched (unversioned data).
    files = sorted(root.glob("data/*/era5-land/era5-land-*.csv")) + sorted(root.glob("weather_data/era5-land/era5-land-*.csv"))
    if not files:
        pytest.skip("no ERA5-Land files")
    grids = {}
    for path in files:
        with path.open(encoding="utf-8", newline="") as stream:
            grids[path.name] = sorted({(float(row["latitude"]), float(row["longitude"])) for row in csv.DictReader(stream)})
    counts = node(f"Object.fromEntries(Object.entries({json.dumps(grids)}).map(([name, points]) => {{"
                  " const middle = barbs.windGridMiddle(points);"
                  " const zooms = points.map(([lat, lon]) => barbs.windMinZoom(lat, lon, middle));"
                  " return [name, [9, 8, 7, 6, 3].map((zoom) => zooms.filter((min) => zoom >= min).length)]; }))")
    for name, per_zoom in counts.items():
        assert all(count >= 1 for count in per_zoom), (name, per_zoom)
