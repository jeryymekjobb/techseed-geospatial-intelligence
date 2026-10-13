#!/usr/bin/env python3
"""Fetch MET Norway's archived MEPS weather forecasts, as issued, for the scenario's fire.

MEPS (MetCoOp Ensemble Prediction System, run by MET Norway with SMHI and the Finnish
Meteorological Institute) forecasts the Nordic countries at 2.5 km four times a day, 0-66
hours ahead; MET Norway keeps every run on thredds.met.no. For each run in the scenario's
period this tool reads, over OPeNDAP, only what the demo needs from the post-processed
control run (`meps_mbr0_pp_2_5km_<run>.nc`):

- at the fire's centre (FIRE_CENTRE), hourly 0-66 h: the 10 m wind turned from the
  model's grid to compass directions, the gust, 2 m temperature and relative humidity,
  the accumulated precipitation, the cloud cover and the combined thunderstorm index;
- over the map area (MAP_BBOX), every GRID_STEP-th point: the 10 m wind and the
  accumulated precipitation, for the map's forecast wind;
- over Scandinavia, every ISOBAR_STEP-th point (about 20 km), at the synoptic hours (00, 03 ...
  21 UTC) of the run's first ISOBAR_HOURS hours, the map's weather chart: the air pressure at sea
  level drawn as isobars every hPa with the highs and lows (tools/isobars.py), the rain of the
  three hours up to then as a transparent image and lightning where the thunderstorm index is
  high (tools/weather_chart.py).

It writes data/<scenario>/met-forecast/<run>.json per run and SOURCE.json with the
licence (NLOD and CC BY 4.0, credit MET Norway). These are forecasts as they were issued,
not observations or a reanalysis; the screens say so.

    TECHSEED_SCENARIO=ljusdal2018 .venv/bin/python -m tools.fetch_met_forecasts

A run already fetched is kept; --force fetches it again, and --isobars-only draws the weather
charts of runs fetched before, skipping those already drawn at the present interval (so a run
broken off by MET Norway's server goes on where it stopped).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from app.backend import scenario
from tools import isobars as isobar_lines
from tools import weather_chart

ARCHIVE = "https://thredds.met.no/thredds/dodsC/meps25epsarchive"
AROME_ARCHIVE = "https://thredds.met.no/thredds/dodsC/aromemetcoopstarc"
MEPS_START = datetime(2016, 11, 8, tzinfo=timezone.utc)  # before it, AROME-MetCoOp's deterministic runs
RUN_HOURS = (0, 6, 12, 18)
LEAD_HOURS = 66
GRID_STEP = 2  # every second 2.5 km point: 5 km between the map's arrows
# The Lambert conformal projection of MEPS: standard parallel 63° N, central meridian 15° E.
STANDARD_PARALLEL = 63.0
CENTRAL_MERIDIAN = 15.0
POINT_VARIABLES = {
    "gust_ms": "wind_speed_of_gust",
    "temperature_k": "air_temperature_2m",
    "humidity": "relative_humidity_2m",
    "precipitation_acc_mm": "precipitation_amount_acc",
    "cloud_pct": "cloud_area_fraction",
}
# The weather chart: every ISOBAR_STEP-th point over ISOBAR_AREA (west, south, east, north), the
# synoptic hours of the run's first ISOBAR_HOURS hours (a run is shown until the next one is published).
ISOBAR_STEP = 8
ISOBAR_AREA = (0.0, 54.0, 35.0, 71.0)
ISOBAR_HOURS = 15  # 12 h and a run missing from the archive
LICENCE = "NLOD 2.0 and CC BY 4.0, https://www.met.no/en/free-meteorological-data/Licensing-and-crediting"
ATTRIBUTION = "Väderprognos: MET Norway (MEPS, MetCoOp), NLOD/CC BY 4.0"
OUT_DIR = getattr(scenario, "MET_FORECAST_DIR", None)


def archive_for(run: datetime) -> dict[str, Any]:
    """The archive of a run's time: its file, the model's name and its thunder variable (None without one).
    AROME-MetCoOp until MEPS came in November 2016 (no thunder index); MEPS's post-processed control
    member until 2019; from 2024 MEPS's deterministic run, as an NcML aggregation in 2024 and one file
    from 2025, with a lightning index. The years between are not used by any scenario."""
    if run < MEPS_START:
        return {"url": f"{AROME_ARCHIVE}/{run:%Y/%m/%d}/AROME_MetCoOp_{run:%H}_fp.nc_{run:%Y%m%d}",
                "model": "AROME-MetCoOp (deterministic)", "thunder": None}
    if run.year < 2020:
        return {"url": f"{ARCHIVE}/{run:%Y/%m/%d}/meps_mbr0_pp_2_5km_{run:%Y%m%dT%H}Z.nc",
                "model": "MEPS, control member, post-processed (meps_mbr0_pp_2_5km)", "thunder": "thunderstorm_index_combined"}
    if run.year < 2025:
        return {"url": f"{ARCHIVE}/{run:%Y/%m/%d}/meps_det_sfc_{run:%Y%m%dT%H}Z.ncml",
                "model": "MEPS, deterministic (meps_det_sfc)", "thunder": "lightning_index"}
    return {"url": f"{ARCHIVE}/{run:%Y/%m/%d}/meps_det_2_5km_{run:%Y%m%dT%H}Z.nc",
            "model": "MEPS, deterministic (meps_det_2_5km)", "thunder": "lightning_index"}


def run_url(run: datetime) -> str:
    return archive_for(run)["url"]


def runs(start: datetime, end: datetime) -> list[datetime]:
    """Every run from `start` up to `end`, at RUN_HOURS."""
    moment = start.replace(hour=0, minute=0, second=0, microsecond=0)
    found = []
    while moment <= end:
        if moment >= start and moment.hour in RUN_HOURS:
            found.append(moment)
        moment += timedelta(hours=6) if moment.hour in RUN_HOURS else timedelta(hours=1)
    return found


def true_wind(x_wind: float, y_wind: float, longitude: float) -> tuple[float, float]:
    """The wind's speed (m/s) and the direction it blows from (degrees, 0 north), from the
    projection's x and y components: the grid's north is turned by n * (longitude - 15°)."""
    angle = math.radians(math.sin(math.radians(STANDARD_PARALLEL)) * (longitude - CENTRAL_MERIDIAN))
    east = math.cos(angle) * x_wind + math.sin(angle) * y_wind
    north = -math.sin(angle) * x_wind + math.cos(angle) * y_wind
    speed = math.hypot(east, north)
    from_deg = (math.degrees(math.atan2(-east, -north)) + 360) % 360
    return round(speed, 2), round(from_deg)


def nearest(latitudes: Any, longitudes: Any, point: tuple[float, float]) -> tuple[int, int]:
    import numpy as np

    lat, lon = point
    distance = (latitudes - lat) ** 2 + ((longitudes - lon) * math.cos(math.radians(lat))) ** 2
    j, i = np.unravel_index(int(np.argmin(distance)), distance.shape)
    return int(j), int(i)


def box(latitudes: Any, longitudes: Any, bbox: Sequence[float]) -> tuple[slice, slice]:
    """The grid's rows and columns that hold the area (west, south, east, north)."""
    import numpy as np

    west, south, east, north = bbox
    rows, cols = np.where((latitudes >= south) & (latitudes <= north) & (longitudes >= west) & (longitudes <= east))
    return slice(int(rows.min()), int(rows.max()) + 1, GRID_STEP), slice(int(cols.min()), int(cols.max()) + 1, GRID_STEP)


def series(dataset: Any, name: str, j: Any, i: Any) -> Any:
    """A variable's values over the run's hours at grid rows j and columns i (its single
    height level dropped)."""
    import numpy as np

    variable = dataset[name]
    index = (slice(0, LEAD_HOURS + 1),) + (0,) * (variable.ndim - 3) + (j, i)
    return np.ma.filled(variable[index].astype(float), np.nan)


def rounded(values: Any, digits: int) -> list[float | None]:
    return [None if math.isnan(value) else round(float(value), digits) for value in values]


def fetch_run(run: datetime, grid: dict[str, Any]) -> dict[str, Any]:
    """One run's point series and map grid."""
    import netCDF4
    import numpy as np

    archive = archive_for(run)
    with netCDF4.Dataset(archive["url"]) as dataset:
        issued = (datetime.fromtimestamp(float(dataset["forecast_reference_time"][:]), tz=timezone.utc)
                  if "forecast_reference_time" in dataset.variables else run)
        times = [datetime.fromtimestamp(float(value), tz=timezone.utc) for value in dataset["time"][: LEAD_HOURS + 1]]
        j, i = grid["point"]
        x_wind, y_wind = series(dataset, "x_wind_10m", j, i), series(dataset, "y_wind_10m", j, i)
        winds = [true_wind(u, v, grid["point_longitude"]) for u, v in zip(x_wind, y_wind)]
        point: dict[str, Any] = {"wind_ms": [speed for speed, _ in winds], "wind_from_deg": [direction for _, direction in winds]}
        for key, name in POINT_VARIABLES.items():
            values = series(dataset, name, j, i)
            if key == "humidity" and np.nanmax(values) <= 1.5:
                values = values * 100  # a fraction in the file
            point[key] = rounded(values, 1)
        point["thunder_index"] = rounded(series(dataset, archive["thunder"], j, i), 2) if archive["thunder"] else None
        rows, cols = grid["rows"], grid["cols"]
        x_grid, y_grid = series(dataset, "x_wind_10m", rows, cols), series(dataset, "y_wind_10m", rows, cols)
        precipitation = series(dataset, "precipitation_amount_acc", rows, cols)
        cells = []
        for row, (latitude_row, longitude_row) in enumerate(zip(grid["latitudes"], grid["longitudes"])):
            for col, (latitude, longitude) in enumerate(zip(latitude_row, longitude_row)):
                pairs = [true_wind(float(x_grid[hour, row, col]), float(y_grid[hour, row, col]), longitude)
                         for hour in range(len(times))]
                cells.append({"latitude": round(latitude, 4), "longitude": round(longitude, 4),
                              "wind_ms": [speed for speed, _ in pairs], "wind_from_deg": [direction for _, direction in pairs],
                              "precipitation_acc_mm": rounded(precipitation[:, row, col], 1)})
    return {
        "issued_utc": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "times_utc": [moment.strftime("%Y-%m-%dT%H:%M:%SZ") for moment in times],
        "point": {"latitude": grid["point_latitude"], "longitude": grid["point_longitude"], **point},
        "grid": cells,
        "source": archive["url"],
        "model": archive["model"],
        "thunder_variable": archive["thunder"],
    }


def fetch_isobars(run: datetime, area: dict[str, Any]) -> list[dict[str, Any]]:
    """The run's weather charts at its synoptic hours up to ISOBAR_HOURS: { valid_utc, lines, centres,
    rain_png, rain_bounds, thunder }."""
    import netCDF4
    import numpy as np

    charts = []
    with netCDF4.Dataset(run_url(run)) as dataset:
        times = [datetime.fromtimestamp(float(value), tz=timezone.utc) for value in dataset["time"][: ISOBAR_HOURS + 1]]
        wanted = [index for index, moment in enumerate(times) if moment.hour % 3 == 0]
        if not wanted:
            return charts
        last = wanted[-1] + 1
        window = (slice(0, last), area["rows"], area["cols"])

        def read(name: str) -> Any:
            variable = dataset[name]
            index = (window[0],) + (0,) * (variable.ndim - 3) + window[1:]
            return np.ma.filled(variable[index].astype(float), np.nan)

        thunder_variable = archive_for(run)["thunder"]
        pressure, accumulated = read("air_pressure_at_sea_level") / 100.0, read("precipitation_amount_acc")
        thunder = read(thunder_variable) if thunder_variable else None
        for index in wanted:
            chart = isobar_lines.isobars(pressure[index], area["latitudes"], area["longitudes"])
            for line in chart["lines"]:  # every second point is enough at 20 km
                line["coords"] = line["coords"][::2] + ([line["coords"][-1]] if len(line["coords"]) % 2 == 0 else [])
            rain = accumulated[index] - accumulated[max(0, index - 3)]  # the three hours up to the chart (fewer at the run's start)
            charts.append({
                "valid_utc": times[index].strftime("%Y-%m-%dT%H:%M:%SZ"), **chart,
                "rain_png": weather_chart.rain_png(rain, area["xs"], area["ys"], ISOBAR_AREA),
                "rain_bounds": [[ISOBAR_AREA[1], ISOBAR_AREA[0]], [ISOBAR_AREA[3], ISOBAR_AREA[2]]],
                "thunder": None if thunder is None else weather_chart.thunder_marks(
                    np.nanmax(thunder[max(0, index - 2):index + 1], axis=0), area["latitudes"], area["longitudes"],
                    weather_chart.THUNDER_THRESHOLDS[thunder_variable]),
            })
    return charts


def isobar_area(first_run: datetime) -> dict[str, Any]:
    """The weather chart's grid: every ISOBAR_STEP-th point over ISOBAR_AREA."""
    import netCDF4
    import numpy as np

    with netCDF4.Dataset(run_url(first_run)) as dataset:
        latitudes, longitudes = dataset["latitude"][:], dataset["longitude"][:]
        xs, ys = np.asarray(dataset["x"][:]), np.asarray(dataset["y"][:])
    west, south, east, north = ISOBAR_AREA
    rows, cols = np.where((latitudes >= south) & (latitudes <= north) & (longitudes >= west) & (longitudes <= east))
    rows = slice(int(rows.min()), int(rows.max()) + 1, ISOBAR_STEP)
    cols = slice(int(cols.min()), int(cols.max()) + 1, ISOBAR_STEP)
    return {"rows": rows, "cols": cols, "latitudes": np.asarray(latitudes[rows, cols]), "longitudes": np.asarray(longitudes[rows, cols]),
            "xs": xs[cols], "ys": ys[rows]}


def retried(fetch: Any, *args: Any, attempts: int = 3) -> Any:
    """`fetch(*args)`, again after a pause when MET Norway's server fails for a moment ("DAP failure",
    "DAP server error"); a run missing from the archive fails every time and is reported then."""
    for attempt in range(attempts):
        try:
            return fetch(*args)
        except (RuntimeError, OSError):
            if attempt == attempts - 1:
                raise
            time.sleep(10 * (attempt + 1))
    return None


def grid_for(first_run: datetime) -> dict[str, Any]:
    """The fire's grid point and the map's cells, from the first run's coordinates (the same grid in every run)."""
    import netCDF4

    with netCDF4.Dataset(run_url(first_run)) as dataset:
        latitudes, longitudes = dataset["latitude"][:], dataset["longitude"][:]
        j, i = nearest(latitudes, longitudes, scenario.FIRE_CENTRE)
        rows, cols = box(latitudes, longitudes, scenario.MAP_BBOX)
        return {"point": (j, i), "point_latitude": round(float(latitudes[j, i]), 4), "point_longitude": round(float(longitudes[j, i]), 4),
                "rows": rows, "cols": cols, "latitudes": latitudes[rows, cols].tolist(), "longitudes": longitudes[rows, cols].tolist()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--force", action="store_true", help="fetch runs already fetched again")
    parser.add_argument("--isobars-only", action="store_true", help="add the isobars to runs already fetched")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_met_forecasts: the scenario {scenario.NAME} has no MET_FORECAST_DIR\n")
    start = datetime.combine(scenario.PERIOD_START, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(scenario.PERIOD_END, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=18)
    wanted = runs(start, end)
    args.out.mkdir(parents=True, exist_ok=True)
    grid = retried(grid_for, wanted[0])
    area = retried(isobar_area, wanted[0])
    fetched, missing = [], []
    for run in wanted:
        target = args.out / f"{run:%Y%m%dT%H}Z.json"
        if args.isobars_only:
            if target.is_file():
                record = json.loads(target.read_text(encoding="utf-8"))
                if record.get("isobar_interval_hpa") == isobar_lines.INTERVAL_HPA and not args.force:
                    fetched.append(run)  # drawn already: a run broken off goes on from here
                    continue
                record["isobars"] = retried(fetch_isobars, run, area)
                record["isobar_interval_hpa"] = isobar_lines.INTERVAL_HPA
                target.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")
                fetched.append(run)
                print(f"{run:%Y-%m-%d %H} UTC: isobarer för {len(record['isobars'])} tider", flush=True)
            else:
                missing.append(f"{run:%Y-%m-%dT%H}Z: not fetched")
            continue
        if target.is_file() and not args.force:
            fetched.append(run)
            continue
        try:
            record = {**retried(fetch_run, run, grid), "isobars": retried(fetch_isobars, run, area),
                      "isobar_interval_hpa": isobar_lines.INTERVAL_HPA}
        except OSError as exc:  # not in the archive
            missing.append(f"{run:%Y-%m-%dT%H}Z: {exc}")
            print(f"saknas: {run:%Y-%m-%d %H} UTC", flush=True)
            continue
        target.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")
        fetched.append(run)
        print(f"{run:%Y-%m-%d %H} UTC: {len(record['times_utc'])} timmar, {len(record['grid'])} rutor", flush=True)
    (args.out / "SOURCE.json").write_text(json.dumps({
        "model": sorted({archive_for(run)["model"] for run in wanted}),
        "archive": sorted({archive_for(run)["url"].rsplit("/", 4)[0] for run in wanted}),
        "runs_utc": [f"{run:%Y-%m-%dT%H:%M:%SZ}" for run in fetched],
        "missing": missing,
        "point": scenario.FIRE_CENTRE,
        "map_bbox_west_south_east_north": list(scenario.MAP_BBOX),
        "grid_step": GRID_STEP,
        "isobars": {"area_west_south_east_north": list(ISOBAR_AREA), "step": ISOBAR_STEP, "hours": ISOBAR_HOURS,
                    "interval_hpa": isobar_lines.INTERVAL_HPA},
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": "OPeNDAP subset with netCDF4; 10 m wind turned from the Lambert grid (lat_1 63, lon_0 15) to compass "
                      "directions; relative humidity in per cent; isobars traced by tools/isobars.py from the smoothed pressure",
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "note": "Forecasts as issued at the time, not observations or a reanalysis.",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(fetched)} körningar i {args.out}, {len(missing)} saknas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
