"""Build Cesium quantized-mesh terrain without Docker, as tools/build_terrain.py does with ctb-tile.

For Windows without Docker (build_terrain --tools native). The DEM tiles are joined and cut to
the map area with GDAL from PATH (geo_tools), read with numpy, and for each level and tile that
ctb-tile writes, the heights on a 65 x 65 grid are triangulated with pydelatin and encoded with
quantized-mesh-encoder, with oct-encoded vertex normals, gzip-compressed, beside the same
layer.json. Both packages are MIT-licensed and have wheels for Windows
(tools/requirements-terrain.txt).

The tiles follow ctb-tile: the geographic (EPSG:4326) TMS scheme with two tiles at level 0,
the tiles covering the map area at every level, and the deepest level whose 64 cells per tile
are no finer than the DEM. Heights outside the map area are 0, as ctb-tile reads no data
there. Each tile's mesh keeps within Cesium's geometric error for its level, so the globe does
not refine further than the mesh allows. Checked against ctb-tile's terrain of flen2024 on
2026-10-22 (reports and CONTEXT.md).
"""

from __future__ import annotations

import gzip
import io
import json
import math
from pathlib import Path

from tools import geo_tools

GRID = 65  # vertices per tile side, as Cesium's height-map terrain and ctb-tile
# Cesium's maximum geometric error at level 0 for the geographic scheme (two tiles across):
# the ellipsoid's equatorial circumference / 4 / 65 / 2, in metres.
LEVEL_ZERO_ERROR = 6378137.0 * 2 * math.pi * 0.25 / (GRID * 2)


def tile_size(level: int) -> float:
    """A tile's width and height in degrees."""
    return 180.0 / 2 ** level


def max_level(resolution: float) -> int:
    """The deepest level whose 64 cells per tile are no finer than the DEM's resolution in degrees."""
    return max(0, math.floor(math.log2(180.0 / ((GRID - 1) * resolution))))


def tile_ranges(bbox: tuple[float, float, float, float], level: int) -> tuple[int, int, int, int]:
    """The tiles over the area at the level: first and last column (from 180° W) and row (TMS, from 90° S)."""
    west, south, east, north = bbox
    if level == 0:
        return 0, 0, 1, 0  # ctb-tile -C writes both root tiles
    size = tile_size(level)
    return (math.floor((west + 180) / size), math.floor((south + 90) / size),
            math.floor((east + 180) / size), math.floor((north + 90) / size))


def tile_bounds(level: int, x: int, y: int) -> tuple[float, float, float, float]:
    size = tile_size(level)
    return x * size - 180, y * size - 90, (x + 1) * size - 180, (y + 1) * size - 90


def geometric_error(level: int) -> float:
    return LEVEL_ZERO_ERROR / 2 ** level


def layer_json(bbox: tuple[float, float, float, float], levels: int) -> dict:
    """The same layer.json as ctb-tile writes."""
    available = []
    for level in range(levels + 1):
        x0, y0, x1, y1 = tile_ranges(bbox, level)
        available.append([{"startX": x0, "startY": y0, "endX": x1, "endY": y1}])
    return {"tilejson": "2.1.0", "name": "area", "description": "", "version": "1.1.0", "format": "quantized-mesh-1.0",
            "attribution": "", "schema": "tms", "extensions": ["octvertexnormals"], "tiles": ["{z}/{x}/{y}.terrain?v={version}"],
            "projection": "EPSG:4326", "bounds": [0.0, -90.0, 180.0, 90.0], "available": available}


class Heights:
    """The DEM over the map area on a regular lon/lat grid (rows north to south), sampled bilinearly; 0 outside."""

    def __init__(self, values, west: float, north: float, xres: float, yres: float) -> None:
        self.values, self.west, self.north, self.xres, self.yres = values, west, north, xres, yres

    def sample(self, lons, lats):
        import numpy as np

        rows, cols = self.values.shape
        # Pixel centres: the value of cell (r, c) lies at its middle.
        fx = (np.asarray(lons) - self.west) / self.xres - 0.5
        fy = (self.north - np.asarray(lats)) / self.yres - 0.5
        inside = (fx >= -0.5) & (fx <= cols - 0.5) & (fy >= -0.5) & (fy <= rows - 0.5)
        fx, fy = np.clip(fx, 0, cols - 1), np.clip(fy, 0, rows - 1)
        x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
        x1, y1 = np.minimum(x0 + 1, cols - 1), np.minimum(y0 + 1, rows - 1)
        tx, ty = fx - x0, fy - y0
        v = self.values
        top = v[y0, x0] * (1 - tx) + v[y0, x1] * tx
        bottom = v[y1, x0] * (1 - tx) + v[y1, x1] * tx
        return np.where(inside, top * (1 - ty) + bottom * ty, 0.0)


def read_ehdr(path: Path) -> Heights:
    """A Float32 EHdr raster (gdal_translate -of EHdr) with its header's grid."""
    import numpy as np

    header = {}
    for line in path.with_suffix(".hdr").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            header[parts[0].upper()] = parts[1]
    rows, cols = int(header["NROWS"]), int(header["NCOLS"])
    dtype = ">f4" if header.get("BYTEORDER", "I").upper() == "M" else "<f4"
    values = np.fromfile(path, dtype=dtype).reshape(rows, cols).astype("f8")
    nodata = float(header["NODATA"]) if "NODATA" in header else None
    if nodata is not None:
        values[values == nodata] = 0.0
    values[~np.isfinite(values) | (values < -1000)] = 0.0
    xres, yres = float(header["XDIM"]), float(header["YDIM"])
    # ULXMAP/ULYMAP are the middle of the upper-left cell.
    return Heights(values, float(header["ULXMAP"]) - xres / 2, float(header["ULYMAP"]) + yres / 2, xres, yres)


def dem_steps(dem_dir: Path, tiles: list[str], bbox: tuple[float, float, float, float]) -> tuple[list[list[str]], list[str]]:
    """GDAL steps (geo_tools): the DEM tiles joined and cut to the map area, as Float32 rows."""
    west, south, east, north = bbox
    return [["gdalbuildvrt", "-q", "-te", *map(str, (west, south, east, north)), "area.vrt",
             *((dem_dir / name).as_posix() for name in tiles)],
            ["gdal_translate", "-q", "-of", "EHdr", "-ot", "Float32", "area.vrt", "area.bil"]], ["area.vrt", "*.aux.xml"]


def in_first_use_order(vertices, triangles):
    """The vertices renumbered in the order the triangles first use them. Quantized mesh encodes the
    indices against a high-water mark, which assumes that order; pydelatin numbers them otherwise, and
    quantized-mesh-encoder does not reorder them, so some indices would be written wrong."""
    import numpy as np

    flat = np.asarray(triangles).reshape(-1)
    _, first = np.unique(flat, return_index=True)
    order = np.unique(flat)[np.argsort(first)]
    renumber = np.empty(len(vertices), dtype=np.uint32)
    renumber[order] = np.arange(len(order), dtype=np.uint32)
    return np.asarray(vertices)[order], renumber[flat].reshape(-1, 3)


def encode_tile(heights: Heights, level: int, x: int, y: int) -> bytes:
    """One tile: the heights on its grid, triangulated within the level's geometric error, as gzip'd quantized mesh."""
    import numpy as np
    from pydelatin import Delatin
    from pydelatin.util import rescale_positions
    from quantized_mesh_encoder import VertexNormalsExtension, encode

    west, south, east, north = tile_bounds(level, x, y)
    lons = np.linspace(west, east, GRID)
    lats = np.linspace(north, south, GRID)  # rows north to south
    grid = heights.sample(*np.meshgrid(lons, lats)).astype("f4")
    mesh = Delatin(grid, width=GRID, height=GRID, max_error=geometric_error(level))
    vertices, triangles = in_first_use_order(mesh.vertices, mesh.triangles)
    # pydelatin's rows already run from the bounds' south, as rescale_positions expects: no flip
    # (with flip_y the heights came out mirrored north to south, checked against the DEM).
    positions = rescale_positions(vertices, (west, south, east, north), flip_y=False)
    buffer = io.BytesIO()
    encode(buffer, positions, triangles, bounds=(west, south, east, north),
           extensions=(VertexNormalsExtension(positions=positions, indices=triangles),))
    return gzip.compress(buffer.getvalue(), mtime=0)


def build(dem_dir: Path, tiles: list[str], bbox: tuple[float, float, float, float], terrain_dir: Path) -> int:
    """Write the terrain's tiles and layer.json to terrain_dir; the number of tiles."""
    steps, cleanup = dem_steps(dem_dir.resolve(), tiles, bbox)
    run = geo_tools.run_native(steps, terrain_dir, cleanup)
    if run.returncode != 0:
        raise RuntimeError(f"GDAL failed for the DEM:\n{run.stderr[-2000:]}")
    heights = read_ehdr(terrain_dir / "area.bil")
    for suffix in (".bil", ".hdr", ".prj", ".bil.aux.xml"):
        (terrain_dir / f"area{suffix}").unlink(missing_ok=True)
    levels = max_level(min(heights.xres, heights.yres))
    count = 0
    for level in range(levels + 1):
        x0, y0, x1, y1 = tile_ranges(bbox, level)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                path = terrain_dir / str(level) / str(x) / f"{y}.terrain"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encode_tile(heights, level, x, y))
                count += 1
    (terrain_dir / "layer.json").write_text(json.dumps(layer_json(bbox, levels)), encoding="utf-8")
    return count
