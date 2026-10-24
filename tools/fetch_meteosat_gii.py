#!/usr/bin/env python3
"""Fetch MTG's instability indices round the scenario's area from EUMETSAT's Data Store.

MTG's Global Instability Indices (MTG 0 degree; EO:EUM:DAT:0683, from 27 January 2025) give, every
ten minutes on a grid of fields of regard over the full disk, the K index, the lifted index and the
precipitable water, computed from FCI's infrared channels where the sky is clear (about 14 MB a
file). They show how favourable the air was for thunderstorms before the clouds came; under the
clouds they have no values. This tool fetches the file of every STEP_HOURS hour of the scenario's
playback into a cache outside the repository and writes data/<scenario>/meteosat-gii/gii.json and
SOURCE.json: for each time, the fields with values within MAP_BBOX widened by MARGIN_DEG, the
highest K index and lowest lifted index among them. WORKERS files are fetched at a time.

The positions are given in the files. It needs the EUMETSAT API key in ~/.eumdac/credentials and
eumdac and h5py (tools/requirements-meteosat.txt). The product is Core (CC BY 4.0).

    TECHSEED_SCENARIO=kramfors2026 .venv/bin/python -m tools.fetch_meteosat_gii
"""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.backend import scenario
from app.backend.meteosat_gii import ATTRIBUTION as PRODUCT_ATTRIBUTION
from tools.fetch_meteosat_cth import CREDENTIALS, MARGIN_DEG, download
from tools.fetch_meteosat_li import sensing_start

COLLECTION = "EO:EUM:DAT:0683"
CACHE = Path.home() / ".cache" / "techseed-meteosat-gii"
LICENCE = "CC BY 4.0 (Core), EUMETSAT data policy article 5.1"
STEP_HOURS = 3
WORKERS = 4
FILL = -32767
SCALE = 0.01


def every_step(names: list[str], step: int = STEP_HOURS) -> list[str]:
    """The first product of every `step`-th whole hour (00, 03, 06 … UTC), by its sensing start."""
    chosen: dict[str, str] = {}
    for name in sorted(names, key=sensing_start):
        start = sensing_start(name)
        if int(start[11:13]) % step == 0:
            chosen.setdefault(start[:13], name)
    return [chosen[key] for key in sorted(chosen)]


def summary(points: list[list[float]]) -> dict[str, Any]:
    """The fields with values and the highest K index and lowest lifted index among them."""
    return {"fields": len(points), "k_max": max((point[2] for point in points), default=None),
            "lifted_min": min((point[3] for point in points if point[3] is not None), default=None)}


def read_zip(data: bytes, bbox: tuple[float, float, float, float], margin: tuple[float, float] = MARGIN_DEG) -> list[list[float]]:
    """The fields of one file within bbox widened by margin with a K index, as [lat, lon, K, lifted index]."""
    import h5py
    import numpy

    west, south, east, north = bbox
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        name = next(item for item in archive.namelist() if item.endswith(".nc") and "NC4E" in item)
        with h5py.File(io.BytesIO(archive.read(name))) as stream:
            lat, lon = stream["latitude"][:], stream["longitude"][:]
            k, lifted = stream["k_index"][:], stream["lifted_index"][:]
    ok = (lat != FILL) & (lon != FILL) & (k != FILL)
    la, lo = lat * SCALE, lon * SCALE
    sel = ok & (la >= south - margin[0]) & (la <= north + margin[0]) & (lo >= west - margin[1]) & (lo <= east + margin[1])
    return [[round(float(a), 2), round(float(b), 2), round(float(c) * SCALE, 1), None if d == FILL else round(float(d) * SCALE, 1)]
            for a, b, c, d in zip(la[sel], lo[sel], k[sel], lifted[sel])] if numpy.any(sel) else []


def main(argv: list[str] | None = None) -> int:
    import eumdac  # only the fetch tools need it

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--cache", type=Path, default=CACHE, help=f"where the products are kept (default {CACHE})")
    parser.add_argument("--out", type=Path, default=scenario.METEOSAT_GII_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_meteosat_gii: the scenario {scenario.NAME} has no METEOSAT_GII_FILE\n")
    if not CREDENTIALS.is_file():
        parser.exit(1, f"fetch_meteosat_gii: no EUMETSAT API key in {CREDENTIALS} (eumdac set-credentials)\n")
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    key, secret = CREDENTIALS.read_text(encoding="utf-8").strip().split(",", 1)
    token = eumdac.AccessToken((key, secret))
    collection = eumdac.DataStore(token).get_collection(COLLECTION)
    found = {str(item): item for item in collection.search(dtstart=scenario.PLAYBACK_START, dtend=scenario.PLAYBACK_END)}
    chosen = [found[name] for name in every_step(list(found))]

    def fetched(product) -> Path:
        return download(product, token, args.cache / f"{sensing_start(str(product)).replace(':', '')}.zip")

    times = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for product, path in zip(chosen, pool.map(fetched, chosen)):
            points = read_zip(path.read_bytes(), scenario.MAP_BBOX)
            times.append({"time_utc": sensing_start(str(product)), **summary(points), "points": points})
            print(f"{times[-1]['time_utc']}: {len(points)} rutor, K max {times[-1]['k_max']}", flush=True)
    args.out.write_text(json.dumps({"times": times}, separators=(",", ":")) + "\n", encoding="utf-8")
    (args.out.parent / "SOURCE.json").write_text(json.dumps({
        "source": "EUMETSAT Global Instability Indices - MTG - 0 degree", "collection": COLLECTION, "licence": LICENCE,
        "attribution": PRODUCT_ATTRIBUTION,
        "map_bbox_west_south_east_north": list(scenario.MAP_BBOX), "margin_deg_lat_lon": list(MARGIN_DEG),
        "step_hours": STEP_HOURS, "times": len(times),
        "fields": ["latitude", "longitude", "K index", "lifted index"],
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(times)} tider; {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
