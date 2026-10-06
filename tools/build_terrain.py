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
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.backend import scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data"
DEM_DIR = scenario.DEM_DIR
TERRAIN_DIR = scenario.TERRAIN_DIR
CTB_IMAGE = "tumgis/ctb-quantized-mesh:latest"


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
    return ["docker", "run", "--rm", "-u", user(), "-v", f"{DATA}:/data", CTB_IMAGE, "sh", "-c", script]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.parse_args(argv)
    source_file = DEM_DIR / "SOURCE.json"
    if not source_file.is_file():
        raise SystemExit("data/dem/SOURCE.json is missing; run python3 -m tools.fetch_copernicus_dem first")
    source = json.loads(source_file.read_text(encoding="utf-8"))
    tiles = [record["file"] for record in source["tiles"]]
    if TERRAIN_DIR.exists():
        shutil.rmtree(TERRAIN_DIR)
    TERRAIN_DIR.mkdir(parents=True)
    subprocess.run(docker_command(build_script(tiles, source["bbox_west_south_east_north"])), check=True)
    count = sum(1 for _ in TERRAIN_DIR.rglob("*.terrain"))
    (TERRAIN_DIR / "SOURCE.json").write_text(json.dumps({
        "dataset": source["dataset"],
        "inputs": source["tiles"],
        "bbox_west_south_east_north": source["bbox_west_south_east_north"],
        "builder": CTB_IMAGE,
        "format": "quantized-mesh-1.0 with oct-encoded vertex normals (gzip)",
        "tiles": count,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attribution": source["attribution"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Terrain: {TERRAIN_DIR} ({count} tiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
