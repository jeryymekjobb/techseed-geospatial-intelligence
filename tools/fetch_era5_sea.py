#!/usr/bin/env python3
"""Fetch hourly ERA5 wind over the sea, where ERA5-Land has no values, as one CSV.

ERA5-Land covers land only, so the wind arrows over the sea are missing
(tools/fetch_era5_land.py leaves those grid points out). ERA5 (dataset
`reanalysis-era5-single-levels`, 0.25° grid) covers the sea as well. This tool
fetches its 10 m wind (u, v) and 2 m temperature around the area and
interpolates them bilinearly to the points of the ERA5-Land 0.1° grid in the
area that the ERA5-Land CSV lacks, and writes the same columns as that CSV
(dewpoint, humidity and precipitation empty) plus `source`.

    .venv/bin/python tools/fetch_era5_sea.py --area 62.6,16.9,62.2,17.8 --start 2026-08-14 --end 2026-08-22 \\
        --land data/sundsvall2026/era5-land/era5-land-sundsvall-2026.csv --raw-dir /tmp/era5-sea \\
        --out data/sundsvall2026/era5-land/era5-sea-sundsvall-2026.csv

Needs `cdsapi` and `netCDF4` (the repository's `.venv`), a CDS account with the
token in `~/.cdsapirc`, and the dataset licence (CC BY 4.0) accepted.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from tools.fetch_era5_land import COLUMNS, requests_for, wind

DATASET = "reanalysis-era5-single-levels"
VARIABLES = ["10m_u_component_of_wind", "10m_v_component_of_wind", "2m_temperature"]
SOURCE = "ERA5, interpolerad från 0,25°"
ATTRIBUTION = (
    "Contains modified Copernicus Climate Change Service information (ERA5, "
    "doi:10.24381/cds.adbb2d47), CC BY 4.0"
)
STEP = 0.1  # the ERA5-Land grid the arrows are on


def grid_points(north: float, west: float, south: float, east: float) -> list[tuple[float, float]]:
    """The 0.1° grid points of the area, as ERA5-Land has them."""
    lats = [round(south + STEP * i, 2) for i in range(round((north - south) / STEP) + 1)]
    lons = [round(west + STEP * i, 2) for i in range(round((east - west) / STEP) + 1)]
    return [(lat, lon) for lat in lats for lon in lons]


def bilinear(latitudes: list[float], longitudes: list[float], field: Any, lat: float, lon: float) -> float:
    """The value at (lat, lon) between the four surrounding grid points (latitudes may run north to south)."""
    def bracket(values: list[float], x: float) -> tuple[int, int, float]:
        ascending = values[0] < values[-1]
        ordered = values if ascending else values[::-1]
        for i in range(len(ordered) - 1):
            if ordered[i] <= x <= ordered[i + 1]:
                share = (x - ordered[i]) / (ordered[i + 1] - ordered[i])
                a, b = (i, i + 1) if ascending else (len(values) - 1 - i, len(values) - 2 - i)
                return a, b, share
        raise ValueError(f"{x} lies outside the grid {values[0]}–{values[-1]}")

    y0, y1, fy = bracket(latitudes, lat)
    x0, x1, fx = bracket(longitudes, lon)
    top = field[y0][x0] * (1 - fx) + field[y0][x1] * fx
    bottom = field[y1][x0] * (1 - fx) + field[y1][x1] * fx
    return float(top * (1 - fy) + bottom * fy)


def land_points(path: Path) -> set[tuple[float, float]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {(round(float(row["latitude"]), 2), round(float(row["longitude"]), 2)) for row in csv.DictReader(stream)}


def rows_for(path: Path, points: list[tuple[float, float]], start: date, end: date) -> list[dict[str, Any]]:
    import netCDF4  # only needed when converting downloaded files

    rows = []
    with netCDF4.Dataset(path) as data:
        times = [datetime.fromtimestamp(int(value), timezone.utc) for value in data.variables["valid_time"][:]]
        latitudes = [float(value) for value in data.variables["latitude"][:]]
        longitudes = [float(value) for value in data.variables["longitude"][:]]
        fields = {name: data.variables[name][:] for name in ("u10", "v10", "t2m")}
        for index, moment in enumerate(times):
            if not start <= moment.date() <= end:
                continue
            for lat, lon in points:
                u, v, t2m = (bilinear(latitudes, longitudes, fields[name][index], lat, lon) for name in ("u10", "v10", "t2m"))
                speed, direction = wind(u, v)
                rows.append({
                    "time_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"), "latitude": lat, "longitude": lon,
                    "u10_ms": round(u, 2), "v10_ms": round(v, 2), "wind_speed_ms": round(speed, 2),
                    "wind_from_deg": round(direction), "t2m_c": round(t2m - 273.15, 1),
                    "d2m_c": "", "rh_pct": "", "precip_mm": "", "source": SOURCE,
                })
    rows.sort(key=lambda row: (row["time_utc"], -row["latitude"], row["longitude"]))
    return rows


def download(area: list[float], start: date, end: date, raw_dir: Path) -> list[Path]:
    import cdsapi

    client = cdsapi.Client(quiet=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for request in requests_for(start, end):
        path = raw_dir / f"era5-{request['year']}-{request['month']}.nc"
        if not path.is_file():
            client.retrieve(DATASET, {
                "product_type": ["reanalysis"], "variable": VARIABLES, **request, "area": area,
                "data_format": "netcdf", "download_format": "unarchived",
            }, str(path))
        paths.append(path)
    return paths


def source_metadata(area: list[float], download_area: list[float], start: date, end: date,
                    land_file: Path, raw_files: list[Path], processed_utc: datetime | None = None) -> dict[str, Any]:
    processed_utc = processed_utc or datetime.now(timezone.utc)
    return {
        "source": "Copernicus Climate Change Service (C3S), ERA5 reanalysis interpolated over sea",
        "dataset": DATASET,
        "doi": "10.24381/cds.adbb2d47",
        "attribution": ATTRIBUTION,
        "licence": "CC BY 4.0",
        "output_area_north_west_south_east": area,
        "download_area_north_west_south_east": download_area,
        "output_period_utc": [start.isoformat(), end.isoformat()],
        "variables": VARIABLES,
        "source_grid_degrees": 0.25,
        "output_grid": "ERA5-Land 0.1-degree points missing from the land CSV",
        "land_input": land_file.name,
        "raw_files": [path.name for path in raw_files],
        "processed_utc": processed_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--area", required=True, help="north,west,south,east in degrees (the ERA5-Land area)")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--land", required=True, type=Path, help="the ERA5-Land CSV whose missing points are filled")
    parser.add_argument("--raw-dir", required=True, type=Path, help="downloaded NetCDF files (reused if present)")
    parser.add_argument("--out", required=True, type=Path, help="output CSV")
    args = parser.parse_args(argv)
    north, west, south, east = (float(value) for value in args.area.split(","))
    # A quarter degree around the area, so every point lies between four ERA5 grid points.
    area = [north, west, south, east]
    download_area = [north + 0.25, west - 0.25, south - 0.25, east + 0.25]
    paths = download(download_area, args.start, args.end, args.raw_dir)
    have = land_points(args.land)
    missing = [point for point in grid_points(north, west, south, east) if point not in have]
    rows = [row for path in paths for row in rows_for(path, missing, args.start, args.end)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*COLUMNS, "source"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.out.with_suffix(".SOURCE.json").write_text(
        json.dumps(source_metadata(area, download_area, args.start, args.end, args.land, paths),
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"{len(rows)} rows, {len(missing)} grid points without ERA5-Land values -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
