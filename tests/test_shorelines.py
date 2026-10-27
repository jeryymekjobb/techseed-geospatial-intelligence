"""Tests for the yearly shoreline lines of a coastal erosion scenario (tools/derive_shorelines.py, shorelines.py)."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import derive_shorelines as ds

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
# Sea south of 55.39 N between 12.8 and 13.0 E.
SEA = [[[[12.7, 55.3], [13.1, 55.3], [13.1, 55.39], [12.7, 55.39], [12.7, 55.3]]]]


def node(expression: str) -> object:
    code = f"const m = require({json.dumps(str(FRONTEND / 'shorelines.js'))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def test_utm_puts_the_central_meridian_at_500_km_and_its_arc_as_the_northing() -> None:
    assert ds.utm(0.0, 15.0, 32633) == pytest.approx((500000.0, 0.0), abs=1e-6)
    # WGS 84's meridian arc to 45° is 4 984 944.38 m; UTM scales it by 0.9996.
    assert ds.utm(45.0, 15.0, 32633)[1] == pytest.approx(4984944.38 * 0.9996, abs=0.5)
    east, west = ds.utm(55.4, 16.0, 32633), ds.utm(55.4, 14.0, 32633)
    assert east[0] - 500000 == pytest.approx(500000 - west[0]) and east[1] == pytest.approx(west[1])
    assert ds.utm(55.4, 21.0, 32634)[0] == pytest.approx(500000.0)  # zone 34's central meridian


def test_the_grid_bounds_cover_the_area_in_whole_pixels() -> None:
    bounds = ds.grid_bounds((12.79, 55.365, 12.995, 55.42), 32633)
    assert all(value % 10 == 0 for value in bounds)
    for lat in (55.365, 55.42):
        for lon in (12.79, 12.995):
            x, y = ds.utm(lat, lon, 32633)
            assert bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]


def test_the_coast_is_found_north_of_the_sea_with_normals_towards_land() -> None:
    points = ds.coast({"name": "Stranden", "west": 12.85, "east": 12.86}, SEA, 55.36, 55.43)
    assert len(points) == 13 and all(lat == pytest.approx(55.39, abs=1e-4) for _, lat in points)
    lines = ds.transects(points, SEA)
    assert len(lines) == 11 and all(item["north"] == pytest.approx(1.0) and abs(item["east"]) < 1e-9 for item in lines)
    lon, lat = ds.along(lines[0], 100)
    assert lon == pytest.approx(lines[0]["longitude"]) and (lat - lines[0]["latitude"]) * 110574 == pytest.approx(100)


def test_the_vegetation_edge_is_found_landward_of_the_waterline() -> None:
    # Every 2 m: water to 20 m, bare sand to 50 m, then vegetation; a sandbank of 10 m at 6 m.
    ndwi = [0.5 if (k < 10 and not 3 <= k < 5) else -0.4 for k in range(60)]
    ndvi = [0.0 if k < 25 else 0.6 for k in range(60)]
    assert ds.edge(ndwi, ndvi, 0.0) == pytest.approx(2 * (24 + 0.5))
    assert ds.edge(ndwi, [0.0] * 60, 0.0) is None  # no vegetation
    assert ds.edge([*ndwi[:-1], math.nan], ndvi, 0.0) is None  # missing data
    assert ds.edge([-0.4] * 60, ndvi, 0.0) is None  # no waterline


def test_spikes_are_left_out_and_the_line_breaks_where_a_point_is_missing() -> None:
    assert ds.despike([10.0, 12.0, 60.0, 14.0, None, 70.0, 16.0]) == [10.0, 12.0, None, 14.0, None, 70.0, 16.0]
    assert ds.pieces([(1, 2), (3, 4), None, (5, 6), None, (7, 8), (9, 10)]) == [[[1, 2], [3, 4]], [[7, 8], [9, 10]]]
    assert ds.otsu([0.4, 0.5, 0.45, -0.3, -0.35, -0.4]) == pytest.approx(0.05, abs=0.4)
    assert -0.3 < ds.otsu([0.4, 0.5, 0.45, -0.3, -0.35, -0.4]) < 0.4


def test_the_layer_gives_the_lines_label_credit_uncertainty_and_view(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import scenario, shorelines

    path = tmp_path / "shorelines.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
                                    {"type": "Feature", "geometry": None, "properties": {"role": "before-babet"}},
                                    {"type": "Feature", "geometry": None, "properties": {"role": "2099"}}],
                                "label": "Strandlinje", "attribution": "Sentinel",
                                "uncertainty_m": [10, 20]}), encoding="utf-8")
    view = {"name": "Kämpinge", "west": 12.946, "south": 55.395, "east": 12.982, "north": 55.407}
    monkeypatch.setattr(scenario, "SHORELINE_FILE", path)
    monkeypatch.setattr(scenario, "SHORELINE_VIEW", view)
    monkeypatch.setattr(scenario, "LANDSAT_ROLES", {"before-babet": "Före Babet"})
    shorelines.lines.cache_clear()
    try:
        # Each line carries its image's role label, its role when the scenario names none.
        assert [feature["properties"]["label"] for feature in shorelines.lines()["features"]] == ["Före Babet", "2099"]
        assert shorelines.layer() == {"label": "Strandlinje", "attribution": "Sentinel", "uncertainty_m": [10, 20],
                                      "url": "/api/shorelines", "view": view}
        monkeypatch.setattr(scenario, "SHORELINE_FILE", tmp_path / "missing.geojson")
        shorelines.lines.cache_clear()
        assert shorelines.layer() is None
    finally:
        shorelines.lines.cache_clear()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_maps_draw_the_lines_up_to_the_clock_from_blue_to_red() -> None:
    feature = lambda day, satellite, role, label: {"geometry": {"coordinates": [[[12.8, 55.39], [12.81, 55.39]]]},  # noqa: E731
                                                   "properties": {"acquired_utc": f"{day}T10:30:00Z", "satellite": satellite,
                                                                  "role": role, "label": label}}
    collection = {"features": [feature("2015-08-19", "Sentinel-2A", "2015", "Årsbild 2015"),
                               feature("2020-06-15", "Sentinel-2B", "before-babet", "Före Babet"),
                               feature("2026-05-25", "Sentinel-2A", "2026", "Årsbild 2026")],
                  "uncertainty_m": [10, 20]}
    shown = node(f"shorelinesAt({json.dumps(collection)}, Date.parse('2021-01-01T00:00:00Z'))")
    assert [(item["colour"], item["latest"]) for item in shown] == [("#1f5fbf", False), ("#7b4474", True)]
    assert shown[1]["text"] == "Vegetationskant 2020-06-15, Sentinel-2B, härledd ur Sentinel-2, ±10–20 m"
    assert node(f"shorelinesAt({json.dumps(collection)}, Date.parse('2015-01-01T00:00:00Z'))") == []
    assert node("shorelineColour(2, 3)") == "#d62828"
    assert node(f"shorelineLegend({json.dumps(collection)}, Date.parse('2021-01-01T00:00:00Z'))") == [
        {"colour": "#1f5fbf", "text": "2015-08-19", "shown": True, "latest": False},
        {"colour": "#7b4474", "text": "2020-06-15, före Babet", "shown": True, "latest": True},
        {"colour": "#d62828", "text": "2026-05-25", "shown": False, "latest": False}]


def test_a_point_far_from_its_transect_s_median_over_the_images_is_left_out() -> None:
    images = [[10.0, 20.0, None], [12.0, 80.0, 5.0], [14.0, 22.0, 6.0], [11.0, 21.0, 90.0]]
    assert ds.without_outliers(images) == [[10.0, 20.0, None], [12.0, None, 5.0], [14.0, 22.0, 6.0], [11.0, 21.0, None]]
