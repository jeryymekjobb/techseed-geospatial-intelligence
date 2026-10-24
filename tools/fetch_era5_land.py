#!/usr/bin/env python3
"""Fetch hourly ERA5-Land reanalysis for an area and period as one CSV.

Requests 10 m wind (u, v), 2 m temperature, 2 m dewpoint and total precipitation
from the Copernicus Climate Data Store (dataset `reanalysis-era5-land`, 0.1°
grid), and writes one row per grid point and UTC hour with wind speed and the
direction the wind blows from, relative humidity (from temperature and dewpoint)
and hourly precipitation (ERA5-Land precipitation accumulates from 00 UTC).

Needs `cdsapi` and `netCDF4` (run with the repository's `.venv`), a CDS account
with the token in `~/.cdsapirc`, and the dataset licence (CC BY 4.0) accepted.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DATASET = "reanalysis-era5-land"
VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
    "2m_dewpoint_temperature",
    "total_precipitation",
]
ATTRIBUTION = (
    "Contains modified Copernicus Climate Change Service information (ERA5-Land, "
    "doi:10.24381/cds.e2161bac), CC BY 4.0"
)
COLUMNS = [
    "time_utc", "latitude", "longitude", "u10_ms", "v10_ms", "wind_speed_ms", "wind_from_deg",
    "t2m_c", "d2m_c", "rh_pct", "precip_mm",
]


def wind(u: float, v: float) -> tuple[float, float]:
    """Speed and the meteorological direction the wind blows from (0 = north, 90 = east)."""
    return math.hypot(u, v), (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0


def relative_humidity(t_c: float, d_c: float) -> float:
    """Magnus formula over water, in percent, capped at 100."""
    def saturation(x: float) -> float:
        return math.exp(17.625 * x / (243.04 + x))

    return min(100.0, 100.0 * saturation(d_c) / saturation(t_c))


def hourly_precipitation(accumulated: dict[datetime, float]) -> dict[datetime, float]:
    """ERA5-Land `tp` accumulates since 00 UTC; the 00 UTC value closes the previous day."""
    result = {}
    for moment, value in accumulated.items():
        if moment.hour == 1:
            result[moment] = value
        else:
            previous = accumulated.get(moment - timedelta(hours=1))
            result[moment] = value - previous if previous is not None else math.nan
    return {moment: max(0.0, value) * 1000.0 if not math.isnan(value) else math.nan for moment, value in result.items()}


def requests_for(start: date, end: date) -> list[dict[str, Any]]:
    """One request per month, with the days of the period in that month and all hours."""
    days: dict[tuple[int, int], list[str]] = {}
    current = start
    while current <= end:
        days.setdefault((current.year, current.month), []).append(f"{current.day:02d}")
        current += timedelta(days=1)
    return [
        {"year": str(year), "month": f"{month:02d}", "day": values, "time": [f"{hour:02d}:00" for hour in range(24)]}
        for (year, month), values in sorted(days.items())
    ]


def read_netcdf(path: Path) -> Iterable[dict[str, Any]]:
    import netCDF4  # only needed when converting downloaded files

    with netCDF4.Dataset(path) as data:
        times = [datetime.fromtimestamp(int(value), timezone.utc) for value in data.variables["valid_time"][:]]
        latitudes = [round(float(value), 2) for value in data.variables["latitude"][:]]
        longitudes = [round(float(value), 2) for value in data.variables["longitude"][:]]
        fields = {name: data.variables[name][:] for name in ("u10", "v10", "t2m", "d2m", "tp")}
        for t_index, moment in enumerate(times):
            for y, latitude in enumerate(latitudes):
                for x, longitude in enumerate(longitudes):
                    values = {name: field[t_index, y, x] for name, field in fields.items()}
                    if any(getattr(value, "mask", False) is True for value in values.values()):
                        continue  # no land value at this grid point
                    yield {"time": moment, "latitude": latitude, "longitude": longitude,
                           **{name: float(value) for name, value in values.items()}}


def rows_from(records: Iterable[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
    by_point: dict[tuple[float, float], dict[datetime, dict[str, Any]]] = {}
    for record in records:
        by_point.setdefault((record["latitude"], record["longitude"]), {})[record["time"]] = record
    rows = []
    for (latitude, longitude), series in by_point.items():
        precipitation = hourly_precipitation({moment: record["tp"] for moment, record in series.items()})
        for moment, record in series.items():
            if not start <= moment.date() <= end:
                continue
            # ERA5-Land covers land only: a point at sea has no values.
            if any(math.isnan(record[name]) for name in ("u10", "v10", "t2m", "d2m")):
                continue
            speed, direction = wind(record["u10"], record["v10"])
            t_c, d_c = record["t2m"] - 273.15, record["d2m"] - 273.15
            rows.append({
                "time_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "latitude": latitude,
                "longitude": longitude,
                "u10_ms": round(record["u10"], 2),
                "v10_ms": round(record["v10"], 2),
                "wind_speed_ms": round(speed, 2),
                "wind_from_deg": round(direction),
                "t2m_c": round(t_c, 1),
                "d2m_c": round(d_c, 1),
                "rh_pct": round(relative_humidity(t_c, d_c)),
                "precip_mm": "" if math.isnan(precipitation[moment]) else round(precipitation[moment], 2),
            })
    rows.sort(key=lambda row: (row["time_utc"], -row["latitude"], row["longitude"]))
    return rows


def download(area: list[float], start: date, end: date, raw_dir: Path) -> list[Path]:
    import cdsapi

    client = cdsapi.Client(quiet=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    # The day before the period is fetched too, so the first hour's precipitation can be de-accumulated.
    paths = []
    for request in requests_for(start - timedelta(days=1), end):
        path = raw_dir / f"era5-land-{request['year']}-{request['month']}.nc"
        if not path.is_file():
            client.retrieve(DATASET, {
                "variable": VARIABLES, **request, "area": area,
                "data_format": "netcdf", "download_format": "unarchived",
            }, str(path))
        paths.append(path)
    return paths


def source_metadata(area: list[float], start: date, end: date, raw_files: list[Path], processed_utc: datetime | None = None) -> dict[str, Any]:
    processed_utc = processed_utc or datetime.now(timezone.utc)
    return {
        "source": "Copernicus Climate Change Service (C3S), ERA5-Land reanalysis",
        "dataset": DATASET,
        "doi": "10.24381/cds.e2161bac",
        "attribution": ATTRIBUTION,
        "licence": "CC BY 4.0",
        "area_north_west_south_east": area,
        "output_period_utc": [start.isoformat(), end.isoformat()],
        "request_period_utc": [(start - timedelta(days=1)).isoformat(), end.isoformat()],
        "variables": VARIABLES,
        "frequency": "hourly",
        "grid_resolution_degrees": 0.1,
        "raw_files": [path.name for path in raw_files],
        "processed_utc": processed_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--area", required=True, help="north,west,south,east in degrees")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--raw-dir", required=True, type=Path, help="downloaded NetCDF files (reused if present)")
    parser.add_argument("--out", required=True, type=Path, help="output CSV")
    args = parser.parse_args(argv)
    area = [float(value) for value in args.area.split(",")]
    paths = download(area, args.start, args.end, args.raw_dir)
    records = [record for path in paths for record in read_netcdf(path)]
    rows = rows_from(records, args.start, args.end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.out.with_suffix(".SOURCE.json").write_text(
        json.dumps(source_metadata(area, args.start, args.end, paths), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    points = len({(row["latitude"], row["longitude"]) for row in rows})
    without = len({(record["latitude"], record["longitude"]) for record in records}) - points
    print(f"{len(rows)} rows, {points} grid points -> {args.out}"
          + (f"; {without} grid points without values (at sea, outside ERA5-Land) left out" if without else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
