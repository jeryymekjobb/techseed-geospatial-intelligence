#!/usr/bin/env python3
"""Fetch LSA SAF's fire risk (FRM v3) over the scenario's map area, one map a day.

LSA SAF's Fire Risk Map v3 gives, for each day, the Canadian fire weather index (FWI) and its
codes, a risk class (1 low to 5 extreme) and a probability on a 0.05° grid over Europe up to
70 N, valid at 12:00 UTC (LSA SAF's map service). The archive (2000 on) is computed with ERA5's
weather and calibrated with satellite fire observations, so it is partly a reanalysis, not
Meteosat's observation alone. This tool fetches the day files of the scenario's playback period
into a cache outside the repository (about 4.5 MB each), keeps the cells inside MAP_BBOX and
writes data/<scenario>/meteosat-frm/frm.json and SOURCE.json. A file already in the cache is
not fetched again.

It uses the LSA SAF account in ~/.netrc and h5py (tools/requirements-meteosat.txt), like
tools/fetch_meteosat_frp.py.

    TECHSEED_SCENARIO=vastmanland2014 .venv/bin/python -m tools.fetch_meteosat_frm
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError

from app.backend import scenario
from app.backend.meteosat_frm import ATTRIBUTION as PRODUCT_ATTRIBUTION
from tools.fetch_meteosat_frp import HOST, LICENCE, opener

BASE_URL = f"https://{HOST}/PRODUCTS/MSG/FRMv3/NETCDF"
FILE_NAME = "NETCDF4_LSASAF_MSG_FRMv3-ERA5_MSG-Disk_{day:%Y%m%d}0000.nc"
CACHE = Path.home() / ".cache" / "techseed-meteosat-frm"
VALID_HOUR_UTC = 12
# The grids kept for each day: the file's name and the decimals written.
GRIDS = {"FWI": ("fwi", 1), "Risk": ("risk", 0), "FFMC": ("ffmc", 1), "DC": ("dc", 0)}


def noon(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, VALID_HOUR_UTC, tzinfo=timezone.utc)


def days(start: datetime, end: datetime) -> list[date]:
    """The day whose map is valid at `start` (the day before, before noon) and every later day whose
    noon falls before `end`."""
    day = start.date() if noon(start.date()) <= start else start.date() - timedelta(days=1)
    found = []
    while noon(day) < end:
        found.append(day)
        day += timedelta(days=1)
    return found


def url(day: date) -> str:
    return f"{BASE_URL}/{day:%Y/%m/%d}/{FILE_NAME.format(day=day)}"


def window(values: Sequence[float], low: float, high: float) -> slice:
    """The index range of the cell centres in `values` (ascending or descending) between low and high."""
    inside = [index for index, value in enumerate(values) if low <= value <= high]
    return slice(inside[0], inside[-1] + 1) if inside else slice(0, 0)


def scaled(rows: Sequence[Sequence[int]], factor: float, missing: int, decimals: int) -> list[list[float | None]]:
    """A grid's raw integers as values with `decimals`, None where missing."""
    def value(raw: int) -> float | int | None:
        if raw == missing:
            return None
        return round(raw * factor, decimals) if decimals else int(round(raw * factor))
    return [[value(raw) for raw in row] for row in rows]


def read_day(path: Path, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    import h5py  # only the fetch tools need it (tools/requirements-meteosat.txt)

    west, south, east, north = bbox
    with h5py.File(path) as stream:
        lats = [round(float(value), 3) for value in stream["y"][:]]
        lons = [round(float(value), 3) for value in stream["x"][:]]
        rows, columns = window(lats, south, north), window(lons, west, east)
        grids = {}
        for name, (key, decimals) in GRIDS.items():
            data = stream[name]
            raw = data[0, rows, columns].tolist()
            grids[key] = scaled(raw, float(data.attrs["scale_factor"][0]), int(data.attrs["_FillValue"][0]), decimals)
    return {"latitudes": lats[rows], "longitudes": lons[columns], **grids}


def fetch(day: date, cache: Path, open_url) -> Path | None:
    """The day's file in the cache, fetched if needed; None when the server has none."""
    target = cache / FILE_NAME.format(day=day)
    if target.is_file() and target.stat().st_size:
        return target
    for attempt in range(3):
        try:
            with open_url(url(day), timeout=300) as response:
                target.write_bytes(response.read())
            return target
        except HTTPError as error:
            if error.code == 404:
                return None
            if error.code == 401:
                raise SystemExit("fetch_meteosat_frm: LSA SAF refused the account in ~/.netrc") from error
        except OSError:
            if attempt == 2:
                return None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--cache", type=Path, default=CACHE, help=f"where the day files are kept (default {CACHE})")
    parser.add_argument("--out", type=Path, default=scenario.METEOSAT_FRM_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_meteosat_frm: the scenario {scenario.NAME} has no METEOSAT_FRM_FILE\n")
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wanted = days(scenario.PLAYBACK_START, scenario.PLAYBACK_END)
    open_url = opener().open
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda day: fetch(day, args.cache, open_url), wanted))
    grid: dict[str, Any] = {}
    found = []
    for day, path in zip(wanted, paths):
        if path is None:
            continue
        read = read_day(path, scenario.MAP_BBOX)
        grid = {"latitudes": read.pop("latitudes"), "longitudes": read.pop("longitudes")}
        found.append({"date": day.isoformat(), "valid_utc": f"{day.isoformat()}T{VALID_HOUR_UTC:02d}:00:00Z", **read})
    missing = [day.isoformat() for day, path in zip(wanted, paths) if path is None]
    args.out.write_text(json.dumps({"cell_deg": 0.05, **grid, "days": found}, separators=(",", ":")) + "\n", encoding="utf-8")
    (args.out.parent / "SOURCE.json").write_text(json.dumps({
        "source": "LSA SAF Fire Risk Map v3 (FRMv3-ERA5), EUMETSAT",
        "url": BASE_URL,
        "licence": LICENCE,
        "attribution": PRODUCT_ATTRIBUTION,
        "valid": f"{VALID_HOUR_UTC:02d}:00 UTC each day (LSA SAF map service)",
        "map_bbox_west_south_east_north": list(scenario.MAP_BBOX),
        "days": len(wanted),
        "days_missing_on_server": missing,
        "grids": {key: name for name, (key, _) in GRIDS.items()},
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(found)} av {len(wanted)} dagar, {len(grid.get('latitudes', []))} x {len(grid.get('longitudes', []))} rutor; {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
