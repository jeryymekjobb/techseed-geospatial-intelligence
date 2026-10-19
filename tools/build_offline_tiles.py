#!/usr/bin/env python3
"""Build offline map tiles for the fire-map area from an OpenStreetMap extract.

1. `osmium extract` cuts the area out of a country extract (in a throw-away
   Debian container with osmium-tool).
2. tilemaker turns it into OpenMapTiles-schema vector tiles in
   `data/tiles/<the scenario's TILES_FILE>`, for example `vastmanland.mbtiles`, with
   `tiles/process-techseed.lua` (tilemaker's OpenMapTiles processing, keeping every railway
   and the road numbers from a lower zoom).
3. `data/tiles/<tiles>.SOURCE.json`, for example `vastmanland.SOURCE.json`, records the input
   file, its SHA-256 and the area, so the scenarios' tiles can share the directory.

The `tiles` service of docker-compose.yml (tileserver-gl) then renders them as
map images, and the backend serves those at /tiles/{z}/{x}/{y}.png. Map data
© OpenStreetMap contributors, ODbL. Only Docker and the Python standard library
are needed; data/ is not versioned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.backend import scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data"
# The scenario's map area: the map view with the margin the GUI allows for panning
# (lon/lat, west,south,east,north).
DEFAULT_BBOX = ",".join(str(value) for value in scenario.MAP_BBOX)
TILEMAKER_IMAGE = "ghcr.io/systemed/tilemaker:master"
PROCESS_DIR = REPO_ROOT / "tiles"
PROCESS_FILE = "process-techseed.lua"
OSMIUM_IMAGE = "debian:stable-slim"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def user() -> str:
    return f"{os.getuid()}:{os.getgid()}"


def extract_command(source: Path, area: Path, bbox: str) -> list[str]:
    script = (
        "apt-get update -qq >/dev/null && apt-get install -y -qq osmium-tool >/dev/null && "
        f"osmium extract -b {bbox} --strategy smart --overwrite /osm/{source.name} -o /osm/{area.name} && "
        f"chown {user()} /osm/{area.name}"
    )
    return ["docker", "run", "--rm", "-v", f"{source.parent}:/osm", OSMIUM_IMAGE, "sh", "-c", script]


def tilemaker_command(area: Path, output: Path, bbox: str) -> list[str]:
    return [
        "docker", "run", "--rm", "-u", user(), "-v", f"{DATA}:/data", "-v", f"{PROCESS_DIR}:/techseed:ro", TILEMAKER_IMAGE,
        "--input", f"/data/{area.relative_to(DATA)}", "--output", f"/data/{output.relative_to(DATA)}",
        "--bbox", bbox, "--config", "resources/config-openmaptiles.json", "--process", f"/techseed/{PROCESS_FILE}",
        # Skip ways whose nodes are missing instead of crashing: Sundsvall's area grown north to
        # Kramfors (2026-10-15) holds a way whose node is missing in the country extract.
        "--skip-integrity",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--source", type=Path, default=DATA / "osm" / "sweden-latest.osm.pbf",
                        help="country extract, for example from download.openstreetmap.fr or Geofabrik")
    parser.add_argument("--source-url", default="https://download.openstreetmap.fr/extracts/europe/sweden-latest.osm.pbf")
    parser.add_argument("--bbox", default=DEFAULT_BBOX, help="west,south,east,north")
    args = parser.parse_args(argv)
    source = args.source.resolve()
    area = source.parent / f"{scenario.NAME}-area.osm.pbf"
    output = DATA / "tiles" / scenario.TILES_FILE
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(extract_command(source, area, args.bbox), check=True)
    if output.exists():
        output.unlink()
    subprocess.run(tilemaker_command(area, output, args.bbox), check=True, stdout=subprocess.DEVNULL)
    (output.parent / f"{output.stem}.SOURCE.json").write_text(json.dumps({
        "source_file": source.name,
        "source_url": args.source_url,
        "source_sha256": sha256_of(source),
        # The file's modification time, which is when it was downloaded.
        "source_downloaded_utc": datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bbox_west_south_east_north": args.bbox,
        "tiles": output.name,
        "tiles_sha256": sha256_of(output),
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": "OpenMapTiles (tilemaker resources/config-openmaptiles.json)",
        "processing": f"tiles/{PROCESS_FILE}: tilemaker's process-openmaptiles.lua, railways from zoom 8, road numbers from zoom 9",
        "attribution": "© OpenStreetMap contributors, ODbL",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Tiles: {output} ({output.stat().st_size // (1 << 20)} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
