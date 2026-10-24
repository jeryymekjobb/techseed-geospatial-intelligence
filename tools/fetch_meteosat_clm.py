#!/usr/bin/env python3
"""Fetch Meteosat's cloud mask over the scenario's map area from EUMETSAT's Data Store.

EUMETSAT's Cloud Mask (MSG, 0 degree; EO:EUM:DAT:MSG:CLM, from 2004) classes every SEVIRI pixel of
the full disk every 15 minutes as clear over water (0), clear over land (1), cloud (2) or no data
(3), in GRIB2 (about 550 kB a product, 3712 x 3712). This tool fetches the product on each whole
hour of the scenario's playback and the quarter nearest each of the scenario's satellite images,
into a cache outside the repository, and writes data/<scenario>/meteosat-clm/clm.json and
SOURCE.json with the cloudy share of the pixels in MAP_BBOX: for every hour, and for every image
with its scene. A product already in the cache is not fetched again.

ecCodes gives the grid's positions turned by 180 degrees against its values, as for the cloud top
height (tools/fetch_meteosat_cth.py); only the positions are turned back. The grid is large, so
this tool counts with numpy.

It needs the EUMETSAT API key in ~/.eumdac/credentials and eumdac and eccodes
(tools/requirements-meteosat.txt). The product is Core under EUMETSAT's data policy (CC BY 4.0).

    TECHSEED_SCENARIO=kramfors2026 .venv/bin/python -m tools.fetch_meteosat_clm
"""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.backend import landsat, scenario
from app.backend.meteosat_clm import ATTRIBUTION as PRODUCT_ATTRIBUTION
from tools.fetch_meteosat_cth import CREDENTIALS, download, time_of

COLLECTION = "EO:EUM:DAT:MSG:CLM"
CACHE = Path.home() / ".cache" / "techseed-meteosat-clm"
LICENCE = "CC BY 4.0 (Core), EUMETSAT data policy article 5.1"
CLEAR, CLOUD = (0, 1), 2
WORKERS = 8


def cloud_pct(classes) -> int | None:
    """The cloudy share of the pixels that are clear or cloudy (no data left out), in whole per cent."""
    import numpy

    cloudy = int(numpy.count_nonzero(classes == CLOUD))
    clear = int(numpy.count_nonzero(numpy.isin(classes, CLEAR)))
    return round(100 * cloudy / (cloudy + clear)) if cloudy + clear else None


def area_index(lats, lons, size: int, bbox: tuple[float, float, float, float]):
    """The flat indices of the values whose pixel lies in bbox (west, south, east, north); the
    positions are turned by 180 degrees to match the values."""
    import numpy

    west, south, east, north = bbox
    lat = numpy.asarray(lats).reshape(size, size)[::-1, ::-1].ravel()
    lon = numpy.asarray(lons).reshape(size, size)[::-1, ::-1].ravel()
    return numpy.flatnonzero((lat >= south) & (lat <= north) & (lon >= west) & (lon <= east))


def read_grib(data: bytes, positions: bool):
    import eccodes  # only the fetch tools need it (tools/requirements-meteosat.txt)

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        grib = archive.read(next(item for item in archive.namelist() if item.endswith(".grb")))
    handle = eccodes.codes_new_from_message(grib)
    try:
        size = eccodes.codes_get(handle, "Nx")
        values = eccodes.codes_get_values(handle)
        if not positions:
            return size, values, None, None
        return size, values, eccodes.codes_get_array(handle, "latitudes"), eccodes.codes_get_array(handle, "longitudes")
    finally:
        eccodes.codes_release(handle)


def wanted_times(start: datetime, end: datetime, images: list[str]) -> list[datetime]:
    """Each whole hour of the playback and the quarter nearest each image, without repeats, in order."""
    found, hour = set(), start.replace(minute=0, second=0, microsecond=0)
    while hour < end:
        found.add(hour)
        hour += timedelta(hours=1)
    for text in images:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        quarter = moment.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=15 * round(moment.minute / 15))
        found.add(quarter)
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    import eumdac  # only the fetch tools need it

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--cache", type=Path, default=CACHE, help=f"where the products are kept (default {CACHE})")
    parser.add_argument("--out", type=Path, default=scenario.METEOSAT_CLM_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_meteosat_clm: the scenario {scenario.NAME} has no METEOSAT_CLM_FILE\n")
    if not CREDENTIALS.is_file():
        parser.exit(1, f"fetch_meteosat_clm: no EUMETSAT API key in {CREDENTIALS} (eumdac set-credentials)\n")
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    scenes = (landsat.layer() or {}).get("scenes", [])
    times = wanted_times(scenario.PLAYBACK_START, scenario.PLAYBACK_END, [scene["acquired_utc"] for scene in scenes])
    key, secret = CREDENTIALS.read_text(encoding="utf-8").strip().split(",", 1)
    token = eumdac.AccessToken((key, secret))
    collection = eumdac.DataStore(token).get_collection(COLLECTION)
    # One search for the playback, and one for each image outside it (a search takes seconds).
    found = {time_of(str(item)): item for item in collection.search(dtstart=scenario.PLAYBACK_START, dtend=scenario.PLAYBACK_END)}
    index, shares, satellites, missing, chosen = None, {}, set(), [], []
    for moment in times:
        stamp = moment.strftime("%Y-%m-%dT%H:%M:00Z")
        if stamp not in found:
            found.update({time_of(str(item)): item for item in collection.search(dtstart=moment, dtend=moment + timedelta(minutes=14))})
        if stamp in found:
            chosen.append(found[stamp])
        else:
            missing.append(stamp)

    def fetched(product) -> Path:
        return download(product, token, args.cache / f"{product}.zip")

    # Most of the time goes to waiting on the Data Store, so WORKERS products are fetched at a time.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        paths = list(pool.map(fetched, chosen))
    for product, cached in zip(chosen, paths):
        name = str(product)
        size, values, lats, lons = read_grib(cached.read_bytes(), positions=index is None)
        if index is None:
            index = area_index(lats, lons, size, scenario.MAP_BBOX)
        shares[time_of(name)] = cloud_pct(values[index])
        satellites.add(name.split("-")[0])
        print(f"{time_of(name)}: {shares[time_of(name)]} % moln", flush=True)

    def nearest(text: str) -> str | None:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        found = min(shares, key=lambda key: abs(datetime.fromisoformat(key.replace("Z", "+00:00")) - moment), default=None)
        return found if found and abs(datetime.fromisoformat(found.replace("Z", "+00:00")) - moment) <= timedelta(minutes=15) else None

    hours = [{"time_utc": key, "cloud_pct": value} for key, value in sorted(shares.items()) if key.endswith(":00:00Z")
             and scenario.PLAYBACK_START <= datetime.fromisoformat(key.replace("Z", "+00:00")) < scenario.PLAYBACK_END]
    images = [{"scene": scene["scene"], "acquired_utc": scene["acquired_utc"], "time_utc": nearest(scene["acquired_utc"]),
               "cloud_pct": shares.get(nearest(scene["acquired_utc"]) or "")} for scene in scenes]
    args.out.write_text(json.dumps({"pixels_in_area": int(len(index)) if index is not None else 0, "hours": hours, "images": images},
                                   ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out.parent / "SOURCE.json").write_text(json.dumps({
        "source": "EUMETSAT Cloud Mask - MSG - 0 degree", "collection": COLLECTION, "licence": LICENCE,
        "attribution": PRODUCT_ATTRIBUTION,
        "satellites": sorted(satellites), "map_bbox_west_south_east_north": list(scenario.MAP_BBOX),
        "times": len(times), "times_missing": missing,
        "classes": {"0": "clear over water", "1": "clear over land", "2": "cloud", "3": "no data"},
        "orientation": "ecCodes' positions turned by 180 degrees against the values (scanning mode 192)",
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(hours)} timmar, {len(images)} bilder, {len(index) if index is not None else 0} pixlar i kartområdet; {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
