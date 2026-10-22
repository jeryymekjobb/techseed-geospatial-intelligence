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
CTB_IMAGE = "tumgis/ctb-quantized-mesh:latest"
NATIVE_BUILDER = "tools/quantized_terrain.py (GDAL, pydelatin 0.4.0, quantized-mesh-encoder 0.5.0)"


def user() -> str:
    return f"{os.getuid()}:{os.getgid()}"


def build_script(tiles: list[str], bbox: str) -> str:
    west, south, east, north = bbox.split(",")
    inputs = " ".join(f"/data/dem/{name}" for name in tiles)
    return (
        f"gdalbuildvrt -q -te {west} {south} {east} {north} /data/terrain/area.vrt {inputs} && "
        "ctb-tile -q -f Mesh -C -N -o /data/terrain /data/terrain/area.vrt && "
        "ctb-tile -q -f Mesh -C -N -l -o /data/terrain /data/terrain/area.vrt && "
        "rm /data/terrain/area.vrt"
    )


def docker_command(script: str) -> list[str]:
    # The scenario's own DEM and terrain directories, at the paths the script uses.
    return ["docker", "run", "--rm", "-u", user(), "-v", f"{DEM_DIR}:/data/dem:ro", "-v", f"{TERRAIN_DIR}:/data/terrain",
            CTB_IMAGE, "sh", "-c", script]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    geo_tools.add_argument(parser)
    args = parser.parse_args(argv)
    tools = geo_tools.choice(args.tools)
    source_file = DEM_DIR / "SOURCE.json"
    if not source_file.is_file():
        raise SystemExit(f"{source_file} is missing; run python3 -m tools.fetch_copernicus_dem first")
    source = json.loads(source_file.read_text(encoding="utf-8"))
    tiles = [record["file"] for record in source["tiles"]]
    if TERRAIN_DIR.exists():
        shutil.rmtree(TERRAIN_DIR)
    TERRAIN_DIR.mkdir(parents=True)
    if tools == "native":
        bbox = tuple(float(value) for value in source["bbox_west_south_east_north"].split(","))
        quantized_terrain.build(DEM_DIR, tiles, bbox, TERRAIN_DIR)
    else:
        subprocess.run(docker_command(build_script(tiles, source["bbox_west_south_east_north"])), check=True)
    count = sum(1 for _ in TERRAIN_DIR.rglob("*.terrain"))
    (TERRAIN_DIR / "SOURCE.json").write_text(json.dumps({
        "dataset": source["dataset"],
        "inputs": source["tiles"],
        "bbox_west_south_east_north": source["bbox_west_south_east_north"],
        "builder": NATIVE_BUILDER if tools == "native" else CTB_IMAGE,
        "format": "quantized-mesh-1.0 with oct-encoded vertex normals (gzip)",
        "tiles": count,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attribution": source["attribution"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Terrain: {TERRAIN_DIR} ({count} tiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
