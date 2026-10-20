#!/usr/bin/env python3
"""Fetch Meteosat's cloud top height over the scenario's area from EUMETSAT's Data Store.

EUMETSAT's Cloud Top Height (MSG, 0 degree; EO:EUM:DAT:MSG:CTH, from 2005) gives, every 15
minutes, the height of the cloud tops on a grid of about 3 x 3 SEVIRI pixels over the full
disk, in GRIB2 (about 400 kB a product). Rising cloud tops show storms building before the rain.
This tool fetches the products of the scenario's playback period into a cache outside the
repository, keeps the cells within MAP_BBOX widened by MARGIN_DEG, and writes
data/<scenario>/meteosat-cth/cth.json and SOURCE.json: each cell's centre and corners, whether it
lies in the map area, and for each quarter every cell's height (None where clear) with the
cloudy share and mean height over the map area. A product already in the cache is not fetched
again.

ecCodes gives this grid's latitudes and longitudes rotated by 180 degrees against its values
(scanning mode 192); `rotated` turns the positions back and leaves the values as they are. Checked on 15 August 2026 against known cloud patterns: the rain belt
south of the Sahara cloudy, southern Africa's winter clear (reports/2026-10-20-meteosat-fler-data).

It needs a EUMETSAT account's API key in ~/.eumdac/credentials ("key,secret", as
`eumdac set-credentials` writes it), never in the repository, and eumdac and eccodes
(tools/requirements-meteosat.txt). The product is Core under EUMETSAT's data policy (CC BY 4.0).

    TECHSEED_SCENARIO=kramfors2026 .venv/bin/python -m tools.fetch_meteosat_cth
"""

from __future__ import annotations

import argparse
import io
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from app.backend import scenario

COLLECTION = "EO:EUM:DAT:MSG:CTH"
CREDENTIALS = Path.home() / ".eumdac" / "credentials"
CACHE = Path.home() / ".cache" / "techseed-meteosat-cth"
MARGIN_DEG = (0.6, 1.2)  # latitude, longitude: the neighbourhood round the map area
LICENCE = "CC BY 4.0 (Core), EUMETSAT data policy article 5.1"


def rows(values: Sequence[float], size: int) -> list[list[float]]:
    """A flat grid of size x size, as ecCodes gives it, in rows."""
    return [list(values[row * size:(row + 1) * size]) for row in range(size)]


def rotated(values: Sequence[float], size: int) -> list[list[float]]:
    """ecCodes' latitudes or longitudes for this product turned by 180 degrees, so that they match
    the values in rows(); only the positions are turned, not the values."""
    return [row[::-1] for row in rows(values, size)[::-1]]


def corners(lats: list[list[float]], lons: list[list[float]], row: int, column: int) -> list[list[float]]:
    """A cell's four corners, [lat, lon], each the mean of the four cell centres round it."""
    found = []
    for dr, dc in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
        r = [row, row + dr]
        c = [column, column + dc]
        points = [(lats[a][b], lons[a][b]) for a in r for b in c]
        found.append([round(sum(p[0] for p in points) / 4, 4), round(sum(p[1] for p in points) / 4, 4)])
    return found


def cells_in(lats: list[list[float]], lons: list[list[float]], bbox: tuple[float, float, float, float],
             margin: tuple[float, float] = MARGIN_DEG) -> list[dict[str, Any]]:
    """The cells within bbox (west, south, east, north) widened by margin, with whether each lies in bbox."""
    west, south, east, north = bbox
    found = []
    for row in range(1, len(lats) - 1):
        for column in range(1, len(lats[row]) - 1):
            lat, lon = lats[row][column], lons[row][column]
            if not (south - margin[0] <= lat <= north + margin[0] and west - margin[1] <= lon <= east + margin[1]):
                continue
            found.append({"row": row, "column": column, "latitude": round(lat, 4), "longitude": round(lon, 4),
                          "in_area": south <= lat <= north and west <= lon <= east,
                          "corners": corners(lats, lons, row, column)})
    return found


def quarter(heights: list[float | None], in_area: list[bool]) -> dict[str, Any]:
    """The cloudy share and mean cloud top height (km) over the cells in the map area."""
    inside = [height for height, flag in zip(heights, in_area) if flag]
    cloudy = [height for height in inside if height is not None]
    return {"cloud_pct": round(100 * len(cloudy) / len(inside)) if inside else None,
            "mean_km": round(sum(cloudy) / len(cloudy) / 1000, 1) if cloudy else None}


def read_grib(data: bytes) -> tuple[int, list[float], list[float], list[float], float]:
    import eccodes  # only this tool needs it (tools/requirements-meteosat.txt)

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        name = next(item for item in archive.namelist() if item.endswith(".grb"))
        grib = archive.read(name)
    # ecCodes reads this product from a file, not from memory ("no final 7777").
    with tempfile.TemporaryFile() as stream:
        stream.write(grib)
        stream.seek(0)
        handle = eccodes.codes_grib_new_from_file(stream)
    try:
        size = eccodes.codes_get(handle, "Nx")
        floats = lambda values: [float(value) for value in values]  # plain floats, not numpy's, for JSON
        return (size, floats(eccodes.codes_get_array(handle, "latitudes")), floats(eccodes.codes_get_array(handle, "longitudes")),
                floats(eccodes.codes_get_values(handle)), float(eccodes.codes_get(handle, "missingValue")))
    finally:
        eccodes.codes_release(handle)


def products(start: datetime, end: datetime):
    import eumdac  # only this tool needs it

    if not CREDENTIALS.is_file():
        raise SystemExit(f"fetch_meteosat_cth: no EUMETSAT API key in {CREDENTIALS} (eumdac set-credentials)")
    key, secret = CREDENTIALS.read_text(encoding="utf-8").strip().split(",", 1)
    store = eumdac.DataStore(eumdac.AccessToken((key, secret)))
    return sorted(store.get_collection(COLLECTION).search(dtstart=start, dtend=end), key=lambda product: str(product))


def time_of(product_id: str) -> str:
    """The product's time from its name, e.g. MSG3-SEVI-MSGCLTH-0100-0100-20260815160000.000000000Z-NA."""
    stamp = product_id.split("-")[5][:12]
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[8:10]}:{stamp[10:12]}:00Z"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--cache", type=Path, default=CACHE, help=f"where the products are kept (default {CACHE})")
    parser.add_argument("--out", type=Path, default=scenario.METEOSAT_CTH_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_meteosat_cth: the scenario {scenario.NAME} has no METEOSAT_CTH_FILE\n")
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cells: list[dict[str, Any]] = []
    quarters = []
    satellites = set()
    for product in products(scenario.PLAYBACK_START, scenario.PLAYBACK_END):
        name = str(product)
        cached = args.cache / f"{name}.zip"
        if not (cached.is_file() and cached.stat().st_size):
            with product.open() as stream:
                cached.write_bytes(stream.read())
        size, lats, lons, values, missing = read_grib(cached.read_bytes())
        grid = rows(values, size)
        if not cells:
            cells = cells_in(rotated(lats, size), rotated(lons, size), scenario.MAP_BBOX)
        heights = [None if grid[cell["row"]][cell["column"]] == missing else round(grid[cell["row"]][cell["column"]]) for cell in cells]
        quarters.append({"time_utc": time_of(name), **quarter(heights, [cell["in_area"] for cell in cells]), "heights_m": heights})
        satellites.add(name.split("-")[0])
        print(f"{time_of(name)}: {quarters[-1]['cloud_pct']} % moln, medel {quarters[-1]['mean_km']} km", flush=True)
    for cell in cells:
        cell.pop("row"), cell.pop("column")
    args.out.write_text(json.dumps({"cells": cells, "quarters": quarters}, separators=(",", ":")) + "\n", encoding="utf-8")
    (args.out.parent / "SOURCE.json").write_text(json.dumps({
        "source": "EUMETSAT Cloud Top Height - MSG - 0 degree", "collection": COLLECTION, "licence": LICENCE,
        "satellites": sorted(satellites),
        "map_bbox_west_south_east_north": list(scenario.MAP_BBOX), "margin_deg_lat_lon": list(MARGIN_DEG),
        "period_utc": [scenario.PLAYBACK_START.strftime("%Y-%m-%dT%H:%MZ"), scenario.PLAYBACK_END.strftime("%Y-%m-%dT%H:%MZ")],
        "quarters": len(quarters), "cells": len(cells), "cells_in_map_area": sum(cell["in_area"] for cell in cells),
        "orientation": "ecCodes' latitudes and longitudes turned by 180 degrees (scanning mode 192)",
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(quarters)} kvartar, {len(cells)} rutor ({sum(cell['in_area'] for cell in cells)} i kartområdet); {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
