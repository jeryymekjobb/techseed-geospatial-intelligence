"""Tests for tools/fetch_sentinel2_scene.py with synthetic data (no network or Docker)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import fetch_sentinel2_scene as s2

try:
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def test_reflectance_is_turned_into_level2a_numbers_with_the_offset_of_newer_baselines() -> None:
    assert s2.dn_for(0.25, "05.11") == 3500 and s2.dn_for(0.0, "04.00") == 1000
    assert s2.dn_for(0.25, "03.01") == 2500


def test_the_focus_area_rows_and_columns() -> None:
    rows, cols = s2.focus_rows_cols((90, 47), (16.9, 62.15, 17.8, 62.62), (17.15, 62.33, 17.45, 62.45))
    assert (rows.start, rows.stop, cols.start, cols.stop) == (17, 29, 25, 55)


def test_the_script_mosaics_every_tile_of_the_datatake_and_writes_the_raw_bands() -> None:
    urls = {band: [f"https://example.org/T33VWK_{band}.tif?t", f"https://example.org/T33VXK_{band}.tif?t"]
            for band in ["B02", "B03", "B04", "B08", "SCL"]}
    script = s2.warp_script(urls, "SCENE", "05.11", (16.9, 62.15, 17.8, 62.62), (90, 47))
    assert script.count("gdalwarp ") == 5
    assert "-te 16.9 62.15 17.8 62.62 -ts 90 47 -srcnodata 0 -dstnodata 0 -r near '/vsicurl/https://example.org/T33VWK_SCL.tif?t' " \
           "'/vsicurl/https://example.org/T33VXK_SCL.tif?t' SCL.tif" in script  # classes: never interpolated
    assert "-r bilinear '/vsicurl/https://example.org/T33VWK_B08.tif?t'" in script
    for band in ["B03", "B08", "SCL"]:
        assert f"gdal_translate -q -of EHdr {band}.tif SCENE-{band}.bil" in script
    assert "-scale 1000 3500 1 255 -a_nodata 0 -of PNG natural.vrt SCENE-natural.png" in script


@pytest.mark.skipif(not HAS_NUMPY, reason="needs numpy and Pillow (the .venv)")
def test_water_is_blue_where_ndwi_is_positive_and_clouds_and_gaps_are_transparent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np
    from PIL import Image

    monkeypatch.setattr(s2, "BBOX", (16.9, 62.15, 17.8, 62.62))
    monkeypatch.setattr(s2, "FOCUS_AREA", (17.15, 62.33, 17.45, 62.45))  # rows 17-28, columns 25-54
    size = (90, 47)  # 0.01 degrees per pixel
    green = np.full((47, 90), 1000 + 600, dtype="<u2")
    nir = np.full((47, 90), 1000 + 2500, dtype="<u2")      # land: NDWI below 0
    scl = np.full((47, 90), 4, dtype="u1")                # vegetation
    nir[20, 30:40] = 1000 + 100                            # a strip of water inside the focus area
    scl[22, 30] = 9                                        # one cloud pixel inside it
    scl[:, :10] = 0                                        # no data in the west
    for band, data in {"B03": green, "B08": nir, "SCL": scl}.items():
        data.tofile(tmp_path / f"S-{band}.bil")
    coverage, cloud, water = s2.water_image(tmp_path, "S", "05.11", size)
    image = np.asarray(Image.open(tmp_path / "S-water.png"))
    assert tuple(image[20, 35]) == s2.WATER_RGBA and image[5, 50, 3] == 0 and image[22, 30, 3] == 0
    rows, cols = s2.focus_rows_cols(size, s2.BBOX, s2.FOCUS_AREA)
    area = (rows.stop - rows.start) * (cols.stop - cols.start)
    assert coverage == 100.0 and cloud == pytest.approx(100 / area, abs=0.1)
    assert water == pytest.approx(100 * 10 / area, abs=0.1)
