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

The sea: tilemaker's OpenMapTiles configuration draws it from OSM's water polygons
(`coastline/water_polygons.shp`), which are not in the country extract. When
`data/osm/water-polygons-split-4326.zip` (osmdata.openstreetmap.de, ODbL; fetch_scenario's
`water-polygons` step) is there, GDAL clips it to the area into `data/osm/<scenario>-coastline/`
and tilemaker gets a copy of its configuration whose `ocean` source is that file. Without it the
map is built as before, with the sea drawn as land.

The `tiles` service of docker-compose.yml (tileserver-gl) then renders them as
map images, and the backend serves those at /tiles/{z}/{x}/{y}.png. Map data
© OpenStreetMap contributors, ODbL. Only Docker and the Python standard library
are needed; data/ is not versioned.

--tools native (geo_tools) runs osmium and tilemaker from PATH instead, with
--tilemaker-resources naming tilemaker's resources directory (config-openmaptiles.json and
process-openmaptiles.lua). There is no ready-made tilemaker for Windows; there the map comes
with the scenario's data package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.backend import scenario
from tools import geo_tools

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data"
# The scenario's map area: the map view with the margin the GUI allows for panning
# (lon/lat, west,south,east,north).
DEFAULT_BBOX = ",".join(str(value) for value in scenario.MAP_BBOX)
# Pinned to the digest the offline maps were built with; its OpenMapTiles config comes from the image too.
TILEMAKER_IMAGE = "ghcr.io/systemed/tilemaker:master@sha256:d3eda2790458de727bb0096eebce775984fc060f60901dac6dbfbbb79ae17370"
PROCESS_DIR = REPO_ROOT / "tiles"
PROCESS_FILE = "process-techseed.lua"
# Pinned to a digest; osmium-tool itself is installed with apt-get at each build, so its version is not.
OSMIUM_IMAGE = "debian:stable-slim@sha256:5bc3287b25407c965a30f38e32603dc253a3869e1b12a21ac09bfc27fd8b13ce"
# OSM's sea as polygons split into tiles, WGS 84 (osmdata.openstreetmap.de, ODbL).
WATER_POLYGONS = DATA / "osm" / "water-polygons-split-4326.zip"
WATER_POLYGONS_URL = "https://osmdata.openstreetmap.de/download/water-polygons-split-4326.zip"
WATER_LAYER = "water-polygons-split-4326/water_polygons.shp"  # inside the zip
# tilemaker's own configuration, inside its image and in a native install's resources directory.
TILEMAKER_CONFIG = "resources/config-openmaptiles.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def user() -> str:
    return f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "0:0"  # Windows has no uid; Docker Desktop maps the files


def extract_command(source: Path, area: Path, bbox: str) -> list[str]:
    script = (
        "apt-get update -qq >/dev/null && apt-get install -y -qq osmium-tool >/dev/null && "
        f"osmium extract -b {bbox} --strategy smart --overwrite /osm/{source.name} -o /osm/{area.name} && "
        f"chown {user()} /osm/{area.name}"
    )
    return ["docker", "run", "--rm", "-v", f"{source.parent}:/osm", OSMIUM_IMAGE, "sh", "-c", script]


def extract_step(source: Path, area: Path, bbox: str) -> list[str]:
    """osmium from PATH (--tools native)."""
    return ["osmium", "extract", "-b", bbox, "--strategy", "smart", "--overwrite", str(source), "-o", str(area)]


def tilemaker_step(area: Path, output: Path, bbox: str, resources: Path, config: Path | None = None) -> list[str]:
    """tilemaker from PATH (--tools native), run in the parent of its resources directory, since
    process-techseed.lua loads resources/process-openmaptiles.lua from there; `config` is a copy
    with the sea, else tilemaker's own."""
    return ["tilemaker", "--input", str(area), "--output", str(output), "--bbox", bbox,
            "--config", str(config or resources / "config-openmaptiles.json"), "--process", str(PROCESS_DIR / PROCESS_FILE), "--skip-integrity"]


def tilemaker_command(area: Path, output: Path, bbox: str, config: Path | None = None) -> list[str]:
    """tilemaker in its image; `config`, under data/, is a copy with the sea, else tilemaker's own."""
    return [
        "docker", "run", "--rm", "-u", user(), "-v", f"{DATA}:/data", "-v", f"{PROCESS_DIR}:/techseed:ro", TILEMAKER_IMAGE,
        "--input", f"/data/{area.relative_to(DATA)}", "--output", f"/data/{output.relative_to(DATA)}",
        "--bbox", bbox, "--config", f"/data/{config.relative_to(DATA)}" if config else TILEMAKER_CONFIG,
        "--process", f"/techseed/{PROCESS_FILE}",
        # Skip ways whose nodes are missing instead of crashing: Sundsvall's area grown north to
        # Kramfors (2026-10-15) holds a way whose node is missing in the country extract.
        "--skip-integrity",
    ]


def coastline_steps(zip_path: str, bbox: str) -> list[list[str]]:
    """The OGR step (geo_tools) that clips the water polygons to the area into water_polygons.shp."""
    west, south, east, north = bbox.split(",")
    return [["ogr2ogr", "-f", "ESRI Shapefile", "-spat", west, south, east, north, "-clipsrc", west, south, east, north,
             "water_polygons.shp", f"/vsizip/{zip_path}/{WATER_LAYER}"]]


def clip_coastline(zip_file: Path, folder: Path, bbox: str, tools: str) -> Path:
    """The water polygons inside the area, as folder/water_polygons.shp."""
    from tools.fetch_landsat_scene import GDAL_IMAGE  # the GDAL container the other tools use

    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    if tools == "native":
        result = geo_tools.run_native(coastline_steps(str(zip_file), bbox), folder)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    else:
        subprocess.run(["docker", "run", "--rm", "-u", user(), "-v", f"{folder}:/data", "-v", f"{zip_file.parent}:/osm:ro", GDAL_IMAGE,
                        "sh", "-c", geo_tools.shell_script(coastline_steps(f"/osm/{zip_file.name}", bbox))], check=True)
    return folder / "water_polygons.shp"


def with_coastline(config: dict, shapefile: str) -> dict:
    """tilemaker's configuration with its `ocean` layer drawn from the clipped water polygons."""
    layers = {**config["layers"], "ocean": {**config["layers"]["ocean"], "source": shapefile}}
    return {**config, "layers": layers}


def tilemaker_config(tools: str, resources: Path | None) -> dict:
    """tilemaker's own OpenMapTiles configuration, from a native install or its image."""
    if tools == "native":
        return json.loads((resources / "config-openmaptiles.json").read_text(encoding="utf-8"))
    shown = subprocess.run(["docker", "run", "--rm", "--entrypoint", "cat", TILEMAKER_IMAGE, TILEMAKER_CONFIG],
                           check=True, capture_output=True, text=True)
    return json.loads(shown.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--source", type=Path, default=DATA / "osm" / "sweden-latest.osm.pbf",
                        help="country extract, for example from download.openstreetmap.fr or Geofabrik")
    parser.add_argument("--source-url", default="https://download.openstreetmap.fr/extracts/europe/sweden-latest.osm.pbf")
    parser.add_argument("--bbox", default=DEFAULT_BBOX, help="west,south,east,north")
    geo_tools.add_argument(parser)
    parser.add_argument("--tilemaker-resources", type=Path, help="with --tools native: tilemaker's resources directory")
    parser.add_argument("--water-polygons", type=Path, default=WATER_POLYGONS,
                        help="OSM's water polygons (water-polygons-split-4326.zip) for the sea; without it no sea is drawn")
    args = parser.parse_args(argv)
    tools = geo_tools.choice(args.tools)
    resources = args.tilemaker_resources.resolve() if args.tilemaker_resources else None
    if tools == "native":
        missing = [name for name in ("osmium", "tilemaker") if shutil.which(name) is None]
        if missing or resources is None or not (resources / "process-openmaptiles.lua").is_file():
            parser.error("--tools native needs osmium and tilemaker on PATH and --tilemaker-resources with tilemaker's "
                         "process-openmaptiles.lua; without tilemaker (as on Windows) take the map from the data package")
    source = args.source.resolve()
    area = source.parent / f"{scenario.NAME}-area.osm.pbf"
    output = DATA / "tiles" / scenario.TILES_FILE
    output.parent.mkdir(parents=True, exist_ok=True)
    if tools == "native":
        subprocess.run(extract_step(source, area, args.bbox), check=True)
    else:
        subprocess.run(extract_command(source, area, args.bbox), check=True)
    if output.exists():
        output.unlink()
    config = None
    if args.water_polygons.is_file():
        water = args.water_polygons.resolve()
        shapefile = clip_coastline(water, source.parent / f"{scenario.NAME}-coastline", args.bbox, tools)
        config = source.parent / f"{scenario.NAME}-tilemaker-config.json"
        inside = str(shapefile) if tools == "native" else f"/data/{shapefile.relative_to(DATA)}"
        config.write_text(json.dumps(with_coastline(tilemaker_config(tools, resources), inside), indent=1) + "\n", encoding="utf-8")
    else:
        print(f"build_offline_tiles: {args.water_polygons} saknas; kartan byggs utan havsytor", flush=True)
    if tools == "native":
        subprocess.run(tilemaker_step(area, output, args.bbox, resources, config), cwd=resources.parent, check=True, stdout=subprocess.DEVNULL)
    else:
        subprocess.run(tilemaker_command(area, output, args.bbox, config), check=True, stdout=subprocess.DEVNULL)
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
        "sea": {"source_file": args.water_polygons.name, "source_url": WATER_POLYGONS_URL,
                "source_downloaded_utc": datetime.fromtimestamp(args.water_polygons.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
               if config else None,
        "attribution": "© OpenStreetMap contributors, ODbL",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Tiles: {output} ({output.stat().st_size // (1 << 20)} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
