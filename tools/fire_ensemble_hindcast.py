#!/usr/bin/env python3
"""Hindcast of the ensemble Kalman filter against today's calibrated forecast, Västmanland 2014.

Both forecasts are made at every satellite pass with data up to that pass only and
compared with the detections that came later, in one run with the same weather
(SMHI Sala A, the files app/backend/forecast.py uses), the same passes and the same
measures as tools/fire_spread_analysis.py:

- hits: the share of new detections (outside the front at the forecast) that lie
  inside the forecast area, per horizon;
- area: the forecast area's growth over the observed growth;
- arrivals: for targets 750 m–25 km outside the front, whether the forecast arrival
  interval overlaps the observation window (last pass without, first pass with).

Today's forecast has the bands low, central and high (half, one and two times the
calibrated rate). The filter's matching areas are where at least 90 %, 50 % and 10 %
of its members have reached - a point counts as inside when that share of the member
fronts contains it, and the area is measured on the quantile front along 72 rays from
the front's centre. The filter's settings are fixed in tools/fire_ensemble.Settings
and are not tuned here; --seed only fixes the random draws.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Sequence

from app.backend import forecast as app_forecast
from app.backend import scenario
from tools import fire_ensemble as fe
from tools import fire_spread as fs
from tools import fire_spread_analysis as analysis
from tools.firms_extract import select_detections

HORIZONS_H = analysis.HORIZONS_H
LEVELS = {"low": 0.9, "central": 0.5, "high": 0.1}  # filter: share of members, matched to today's bands
RAYS = 72


def ray_distance(origin: fs.Point, bearing_deg: float, polygon: Sequence[fs.Point]) -> float:
    """Distance from origin to a convex polygon's edge along a bearing (0 if the polygon is degenerate)."""
    if len(polygon) < 3:
        return 0.0
    theta = math.radians(bearing_deg)
    dx, dy = math.sin(theta), math.cos(theta)
    best = 0.0
    for a, b in zip(polygon, [*polygon[1:], polygon[0]]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        denominator = dx * ey - dy * ex
        if abs(denominator) < 1e-12:
            continue
        t = ((a[0] - origin[0]) * ey - (a[1] - origin[1]) * ex) / denominator
        s = ((a[0] - origin[0]) * dy - (a[1] - origin[1]) * dx) / denominator
        if t >= 0 and -1e-9 <= s <= 1 + 1e-9:
            best = max(best, t)
    return best


def quantile_front(centre: fs.Point, fronts: Sequence[Sequence[fs.Point]], share: float) -> list[fs.Point]:
    """The front reached by at least `share` of the members, along RAYS rays from the centre."""
    points = []
    for index in range(RAYS):
        bearing = 360.0 * index / RAYS
        distances = sorted((ray_distance(centre, bearing, front) for front in fronts), reverse=True)
        reach = distances[max(0, math.ceil(share * len(distances)) - 1)]
        theta = math.radians(bearing)
        points.append((centre[0] + reach * math.sin(theta), centre[1] + reach * math.cos(theta)))
    return points


def reach_hours(point: fs.Point, fronts: Sequence[Sequence[fs.Point]]) -> int | None:
    """First hour (1-based) whose front contains the point; the fronts only grow, so bisect."""
    if not fronts or not fs.inside_convex(point, fronts[-1]):
        return None
    low, high = 0, len(fronts) - 1
    while low < high:
        middle = (low + high) // 2
        if fs.inside_convex(point, fronts[middle]):
            high = middle
        else:
            low = middle + 1
    return low + 1


def summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    return {"n": len(values), "median": round(statistics.median(values), 2),
            "p25": round(ordered[int(0.25 * (len(ordered) - 1))], 2), "p75": round(ordered[int(0.75 * (len(ordered) - 1))], 2)}


def arrival_record(predicted: dict[str, int | None], observed_h: float | None, window_start_h: float | None) -> dict[str, Any]:
    return {"predicted": predicted, "observed_h": observed_h, "window_start_h": window_start_h}


def arrival_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    reached = [r for r in records if r["observed_h"] is not None]
    overlaps = [r for r in reached if r["predicted"]["high"] is not None and r["predicted"]["high"] <= r["observed_h"]
                and (r["predicted"]["low"] is None or r["predicted"]["low"] >= r["window_start_h"])]
    central_in_window = [r for r in reached if r["predicted"]["central"] is not None
                         and r["window_start_h"] <= r["predicted"]["central"] <= r["observed_h"]]
    predicted_not_reached = [r for r in records if r["observed_h"] is None and r["predicted"]["central"] is not None]
    return {
        "reached_within_24h": len(reached),
        "interval_overlaps_window": len(overlaps),
        "interval_overlaps_window_pct": round(100 * len(overlaps) / len(reached)) if reached else None,
        "central_within_window": len(central_in_window),
        "predicted_central_but_not_reached": len(predicted_not_reached),
    }


def run(seed: int) -> dict[str, Any]:
    started = time.time()
    kept, _, _ = select_detections(scenario.FIRMS_FILES, start=scenario.PERIOD_START, end=scenario.PERIOD_END, bbox=scenario.FIRE_BBOX)
    projector = fs.Projector(*scenario.FIRE_CENTRE)
    detections = sorted((analysis.parse_time(item["acq_datetime_utc"]), projector.xy(item["latitude"], item["longitude"])) for item in kept)
    hourly = analysis.load_weather_smhi_csv(app_forecast.SMHI_FILES)
    weather = {item.time: item for item in hourly}
    fire_weather = fs.FireWeather(hourly).compute()
    passes = fs.group_passes(detections)
    intervals, hulls = analysis.observed_intervals(passes, weather, fire_weather)
    by_end = {item["end_utc"]: item for item in intervals}
    cells = analysis.load_targets(app_forecast.TARGETS_FILE, projector)
    arrivals = analysis.observed_arrivals(cells, detections)
    times = [moment for moment, _ in detections]

    ensemble = fe.EnsembleFilter(seed=seed)
    hits: dict[str, dict[str, dict[str, list[float]]]] = {"today": {}, "filter": {}}
    areas: dict[str, dict[str, list[float]]] = {"today": {}, "filter": {}}
    arrival_records: dict[str, list[dict[str, Any]]] = {"today": [], "filter": []}
    updates = []
    previous_index = None
    for index, current in enumerate(passes):
        hull = hulls[index]
        hour = current.time.replace(minute=0, second=0, microsecond=0)
        # Update the filter with the spread observed since the last pass it used.
        interval = by_end.get(current.time.isoformat())
        if previous_index is not None and interval and not interval["short_interval"]:
            start = passes[previous_index].time
            hours = max(1, round((current.time - start).total_seconds() / 3600.0))
            steps = analysis.steps_for("era5", start, hours, weather, fire_weather, 1.0)  # the weather that came, hour by hour
            if len(steps) == hours:
                ensemble.predict()
                result = ensemble.update(hulls[previous_index], steps, interval["advance_m"], interval["observed_direction_deg"])
                updates.append({"pass_utc": current.time.isoformat(), "advance_m": interval["advance_m"],
                                "direction_deg": interval["observed_direction_deg"], **{k: round(v, 3) for k, v in result.items()},
                                "k_after": round(math.exp(result["log_k_after"]), 2)})
        if len(hull) >= 3:
            previous_index = index
        if len(hull) < 3 or hour not in weather:
            continue
        # Today's forecast: the calibrated rate, half and twice.
        factor = analysis.calibration_factor(intervals, current.time)
        today = {band: fs.forecast(hull, analysis.steps_for("persistence", current.time, max(HORIZONS_H), weather, fire_weather, factor * m))
                 for band, m in analysis.BANDS.items()}
        # The filter's members, with the weather held from the pass as today's forecast does.
        base = analysis.steps_for("persistence", current.time, max(HORIZONS_H), weather, fire_weather, 1.0)
        members = ensemble.forecast(hull, base)
        centre = fs.centroid(hull)
        hull_area = fs.polygon_area(hull)
        for horizon in HORIZONS_H:
            later = [point for moment, point in detections[bisect.bisect_right(times, current.time):]
                     if moment <= current.time + timedelta(hours=horizon)]
            outside = [point for point in later if fs.distance_to_hull(point, hull) > analysis.MIN_ADVANCE_M]
            if len(outside) < 5 or any(len(front) < horizon for front in today.values()):
                continue
            observed_area = fs.polygon_area(fs.convex_hull([*hull, *later])) - hull_area
            fronts_now = [member[horizon - 1] for member in members]
            shares = [fe.reach_fraction(point, fronts_now) for point in outside]
            for band, front_list in today.items():
                front = front_list[horizon - 1]
                hits["today"].setdefault(str(horizon), {}).setdefault(band, []).append(
                    sum(fs.inside_convex(p, front) for p in outside) / len(outside))
                level = LEVELS[band]
                hits["filter"].setdefault(str(horizon), {}).setdefault(band, []).append(sum(share >= level for share in shares) / len(outside))
            if observed_area > 0:
                areas["today"].setdefault(str(horizon), []).append((fs.polygon_area(today["central"][horizon - 1]) - hull_area) / observed_area)
                median_front = quantile_front(centre, fronts_now, LEVELS["central"])
                areas["filter"].setdefault(str(horizon), []).append((fs.polygon_area(median_front) - hull_area) / observed_area)
        # Arrivals at targets not yet reached, 750 m–25 km outside the front.
        for key, cell in cells.items():
            observed = arrivals.get(key)
            if observed is not None and observed <= current.time:
                continue
            distance = fs.distance_to_hull(cell["centre"], hull)
            if distance <= analysis.REACH_DISTANCE_M or distance > 25_000:
                continue
            observed_h = (observed - current.time).total_seconds() / 3600.0 if observed else None
            window_start_h = None
            if observed_h is not None and observed_h <= 24:
                earlier = [item.time for item in passes if current.time <= item.time < observed]
                window_start_h = (max(earlier) - current.time).total_seconds() / 3600.0 if earlier else 0.0
            else:
                observed_h = None
            today_predicted = {band: analysis.first_reaching_hour(cell["centre"], today[band]) for band in analysis.BANDS}
            member_hours = sorted(h for h in (reach_hours(cell["centre"], member) for member in members) if h is not None)
            filter_predicted = {}
            for band, level in LEVELS.items():
                needed = math.ceil(level * len(members))
                filter_predicted[band] = member_hours[needed - 1] if len(member_hours) >= needed else None
            for name, predicted in [("today", today_predicted), ("filter", filter_predicted)]:
                if any(value is not None for value in predicted.values()) or observed_h is not None:
                    arrival_records[name].append(arrival_record(predicted, observed_h, window_start_h))

    return {
        "method": {"weather": "SMHI Sala A (app/backend/forecast.py)", "seed": seed, "settings": vars(fe.Settings()) if hasattr(fe.Settings(), "__dict__") else str(fe.Settings()),
                   "levels": LEVELS, "passes": len(passes), "updates": len(updates), "seconds": round(time.time() - started)},
        "hits": {name: {h: {band: summary(values) for band, values in bands.items()} for h, bands in horizons.items()} for name, horizons in hits.items()},
        "area_ratio_central": {name: {h: summary(values) for h, values in horizons.items()} for name, horizons in areas.items()},
        "arrivals": {name: arrival_summary(records) for name, records in arrival_records.items()},
        "updates": updates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--seed", type=int, default=2014)
    parser.add_argument("--out", type=Path, default=scenario.REPO_ROOT / "data" / "fire-ensemble-hindcast.json")
    args = parser.parse_args(argv)
    result = run(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("method", "hits", "area_ratio_central", "arrivals")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
