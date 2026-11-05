#!/usr/bin/env python3
"""Build Cesium terrain for the 3D globe from the GLO-30 tiles in data/dem/.

1. `gdalbuildvrt` joins the tiles and cuts them to the map area.
2. cesium-terrain-builder (`ctb-tile`, in the tumgis/ctb-quantized-mesh
   container) writes quantized-mesh tiles with vertex normals and `layer.json`
   to `data/terrain/`.
3. `data/terrain/SOURCE.json` records the input tiles, the area and the
   attribution from `data/dem/SOURCE.json`.

The backend serves the result at /terrain/. Run tools/fetch_copernicus_dem.py
first. Only Docker and the Python standard library are needed; data/ is not
versioned.

--tools native (geo_tools) builds the same tiles and layer.json without Docker:
GDAL from PATH joins the DEM, and tools/quantized_terrain.py meshes and encodes the
tiles (pydelatin and quantized-mesh-encoder, tools/requirements-terrain.txt).

--area builds a monitoring area's terrain from its data/monitoring/<area>/dem/ into its
data/monitoring/<area>/terrain/ (fetch_copernicus_dem.py --area first), leaving the scenarios' alone.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone

from app.backend import scenario
from tools import geo_tools, quantized_terrain

DEM_DIR = scenario.DEM_DIR
TERRAIN_DIR = scenario.TERRAIN_DIR
# Pinned to the digest the terrain was built with, so a clean install builds the same (the tag moves).
CTB_IMAGE = "tumgis/ctb-quantized-mesh:latest@sha256:31053c0cee60fe2f6651812786b2861e1dda03b25a88f2fa6325a4a9e266ad98"
NATIVE_BUILDER = "tools/quantized_terrain.py (GDAL, pydelatin 0.4.0, quantized-mesh-encoder 0.5.0)"


def user() -> str:
    return f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "0:0"  # Windows has no uid; Docker Desktop maps the files


def build_script(tiles: list[str], bbox: str) -> str:
    west, south, east, north = bbox.split(",")
    inputs = " ".join(f"/data/dem/{name}" for name in tiles)
    return (
        f"gdalbuildvrt -q -te {west} {south} {east} {north} /data/terrain/area.vrt {inputs} && "
        "ctb-tile -q -f Mesh -C -N -o /data/terrain /data/terrain/area.vrt && "
        "ctb-tile -q -f Mesh -C -N -l -o /data/terrain /data/terrain/area.vrt && "
        "rm /data/terrain/area.vrt"
    )


def docker_command(script: str, dem_dir=DEM_DIR, terrain_dir=TERRAIN_DIR) -> list[str]:
    # The scenario's (or the area's) DEM and terrain directories, at the paths the script uses.
    return ["docker", "run", "--rm", "-u", user(), "-v", f"{dem_dir}:/data/dem:ro", "-v", f"{terrain_dir}:/data/terrain",
            CTB_IMAGE, "sh", "-c", script]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    geo_tools.add_argument(parser)
    parser.add_argument("--area", help="a monitoring area (app/monitoring/areas/) instead of the scenario")
    args = parser.parse_args(argv)
    tools = geo_tools.choice(args.tools)
    dem_dir, terrain_dir = DEM_DIR, TERRAIN_DIR
    if args.area:
        from app.monitoring import areas

        area = areas.load(args.area)
        dem_dir, terrain_dir = area.DATA_DIR / "dem", area.DATA_DIR / "terrain"
    source_file = dem_dir / "SOURCE.json"
    if not source_file.is_file():
        raise SystemExit(f"{source_file} is missing; run python3 -m tools.fetch_copernicus_dem first")
    source = json.loads(source_file.read_text(encoding="utf-8"))
    tiles = [record["file"] for record in source["tiles"]]
    if terrain_dir.exists():
        shutil.rmtree(terrain_dir)
    terrain_dir.mkdir(parents=True)
    if tools == "native":
        bbox = tuple(float(value) for value in source["bbox_west_south_east_north"].split(","))
        quantized_terrain.build(dem_dir, tiles, bbox, terrain_dir)
    else:
        subprocess.run(docker_command(build_script(tiles, source["bbox_west_south_east_north"]), dem_dir, terrain_dir), check=True)
    count = sum(1 for _ in terrain_dir.rglob("*.terrain"))
    (terrain_dir / "SOURCE.json").write_text(json.dumps({
        "dataset": source["dataset"],
        "inputs": source["tiles"],
        "bbox_west_south_east_north": source["bbox_west_south_east_north"],
        "builder": NATIVE_BUILDER if tools == "native" else CTB_IMAGE,
        "format": "quantized-mesh-1.0 with oct-encoded vertex normals (gzip)",
        "tiles": count,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attribution": source["attribution"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Terrain: {terrain_dir} ({count} tiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
