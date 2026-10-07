"""Tests for tools/fetch_sentinel1_scene.py with synthetic data (no network or Docker)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import fetch_sentinel1_scene as s1

try:
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

BBOX = (16.9, 62.15, 17.8, 62.62)
FOCUS = (17.15, 62.33, 17.45, 62.45)  # rows 17-28, columns 25-54 of 90 x 47
SIZE = (90, 47)


def test_the_acquisition_is_named_by_satellite_and_time() -> None:
    assert s1.scene_key({"satellite": "Sentinel-1C", "time_utc": "2026-08-16T05:21:32Z"}) == "S1C_20260816T052132"


def test_the_products_are_warped_with_their_control_points_and_the_dem_onto_the_same_grid() -> None:
    script = s1.warp_script(["https://example.org/a.tiff?t", "https://example.org/b.tiff?t"], "K", BBOX, SIZE)
    assert "-tps -t_srs EPSG:4326 -te 16.9 62.15 17.8 62.62 -ts 90 47 -r average -srcnodata 0 -dstnodata 0 -ot UInt16 " \
           "'/vsicurl/https://example.org/a.tiff?t' '/vsicurl/https://example.org/b.tiff?t' vv.tif" in script
    assert "gdal_translate -q -of EHdr vv.tif K-vv.bil" in script
    dem = s1.dem_script(["N62.tif", "N63.tif"], BBOX, SIZE)
    assert "-te 16.9 62.15 17.8 62.62 -ts 90 47 -r average -ot Float32 /dem/N62.tif /dem/N63.tif dem.tif" in dem


@pytest.mark.skipif(not HAS_NUMPY, reason="needs numpy and Pillow (the .venv)")
def test_dark_land_as_dark_as_open_water_is_marked_and_a_scene_without_contrast_is_not_separable(tmp_path: Path) -> None:
    import numpy as np
    from PIL import Image

    water = np.zeros((47, 90), dtype=bool)
    water[:, 70:] = True                                     # the sea in the east
    amplitude = np.full((47, 90), 1000, dtype="<u2")         # land: 60 dB
    amplitude[water] = 30                                    # water: about 29,5 dB
    amplitude[20:23, 30:33] = 20                             # a 3 x 3 pool on land inside the focus area
    amplitude[5, 5] = 20                                     # one dark pixel of speckle
    amplitude.tofile(tmp_path / "K-vv.bil")
    stats = s1.radar_images(tmp_path, "K", water, SIZE, BBOX, FOCUS)
    mask = np.asarray(Image.open(tmp_path / "K-radarwater.png"))
    assert tuple(mask[21, 31]) == s1.WATER_RGBA and mask[5, 5, 3] == 0 and mask[20, 75, 3] == 0  # not speckle, not the sea
    assert stats["separable"] and stats["focus_area_coverage_pct"] == 100.0
    # The pool's four corners have only four dark neighbours of nine: five pixels remain.
    assert stats["focus_area_new_water_pct"] == pytest.approx(100 * 5 / (12 * 30), abs=0.01)
    grey = np.asarray(Image.open(tmp_path / "K-radar.png"))
    assert grey[21, 31, 0] < grey[10, 10, 0] and grey[10, 10, 3] == 255

    amplitude[~water] = 25                                   # land as dark as the water: wind or rain
    amplitude.tofile(tmp_path / "K-vv.bil")
    assert not s1.radar_images(tmp_path, "K", water, SIZE, BBOX, FOCUS)["separable"]
