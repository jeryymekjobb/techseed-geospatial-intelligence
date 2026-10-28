#!/usr/bin/env python3
"""Fetch EFAS's river-flow forecasts, as issued, for the scenario's flow stations.

The European Flood Awareness System (Copernicus Emergency Management Service) keeps its
operational forecasts in the Early Warning Data Store (EWDS, dataset efas-forecast). This tool
asks once for ECMWF's high-resolution run at 00 UTC on each day of the scenario's EFAS_ISSUES,
6-240 hours ahead (the mean flow of the last six hours, dis06), over EFAS_AREA, with the key in
~/.ewdsapirc, and keeps the GRIB file in RAW_DIR; a later run reuses it. For each of EFAS_STATIONS
(ids of /api/hydro's stations) it takes the grid cell with the largest mean flow within CELL_KM of
the station, since the river runs in the cell that drains the most, and writes each issue's flows
there to EFAS_DIR/forecasts.json.

    TECHSEED_SCENARIO=ljungan-aug2023 .venv/bin/python -m tools.fetch_efas_forecasts

EFAS's data are free under the CEMS-FLOODS licence, which asks for the notice below and says the
data are information, not a flood warning: only the national services (SMHI) warn. The grid in
2023 is about 5 km, so small streams are not in it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.backend import hydro, scenario

DATASET = "efas-forecast"
VARIABLE = "river_discharge_in_the_last_6_hours"
LEAD_HOURS = range(6, 241, 6)
# The river's cell is the one with the largest mean flow this close to the station.
CELL_KM = 4.0
# When an issue is taken to have reached its users after its run time: an assumption, not EFAS's schedule.
AVAILABLE_AFTER_HOURS = 12
ATTRIBUTION = "Contains modified Copernicus Emergency Management Service information 2023 (EFAS, CEMS-FLOODS licence)"
CREDENTIALS = Path.home() / ".ewdsapirc"


def request(first: date, last: date, area: tuple[float, float, float, float]) -> dict[str, Any]:
    """The EWDS request for the 00 UTC runs from `first` to `last` (one month), area north, west, south, east."""
    return {
        "system_version": ["operational"], "originating_centre": "ecmwf", "product_type": ["high_resolution_forecast"],
        "variable": [VARIABLE], "model_levels": "surface_level",
        "year": [str(first.year)], "month": [f"{first.month:02d}"],
        "day": [f"{day:02d}" for day in range(first.day, last.day + 1)], "time": ["00:00"],
        "leadtime_hour": [str(hours) for hours in LEAD_HOURS],
        "data_format": "grib", "download_format": "unarchived", "area": list(area),
    }


def download(target: Path, payload: dict[str, Any]) -> None:
    import cdsapi

    settings = dict(line.strip().split(": ", 1) for line in CREDENTIALS.read_text(encoding="utf-8").splitlines() if ": " in line)
    client = cdsapi.Client(url=settings["url"], key=settings["key"], quiet=True)
    part = target.with_suffix(".part")
    client.retrieve(DATASET, payload, str(part))
    os.replace(part, target)


def read_grib(path: Path) -> tuple[list[float], list[float], list[tuple[datetime, datetime, list[float]]]]:
    """The grid's latitudes and longitudes and each field's (run time, valid time, flows); missing values None."""
    import eccodes

    fields = []
    latitudes = longitudes = []
    with path.open("rb") as stream:
        while (handle := eccodes.codes_grib_new_from_file(stream)) is not None:
            try:
                if not fields:
                    latitudes = list(eccodes.codes_get_array(handle, "latitudes"))
                    longitudes = list(eccodes.codes_get_array(handle, "longitudes"))
                missing = eccodes.codes_get(handle, "missingValue")
                values = [None if value == missing else float(value) for value in eccodes.codes_get_values(handle)]
                stamp = str(eccodes.codes_get(handle, "dataDate"))
                run = datetime(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]), tzinfo=timezone.utc)
                run += timedelta(hours=int(eccodes.codes_get(handle, "dataTime")) // 100)
                fields.append((run, run + timedelta(hours=int(eccodes.codes_get(handle, "endStep"))), values))
            finally:
                eccodes.codes_release(handle)
    return latitudes, longitudes, fields


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return math.hypot((lat1 - lat2) * 111.2, (lon1 - lon2) * 111.2 * math.cos(math.radians((lat1 + lat2) / 2)))


def river_cell(latitudes: list[float], longitudes: list[float], fields: list[tuple[datetime, datetime, list[float]]],
               latitude: float, longitude: float) -> int | None:
    """The cell within CELL_KM of the place with the largest mean flow over the fields, or None."""
    best, best_mean = None, -1.0
    for index, (lat, lon) in enumerate(zip(latitudes, longitudes)):
        if distance_km(lat, lon, latitude, longitude) > CELL_KM:
            continue
        values = [field[2][index] for field in fields if field[2][index] is not None]
        if values and sum(values) / len(values) > best_mean:
            best, best_mean = index, sum(values) / len(values)
    return best


def forecasts(latitudes: list[float], longitudes: list[float], fields: list[tuple[datetime, datetime, list[float]]],
              stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each station its cell and each issue's flows in time order."""
    stamp = lambda moment: moment.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    result = []
    for station in stations:
        index = river_cell(latitudes, longitudes, fields, station["latitude"], station["longitude"])
        if index is None:
            continue
        issues: dict[datetime, list[dict[str, Any]]] = {}
        for run, valid, values in fields:
            if values[index] is not None:
                issues.setdefault(run, []).append({"time_utc": stamp(valid), "value": round(values[index], 1)})
        result.append({
            "id": station["id"], "name": station["name"],
            "cell": {"latitude": round(latitudes[index], 4), "longitude": round(longitudes[index], 4),
                     "distance_km": round(distance_km(latitudes[index], longitudes[index], station["latitude"], station["longitude"]), 1)},
            "issues": [{"issued_utc": stamp(run), "available_utc": stamp(run + timedelta(hours=AVAILABLE_AFTER_HOURS)),
                        "values": sorted(values, key=lambda item: item["time_utc"])} for run, values in sorted(issues.items())],
        })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.EFAS_DIR)
    args = parser.parse_args(argv)
    if args.out is None or not scenario.EFAS_STATIONS or not scenario.EFAS_ISSUES:
        parser.exit(1, f"fetch_efas_forecasts: the scenario {scenario.NAME} has no EFAS forecasts\n")
    first, last = scenario.EFAS_ISSUES
    raw = args.out / "raw" / f"efas-hres-{first:%Y%m%d}-{last:%Y%m%d}.grib"
    if not raw.is_file():
        if not CREDENTIALS.is_file():
            parser.exit(1, f"fetch_efas_forecasts: {CREDENTIALS} is missing (an EWDS account, its CEMS-FLOODS licence accepted)\n")
        raw.parent.mkdir(parents=True, exist_ok=True)
        print(f"Asking EWDS for EFAS's runs {first} to {last}; the queue can take an hour or more", flush=True)
        download(raw, request(first, last, scenario.EFAS_AREA))
    latitudes, longitudes, fields = read_grib(raw)
    known = {station["id"]: station for station in (hydro.stations() or {}).get("stations", [])}
    missing = [key for key in scenario.EFAS_STATIONS if key not in known]
    if missing:
        parser.exit(1, f"fetch_efas_forecasts: no such station in /api/hydro: {', '.join(missing)} (fetch the flows first)\n")
    result = forecasts(latitudes, longitudes, fields, [known[key] for key in scenario.EFAS_STATIONS])
    for station in result:
        print(f"{station['name']}: cell {station['cell']['distance_km']} km away, {len(station['issues'])} issues", flush=True)
    (args.out / "forecasts.json").write_text(json.dumps({
        "source": ATTRIBUTION, "dataset": DATASET, "product": "ECMWF high-resolution run, 00 UTC, mean flow of the last 6 hours",
        "available_after_hours": AVAILABLE_AFTER_HOURS, "raw_file": raw.name,
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stations": result,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
