"""Tests for tools/quantized_terrain.py with a SYNTHETIC height model (a tilted plane), not real DEM data."""

from __future__ import annotations

import gzip
import importlib.util
import struct
from pathlib import Path

import pytest

from tools import quantized_terrain as qt

HAS_MESHING = all(importlib.util.find_spec(name) for name in ("numpy", "pydelatin", "quantized_mesh_encoder"))
FLEN = (16.35, 58.95, 16.75, 59.13)


def test_the_levels_and_tiles_follow_ctb_tile() -> None:
    # GLO-30 has 1" rows: level 13 is the deepest, as in ctb-tile's terrain of every scenario.
    assert qt.max_level(1 / 3600) == 13
    assert qt.tile_ranges(FLEN, 0) == (0, 0, 1, 0)  # both root tiles, as ctb-tile -C
    # ctb-tile's layer.json for flen2024 (data/flen2024/terrain, built 2026-10-21).
    assert qt.tile_ranges(FLEN, 1) == (2, 1, 2, 1) and qt.tile_ranges(FLEN, 2) == (4, 3, 4, 3)
    assert qt.tile_ranges(FLEN, 13) == (8936, 6778, 8954, 6787)
    layer = qt.layer_json(FLEN, 13)
    assert layer["format"] == "quantized-mesh-1.0" and layer["extensions"] == ["octvertexnormals"] and layer["schema"] == "tms"
    assert len(layer["available"]) == 14 and layer["available"][13] == [{"startX": 8936, "startY": 6778, "endX": 8954, "endY": 6787}]
    # Cesium: the ellipsoid's circumference / 4 / 65 / the 2 tiles at level 0 = 77 067 m, halved per level.
    assert qt.geometric_error(0) == pytest.approx(77067.3, abs=0.1) and qt.geometric_error(13) == pytest.approx(9.41, abs=0.01)


@pytest.mark.skipif(not HAS_MESHING, reason="needs numpy, pydelatin and quantized-mesh-encoder (tools/requirements-terrain.txt)")
def test_the_vertices_are_numbered_in_first_use_order() -> None:
    import numpy as np

    vertices = np.array([[0, 0, 1.0], [1, 0, 2.0], [0, 1, 3.0], [1, 1, 4.0]])
    triangles = np.array([[3, 1, 0], [0, 2, 3]])
    ordered, renumbered = qt.in_first_use_order(vertices, triangles)
    assert renumbered.tolist() == [[0, 1, 2], [2, 3, 0]]
    assert ordered[:, 2].tolist() == [4.0, 2.0, 1.0, 3.0]  # the same triangles, the same points
    highest = 0
    for index in renumbered.reshape(-1):  # quantized mesh's high-water mark: a new index is the next one
        assert index <= highest
        highest += index == highest


def decode(data: bytes, bounds: tuple[float, float, float, float]):
    """Vertex longitudes, latitudes and heights of a quantized-mesh tile."""
    import numpy as np

    data = gzip.decompress(data)
    min_height, max_height = struct.unpack_from("<2f", data, 24)
    count = struct.unpack_from("<I", data, 88)[0]
    values = []
    for part in range(3):
        raw = np.frombuffer(data, "<u2", count, 92 + part * 2 * count).astype(np.int64)
        decoded = (raw >> 1) ^ -(raw & 1)  # zigzag, then the running sum
        values.append(np.cumsum(decoded))
    u, v, h = values
    west, south, east, north = bounds
    return (west + u / 32767 * (east - west), south + v / 32767 * (north - south),
            min_height + h / 32767 * (max_height - min_height))


@pytest.mark.skipif(not HAS_MESHING, reason="needs numpy, pydelatin and quantized-mesh-encoder (tools/requirements-terrain.txt)")
def test_a_tile_keeps_the_heights_where_they_lie(tmp_path: Path) -> None:
    import numpy as np

    # A synthetic plane rising 100 m from west to east and 50 m from south to north over the area.
    west, south, east, north = FLEN
    xres, yres = 1 / 2400, 1 / 3600
    cols, rows = round((east - west) / xres), round((north - south) / yres)
    lons = west + (np.arange(cols) + 0.5) * xres
    lats = north - (np.arange(rows) + 0.5) * yres
    plane = lambda lon, lat: 20 + 100 * (lon - west) / (east - west) + 50 * (lat - south) / (north - south)  # noqa: E731
    values = plane(*np.meshgrid(lons, lats)).astype("<f4")
    values.tofile(tmp_path / "area.bil")
    (tmp_path / "area.hdr").write_text(f"BYTEORDER I\nLAYOUT BIL\nNROWS {rows}\nNCOLS {cols}\nNBANDS 1\nNBITS 32\n"
                                       f"PIXELTYPE FLOAT\nULXMAP {west + xres / 2}\nULYMAP {north - yres / 2}\nXDIM {xres}\nYDIM {yres}\n")
    heights = qt.read_ehdr(tmp_path / "area.bil")
    assert heights.sample([16.55], [59.04])[0] == pytest.approx(plane(16.55, 59.04), abs=0.05)
    assert heights.sample([10.0], [59.04])[0] == 0.0  # outside the area, as ctb-tile reads no data there
    x0, y0, x1, y1 = qt.tile_ranges(FLEN, 13)
    level, x, y = 13, (x0 + x1) // 2, (y0 + y1) // 2
    bounds = qt.tile_bounds(level, x, y)
    lon, lat, height = decode(qt.encode_tile(heights, level, x, y), bounds)
    assert len(lon) >= 4 and lon.min() == pytest.approx(bounds[0]) and lat.max() == pytest.approx(bounds[3])
    # Each vertex's height is the plane's at its place: not mirrored north to south (an earlier mistake).
    assert np.abs(height - plane(lon, lat)).max() < 0.1
