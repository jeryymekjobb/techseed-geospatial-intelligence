#!/usr/bin/env python3
"""Hindcast of fire-spread forecasts for the Västmanland 2014 fire.

At every satellite pass the fire front is estimated from the FIRMS detections so
far, a spread forecast is made with data up to that pass only, and the forecast
is compared with the detections that followed. Writes a JSON result with:

- observed spread between passes (rate and direction) next to the wind and the
  FBP model rate;
- daily Fire Weather Index values;
- forecast skill per horizon and weather mode (persistence of the weather at the
  forecast time, or the actual ERA5-Land weather, which no forecaster had);
- arrival-time skill for places, buildings, roads and railways (OSM).

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from app.backend import scenario
from tools import fire_spread as fs
from tools.firms_extract import select_detections

HORIZONS_H = (3, 6, 12, 24)
BANDS = {"low": 0.5, "central": 1.0, "high": 2.0}  # factors on the calibrated rate
FUEL = "C-2"
WEATHER_POINT = (59.9, 16.2)  # ERA5-Land grid point nearest the fire's centre
REACH_DISTANCE_M = 750.0      # a target counts as reached when a detection lies this close
CELL_M = 500.0
MIN_ADVANCE_M = 300.0
# Passes of different satellites close in time see fire that burned during an earlier
# gap; such short intervals overstate the rate, so they are not used for calibration.
MIN_INTERVAL_H = 1.5


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def load_weather(paths: Sequence[Path]) -> list[fs.Weather]:
    rows: dict[datetime, fs.Weather] = {}
    for path in paths:
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (float(row["latitude"]), float(row["longitude"])) != WEATHER_POINT:
                    continue
                moment = parse_time(row["time_utc"])
                rows[moment] = fs.Weather(
                    moment, float(row["t2m_c"]), float(row["rh_pct"]), float(row["wind_speed_ms"]) * 3.6,
                    float(row["wind_from_deg"]), float(row["precip_mm"] or 0.0),
                )
    return [rows[moment] for moment in sorted(rows)]


def load_weather_smhi(raw_dir: Path, station: str, start: datetime, end: datetime) -> list[fs.Weather]:
    """Hourly weather from SMHI archives saved by tools/fetch_smhi_weather.py --raw-dir."""
    from tools.fetch_smhi_weather import parse_archive

    columns = {1: "t", 6: "rh", 4: "ws", 3: "wd", 7: "pr"}
    values: dict[datetime, dict[str, float]] = {}
    for parameter, name in columns.items():
        archive = parse_archive((raw_dir / f"raw-{station}-{parameter}.csv").read_text(encoding="utf-8-sig"))
        for day, clock, value, _ in archive["rows"]:
            moment = datetime.fromisoformat(f"{day}T{clock}:00+00:00")
            if start <= moment <= end and value != "":
                values.setdefault(moment, {})[name] = float(value)
    return [
        fs.Weather(moment, item["t"], item["rh"], item["ws"] * 3.6, item["wd"], item.get("pr", 0.0))
        for moment, item in sorted(values.items())
        if {"t", "rh", "ws", "wd"} <= set(item)
    ]


def load_targets(path: Path, projector: fs.Projector) -> dict[tuple[str, int, int], dict[str, Any]]:
    """500 m cells per target kind, with the names of places in the cell."""
    cells: dict[tuple[str, int, int], dict[str, Any]] = {}
    collection = json.loads(path.read_text(encoding="utf-8"))
    for feature in collection["features"]:
        kind = feature["properties"]["kind"]
        geometry = feature["geometry"]
        coordinates = [geometry["coordinates"]] if geometry["type"] == "Point" else geometry["coordinates"]
        for lon, lat in coordinates:
            x, y = projector.xy(lat, lon)
            key = (kind, int(math.floor(x / CELL_M)), int(math.floor(y / CELL_M)))
            cell = cells.setdefault(key, {"kind": kind, "centre": ((key[1] + 0.5) * CELL_M, (key[2] + 0.5) * CELL_M), "names": set()})
            if kind == "place" and feature["properties"].get("name"):
                cell["names"].add(feature["properties"]["name"])
    return cells


def observed_arrivals(cells: dict, detections: Sequence[tuple[datetime, fs.Point]]) -> dict:
    arrivals = {}
    for key, cell in cells.items():
        cx, cy = cell["centre"]
        for moment, (x, y) in detections:  # detections are in time order
            if abs(x - cx) <= REACH_DISTANCE_M and abs(y - cy) <= REACH_DISTANCE_M and math.hypot(x - cx, y - cy) <= REACH_DISTANCE_M:
                arrivals[key] = moment
                break
    return arrivals


def steps_for(mode: str, start: datetime, hours: int, weather: dict[datetime, fs.Weather], fire_weather: fs.FireWeather, factor: float) -> list[fs.SpreadStep]:
    now = weather.get(start.replace(minute=0, second=0, microsecond=0))
    steps = []
    for hour in range(1, hours + 1):
        moment = start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=hour)
        if mode == "persistence":
            item = fs.Weather(moment, now.temp_c, now.rh_pct, now.wind_kmh, now.wind_from_deg, 0.0)
            steps.append(fs.model_step(fire_weather, item, FUEL, factor, ffmc_override=fire_weather.ffmc_hour.get(now.time)))
        else:
            item = weather.get(moment)
            if item is None:
                break
            steps.append(fs.model_step(fire_weather, item, FUEL, factor))
    return steps


def first_reaching_hour(point: fs.Point, fronts: Sequence[Sequence[fs.Point]]) -> int | None:
    """First hourly front within REACH_DISTANCE_M of the point; fronts only grow, so search binary."""
    def reaches(front: Sequence[fs.Point]) -> bool:
        xs = [p[0] for p in front]
        ys = [p[1] for p in front]
        if not (min(xs) - REACH_DISTANCE_M <= point[0] <= max(xs) + REACH_DISTANCE_M
                and min(ys) - REACH_DISTANCE_M <= point[1] <= max(ys) + REACH_DISTANCE_M):
            return False
        return fs.distance_to_hull(point, front) <= REACH_DISTANCE_M

    if not fronts or not reaches(fronts[-1]):
        return None
    low, high = 0, len(fronts) - 1
    while low < high:
        middle = (low + high) // 2
        if reaches(fronts[middle]):
            high = middle
        else:
            low = middle + 1
    return low + 1


def mean_model_ros(start: datetime, end: datetime, weather: dict, fire_weather: fs.FireWeather) -> float:
    values = []
    moment = start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while moment <= end + timedelta(hours=1):
        if moment in weather:
            values.append(fs.model_step(fire_weather, weather[moment], FUEL, 1.0).ros_m_per_h)
        moment += timedelta(hours=1)
    return statistics.mean(values) if values else 0.0


def analyse(args: argparse.Namespace) -> dict[str, Any]:
    kept, _, _ = select_detections(scenario.FIRMS_FILES, start=scenario.PERIOD_START, end=scenario.PERIOD_END, bbox=scenario.FIRE_BBOX)
    projector = fs.Projector(*scenario.FIRE_CENTRE)
    detections = [(parse_time(item["acq_datetime_utc"]), projector.xy(item["latitude"], item["longitude"])) for item in kept]
    if args.weather_smhi:
        hourly = load_weather_smhi(
            args.weather_smhi, args.smhi_station,
            datetime(2014, 5, 1, tzinfo=timezone.utc), datetime(2014, 8, 15, tzinfo=timezone.utc),
        )
    else:
        hourly = load_weather(args.weather)
    weather = {item.time: item for item in hourly}
    fire_weather = fs.FireWeather(hourly).compute()
    passes = fs.group_passes(detections)
    cells = load_targets(args.targets, projector)
    arrivals = observed_arrivals(cells, detections)

    # Observed spread between consecutive passes.
    intervals = []
    cumulative: list[fs.Point] = []
    hulls = []
    for index, current in enumerate(passes):
        previous_hull = fs.convex_hull(cumulative) if cumulative else []
        if index and len(previous_hull) >= 3:
            start = passes[index - 1].time
            hours = (current.time - start).total_seconds() / 3600.0
            advance, direction = fs.observed_advance(previous_hull, current.points, MIN_ADVANCE_M)
            mid = (start + (current.time - start) / 2).replace(minute=0, second=0, microsecond=0)
            wind = weather.get(mid)
            model = mean_model_ros(start, current.time, weather, fire_weather)
            intervals.append({
                "start_utc": start.isoformat(), "end_utc": current.time.isoformat(), "hours": round(hours, 2),
                "new_points": len(current.points), "advance_m": round(advance), "short_interval": hours < MIN_INTERVAL_H, "observed_ros_m_per_h": round(advance / hours) if hours else None,
                "observed_direction_deg": round(direction) if direction is not None else None,
                "wind_from_deg": wind.wind_from_deg if wind else None, "wind_kmh": round(wind.wind_kmh, 1) if wind else None,
                "downwind_deg": (wind.wind_from_deg + 180) % 360 if wind else None,
                "model_ros_m_per_h": round(model),
                "direction_error_deg": round(fs.angle_difference(direction, (wind.wind_from_deg + 180) % 360)) if direction is not None and wind else None,
            })
        cumulative.extend(current.points)
        hulls.append(fs.convex_hull(cumulative))

    def calibration(at: datetime) -> float:
        ratios = [
            item["observed_ros_m_per_h"] / item["model_ros_m_per_h"]
            for item in intervals
            if parse_time(item["end_utc"]) <= at and parse_time(item["end_utc"]) > at - timedelta(hours=24)
            and item["observed_ros_m_per_h"] and item["model_ros_m_per_h"] > 0 and not item["short_interval"]
        ]
        return min(10.0, max(0.1, statistics.median(ratios))) if ratios else 1.0

    # Forecasts at every pass, compared with later detections and target arrivals.
    skill: dict[str, dict[str, dict[str, list[float]]]] = {}
    arrival_errors: dict[str, dict[str, list[dict[str, Any]]]] = {}
    forecasts_made = 0
    for index, current in enumerate(passes):
        hull = hulls[index]
        if len(hull) < 3 or current.time.replace(minute=0, second=0, microsecond=0) not in weather:
            continue
        forecasts_made += 1
        factor = calibration(current.time)
        for mode in ("persistence", "era5"):
            fronts = {band: fs.forecast(hull, steps_for(mode, current.time, max(HORIZONS_H), weather, fire_weather, factor * multiplier))
                      for band, multiplier in BANDS.items()}
            for horizon in HORIZONS_H:
                later = [point for moment, point in detections if current.time < moment <= current.time + timedelta(hours=horizon)]
                outside_now = [point for point in later if fs.distance_to_hull(point, hull) > MIN_ADVANCE_M]
                if len(outside_now) < 5 or any(len(front) < horizon for front in fronts.values()):
                    continue
                entry = skill.setdefault(mode, {}).setdefault(str(horizon), {})
                for band, front_list in fronts.items():
                    front = front_list[horizon - 1]
                    entry.setdefault(f"hit_{band}", []).append(sum(fs.inside_convex(p, front) for p in outside_now) / len(outside_now))
                observed_area = fs.polygon_area(fs.convex_hull([*hull, *later])) - fs.polygon_area(hull)
                predicted_area = fs.polygon_area(fronts["central"][horizon - 1]) - fs.polygon_area(hull)
                if observed_area > 0:
                    entry.setdefault("area_ratio_central", []).append(predicted_area / observed_area)
            # Arrival times for targets not yet reached and at least REACH_DISTANCE_M outside the front.
            for key, cell in cells.items():
                observed = arrivals.get(key)
                if observed is not None and observed <= current.time:
                    continue
                if fs.distance_to_hull(cell["centre"], hull) <= REACH_DISTANCE_M or fs.distance_to_hull(cell["centre"], hull) > 25_000:
                    continue
                predicted = {}
                for band, front_list in fronts.items():
                    hour = first_reaching_hour(cell["centre"], front_list)
                    if hour is not None:
                        predicted[band] = hour
                observed_hours = (observed - current.time).total_seconds() / 3600.0 if observed else None
                window_start_h = None
                if observed_hours is not None and observed_hours <= 24:
                    # The fire reached the target after the last pass that did not see it there.
                    earlier = [item.time for item in passes if current.time <= item.time < observed]
                    window_start_h = (max(earlier) - current.time).total_seconds() / 3600.0 if earlier else 0.0
                else:
                    observed_hours = None
                if not predicted and observed_hours is None:
                    continue
                arrival_errors.setdefault(mode, {}).setdefault(cell["kind"], []).append({
                    "forecast_utc": current.time.isoformat(), "names": sorted(cell["names"]),
                    "observed_h": round(observed_hours, 1) if observed_hours is not None else None,
                    "observed_window_start_h": round(window_start_h, 1) if window_start_h is not None else None,
                    **{f"predicted_{band}_h": predicted.get(band) for band in BANDS},
                })

    def summary(values: list[float]) -> dict[str, float]:
        return {"n": len(values), "median": round(statistics.median(values), 2), "p25": round(_pct(values, 0.25), 2), "p75": round(_pct(values, 0.75), 2)}

    skill_summary = {mode: {h: {name: summary(values) for name, values in metrics.items()} for h, metrics in horizons.items()} for mode, horizons in skill.items()}
    arrival_summary = {}
    for mode, kinds in arrival_errors.items():
        for kind, records in kinds.items():
            reached = [r for r in records if r["observed_h"] is not None]
            predicted_central = [r for r in records if r["predicted_central_h"] is not None]
            caught = [r for r in reached if r["predicted_central_h"] is not None]
            within_band = [r for r in reached if r["predicted_high_h"] is not None and r["predicted_high_h"] <= r["observed_h"]
                           and (r["predicted_low_h"] is None or r["predicted_low_h"] >= r["observed_h"])]
            errors = [r["predicted_central_h"] - r["observed_h"] for r in caught]
            # Error against the observation window [last pass without detection, first pass with one].
            window_errors = [
                0.0 if r["observed_window_start_h"] <= r["predicted_central_h"] <= r["observed_h"]
                else (r["predicted_central_h"] - r["observed_h"] if r["predicted_central_h"] > r["observed_h"]
                      else r["predicted_central_h"] - r["observed_window_start_h"])
                for r in caught
            ]
            band_overlaps = [
                r for r in reached
                if r["predicted_high_h"] is not None and r["predicted_high_h"] <= r["observed_h"]
                and (r["predicted_low_h"] is None or r["predicted_low_h"] >= r["observed_window_start_h"])
            ]
            window_lengths = [r["observed_h"] - r["observed_window_start_h"] for r in reached]
            arrival_summary.setdefault(mode, {})[kind] = {
                "cases_reached_within_24h": len(reached),
                "reached_and_predicted_within_24h": len(caught),
                "reached_within_low_high_interval": len(within_band),
                "predicted_but_not_reached_within_24h": len(predicted_central) - len(caught),
                "central_error_h": summary(errors) if errors else None,
                "median_abs_error_h": round(statistics.median([abs(e) for e in errors]), 1) if errors else None,
                "observation_window_h": summary(window_lengths) if window_lengths else None,
                "central_within_window": sum(1 for e in window_errors if e == 0.0),
                "median_abs_error_outside_window_h": round(statistics.median([abs(e) for e in window_errors]), 1) if window_errors else None,
                "low_high_overlaps_window": len(band_overlaps),
            }
    named = sorted(
        ({"names": sorted(cell["names"]), "first_detection_within_750m_utc": arrivals[key].isoformat()}
         for key, cell in cells.items() if cell["kind"] == "place" and cell["names"] and key in arrivals),
        key=lambda item: item["first_detection_within_750m_utc"],
    )
    named_forecasts = [
        record for record in arrival_errors.get("persistence", {}).get("place", [])
        if record["names"] and record["observed_h"] is not None and 3 <= record["observed_h"] <= 24
    ]
    return {
        "method": {
            "fuel": FUEL, "weather_point": WEATHER_POINT,
            "weather_source": f"SMHI {args.smhi_station}" if args.weather_smhi else "ERA5-Land", "bands": BANDS, "horizons_h": HORIZONS_H,
            "reach_distance_m": REACH_DISTANCE_M, "cell_m": CELL_M, "fwi_start": fs.FWI_START, "min_interval_h": MIN_INTERVAL_H,
            "passes": len(passes), "forecasts": forecasts_made, "detections": len(detections),
        },
        "fwi_daily": {day: {k: round(v, 1) for k, v in values.items()} for day, values in fire_weather.daily.items() if day >= "2014-07-25"},
        "intervals": intervals,
        "skill": skill_summary,
        "arrivals": arrival_summary,
        "named_places_reached": named,
        "named_place_forecasts_persistence": named_forecasts,
    }


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--weather", nargs="+", type=Path, default=[], help="ERA5-Land CSV files from tools/fetch_era5_land.py, spin-up first")
    parser.add_argument("--targets", required=True, type=Path, help="GeoJSON from tools/fetch_osm_targets.py")
    parser.add_argument("--weather-smhi", type=Path, help="use SMHI station archives in this directory instead of ERA5-Land")
    parser.add_argument("--smhi-station", default="96560")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    result = analyse(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"method": result["method"], "skill": result["skill"], "arrivals": result["arrivals"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
