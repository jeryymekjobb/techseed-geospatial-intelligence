#!/usr/bin/env python3
"""Fetch Copernicus DEM GLO-30 elevation tiles over the fire-map area into data/dem/.

GLO-30 is a 30 m global elevation model, free under the Copernicus DEM licence.
The 1x1 degree tiles come as Cloud Optimized GeoTIFFs from the public AWS
open-data bucket (no account needed). `data/dem/SOURCE.json` records the URL,
size and SHA-256 of each tile and the attribution the licence requires.
tools/build_terrain.py then turns the tiles into Cesium terrain.
Only the Python standard library is used; data/ is not versioned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
DEM_DIR = REPO_ROOT / "data" / "dem"
BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
# Same area as the offline map (lon/lat, west,south,east,north).
DEFAULT_BBOX = "15.5,59.55,16.8,60.3"
# The licence's notice for modified data; the terrain mesh is derived from the DEM.
ATTRIBUTION = (
    "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
    "provided under COPERNICUS by the European Union and ESA; all rights reserved"
)
LICENCE_URL = "https://spacedata.copernicus.eu/en/web/guest/collections/copernicus-digital-elevation-model/"


def tile_name(lat: int, lon: int) -> str:
    """GLO-30 tile name for the 1x1 degree cell whose south-west corner is (lat, lon)."""
    ns = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00"
    ew = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00"
    return f"Copernicus_DSM_COG_10_{ns}_{ew}_DEM"


def tiles_for(bbox: str) -> list[str]:
    west, south, east, north = (float(value) for value in bbox.split(","))
    if not (west < east and south < north):
        raise ValueError(f"bbox must be west,south,east,north: {bbox}")
    return [
        tile_name(lat, lon)
        for lat in range(math.floor(south), math.ceil(north))
        for lon in range(math.floor(west), math.ceil(east))
    ]


def tile_url(name: str) -> str:
    return f"{BUCKET}/{name}/{name}.tif"


def download(url: str, target: Path) -> str:
    """Download to target (through a .part file) and return its SHA-256."""
    digest = hashlib.sha256()
    partial = target.with_suffix(target.suffix + ".part")
    request = Request(url, headers={"User-Agent": "techseed-geospatial-intelligence/0.1"})
    with urlopen(request, timeout=300) as response, partial.open("wb") as stream:
        for block in iter(lambda: response.read(1 << 20), b""):
            digest.update(block)
            stream.write(block)
    partial.replace(target)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--bbox", default=DEFAULT_BBOX, help="west,south,east,north")
    args = parser.parse_args(argv)
    DEM_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for name in tiles_for(args.bbox):
        url = tile_url(name)
        target = DEM_DIR / f"{name}.tif"
        sha256 = download(url, target)
        records.append({"file": target.name, "url": url, "bytes": target.stat().st_size, "sha256": sha256})
        print(f"{target.name}: {target.stat().st_size // (1 << 20)} MB")
    (DEM_DIR / "SOURCE.json").write_text(json.dumps({
        "dataset": "Copernicus DEM GLO-30 (DGED/COG, AWS open data)",
        "bbox_west_south_east_north": args.bbox,
        "downloaded_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "licence": LICENCE_URL,
        "attribution": ATTRIBUTION,
        "tiles": records,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
