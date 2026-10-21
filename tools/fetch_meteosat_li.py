#!/usr/bin/env python3
"""Fetch the Lightning Imager's flashes over the scenario's area from EUMETSAT's Data Store.

MTG's Lightning Imager (LI Lightning Flashes, MTG 0 degree; EO:EUM:DAT:0691, from July 2024)
lists every flash it saw on the full disk, in files of ten minutes (about 0.4 MB): time, position,
radiance, duration and a confidence, cloud flashes as well as flashes to the ground. This tool
fetches the files of the scenario's playback into a cache outside the repository, keeps the
flashes within MAP_BBOX widened by MARGIN_DEG and writes data/<scenario>/meteosat-li/li.json and
SOURCE.json: each flash as [epoch seconds, latitude, longitude] in time order. A file already in
the cache is not fetched again; WORKERS files are fetched at a time.

The Nordic area lies at the edge of the instrument's view (positions are given in the files, so
nothing is turned). It needs the EUMETSAT API key in ~/.eumdac/credentials and eumdac and h5py
(tools/requirements-meteosat.txt). The product is Core under EUMETSAT's data policy (CC BY 4.0).

    TECHSEED_SCENARIO=kramfors2026 .venv/bin/python -m tools.fetch_meteosat_li
"""

from __future__ import annotations

import argparse
import io
import json
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.backend import scenario
from tools.fetch_meteosat_cth import CREDENTIALS, MARGIN_DEG, download

COLLECTION = "EO:EUM:DAT:0691"
CACHE = Path.home() / ".cache" / "techseed-meteosat-li"
LICENCE = "CC BY 4.0 (Core), EUMETSAT data policy article 5.1"
WORKERS = 4
EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)  # the files' "seconds since 2000-01-01"
SENSING = re.compile(r"_OPE_(\d{14})_(\d{14})_")


def sensing_start(name: str) -> str:
    """The start of a product's ten minutes from its name, e.g. …_OPE_20260815160006_20260815161006_…"""
    stamp = SENSING.search(name).group(1)
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[8:10]}:{stamp[10:12]}:{stamp[12:14]}Z"


def flashes_in(columns: dict[str, Any], bbox: tuple[float, float, float, float], margin: tuple[float, float] = MARGIN_DEG) -> list[list[float]]:
    """The flashes of one file (scaled latitude, longitude and flash_time in seconds since 2000) within
    bbox (west, south, east, north) widened by margin, as [epoch seconds, latitude, longitude]."""
    west, south, east, north = bbox
    found = []
    offset = EPOCH.timestamp()
    for lat, lon, seconds in zip(columns["latitude"], columns["longitude"], columns["flash_time"]):
        if lat is None or lon is None:
            continue
        if south - margin[0] <= lat <= north + margin[0] and west - margin[1] <= lon <= east + margin[1]:
            found.append([round(offset + seconds), round(lat, 3), round(lon, 3)])
    return found


def read_zip(data: bytes, bbox: tuple[float, float, float, float]) -> list[list[float]]:
    import h5py  # only the fetch tools need it

    found = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if not (name.endswith(".nc") and "BODY" in name):
                continue
            with h5py.File(io.BytesIO(archive.read(name))) as stream:
                columns = {}
                for key in ("latitude", "longitude"):
                    raw = stream[key][:]
                    fill = int(stream[key].attrs["_FillValue"][0])
                    factor = float(stream[key].attrs["scale_factor"][0])
                    columns[key] = [None if value == fill else float(value) * factor for value in raw]
                columns["flash_time"] = [float(value) for value in stream["flash_time"][:]]
            found += flashes_in(columns, bbox)
    return found


def main(argv: list[str] | None = None) -> int:
    import eumdac  # only the fetch tools need it

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--cache", type=Path, default=CACHE, help=f"where the products are kept (default {CACHE})")
    parser.add_argument("--out", type=Path, default=scenario.METEOSAT_LI_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_meteosat_li: the scenario {scenario.NAME} has no METEOSAT_LI_FILE\n")
    if not CREDENTIALS.is_file():
        parser.exit(1, f"fetch_meteosat_li: no EUMETSAT API key in {CREDENTIALS} (eumdac set-credentials)\n")
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    key, secret = CREDENTIALS.read_text(encoding="utf-8").strip().split(",", 1)
    token = eumdac.AccessToken((key, secret))
    collection = eumdac.DataStore(token).get_collection(COLLECTION)
    products = sorted(collection.search(dtstart=scenario.PLAYBACK_START, dtend=scenario.PLAYBACK_END), key=lambda item: sensing_start(str(item)))

    def fetched(product) -> Path:
        return download(product, token, args.cache / f"{sensing_start(str(product)).replace(':', '')}.zip")

    flashes: list[list[float]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for product, path in zip(products, pool.map(fetched, products)):
            found = read_zip(path.read_bytes(), scenario.MAP_BBOX)
            flashes += found
            print(f"{sensing_start(str(product))}: {len(found)} blixtar", flush=True)
    flashes.sort()
    args.out.write_text(json.dumps({"flashes": flashes}, separators=(",", ":")) + "\n", encoding="utf-8")
    (args.out.parent / "SOURCE.json").write_text(json.dumps({
        "source": "EUMETSAT LI Lightning Flashes - MTG - 0 degree", "collection": COLLECTION, "licence": LICENCE,
        "map_bbox_west_south_east_north": list(scenario.MAP_BBOX), "margin_deg_lat_lon": list(MARGIN_DEG),
        "files": len(products), "flashes": len(flashes),
        "fields": ["epoch seconds (UTC)", "latitude", "longitude"],
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(products)} filer, {len(flashes)} blixtar; {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
