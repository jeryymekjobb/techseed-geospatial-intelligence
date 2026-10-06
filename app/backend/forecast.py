"""Fire-spread forecasts for the fire map, one per satellite pass.

At each FIRMS pass the front is the hull of all detections so far; the forecast
uses only data up to that pass: SMHI Sala A weather held at its value at the pass
(persistence), Fire Weather Index codes run in from 1 May, FBP C-2 spread
calibrated against the observed spread of the previous 24 hours, and the band
half to double the calibrated rate. See
`reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md` for
how well this did in the hindcast.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from app.backend import scenario
from tools import fire_spread as fs
from tools import fire_spread_analysis as analysis
from tools.firms_extract import select_detections

HORIZONS_H = (3, 6, 12, 24)
BANDS = analysis.BANDS
SMHI_FILES = scenario.FORECAST_WEATHER_FILES
TARGETS_FILE = scenario.TARGETS_FILE
LABEL = "Modellprognos med stor osäkerhet – inte beslutsunderlag"
COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV"]


def _latlon_ring(projector: fs.Projector, points: list[fs.Point]) -> list[list[float]]:
    return [[round(lat, 5), round(lon, 5)] for lat, lon in (projector.latlon(x, y) for x, y in points)]


def _span(hours: dict[str, int | None]) -> str:
    """Earliest (high rate) to latest (low rate) arrival, as text."""
    earliest = hours.get("high")
    latest = hours.get("low")
    if earliest is None:
        return ""
    if latest == earliest:
        return f"{earliest} h"
    return f"{earliest}–{latest} h" if latest is not None else f"{earliest}–>24 h"


@lru_cache(maxsize=1)
def forecasts() -> dict[str, Any]:
    kept, _, _ = select_detections(scenario.FIRMS_FILES, start=scenario.PERIOD_START, end=scenario.PERIOD_END, bbox=scenario.FIRE_BBOX)
    projector = fs.Projector(*scenario.FIRE_CENTRE)
    detections = [(analysis.parse_time(item["acq_datetime_utc"]), projector.xy(item["latitude"], item["longitude"])) for item in kept]
    hourly = analysis.load_weather_smhi_csv(SMHI_FILES)
    weather = {item.time: item for item in hourly}
    fire_weather = fs.FireWeather(hourly).compute()
    passes = fs.group_passes(detections)
    intervals, hulls = analysis.observed_intervals(passes, weather, fire_weather)
    cells = analysis.load_targets(TARGETS_FILE, projector)
    places = {key: cell for key, cell in cells.items() if cell["kind"] == "place" and cell["names"]}
    arrivals = analysis.observed_arrivals(places, detections)

    states = []
    for index, current in enumerate(passes):
        hull = hulls[index]
        hour = current.time.replace(minute=0, second=0, microsecond=0)
        if len(hull) < 3 or hour not in weather:
            continue
        factor = analysis.calibration_factor(intervals, current.time)
        fronts = {
            band: fs.forecast(hull, analysis.steps_for("persistence", current.time, max(HORIZONS_H), weather, fire_weather, factor * multiplier))
            for band, multiplier in BANDS.items()
        }
        observed = next(
            (item for item in reversed(intervals)
             if analysis.parse_time(item["end_utc"]) <= current.time and not item["short_interval"] and item["advance_m"] > 0),
            None,
        )
        now = weather[hour]
        step = fs.model_step(fire_weather, now, analysis.FUEL, factor, ffmc_override=fire_weather.ffmc_hour.get(hour))
        daily_key = (current.time.date() if current.time.hour >= fire_weather.noon_hour_utc else current.time.date() - timedelta(days=1)).isoformat()
        targets = []
        for key, cell in places.items():
            reached = arrivals.get(key)
            if reached is not None and reached <= current.time:
                continue
            if fs.distance_to_hull(cell["centre"], hull) <= analysis.REACH_DISTANCE_M:
                continue
            hours = {band: analysis.first_reaching_hour(cell["centre"], fronts[band]) for band in BANDS}
            if hours["high"] is None:
                continue
            lat, lon = projector.latlon(*cell["centre"])
            targets.append({"names": sorted(cell["names"]), "latitude": round(lat, 5), "longitude": round(lon, 5),
                            "earliest_h": hours["high"], "span": _span(hours)})
        targets.sort(key=lambda item: (item["earliest_h"], item["names"]))
        centre_lat, centre_lon = projector.latlon(*fs.centroid(hull))
        states.append({
            "pass_utc": current.time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "detections_so_far": sum(1 for moment, _ in detections if moment <= current.time),
            "front": _latlon_ring(projector, hull),
            "front_centre": [round(centre_lat, 5), round(centre_lon, 5)],
            "forecast": {
                str(horizon): {band: _latlon_ring(projector, fronts[band][horizon - 1]) for band in BANDS}
                for horizon in HORIZONS_H
            },
            "observed_spread": None if observed is None else {
                "from_utc": observed["start_utc"], "to_utc": observed["end_utc"],
                "km_per_h": round(observed["observed_ros_m_per_h"] / 1000.0, 2),
                "towards_deg": observed["observed_direction_deg"],
                "towards": COMPASS[round(observed["observed_direction_deg"] / 22.5) % 16] if observed["observed_direction_deg"] is not None else None,
            },
            "model": {
                "calibration_factor": round(factor, 2),
                "head_km_per_h": {band: round(step.ros_m_per_h * multiplier / 1000.0, 2) for band, multiplier in BANDS.items()},
                "towards_deg": round(step.towards_deg),
                "towards": COMPASS[round(step.towards_deg / 22.5) % 16],
                "wind_kmh": round(now.wind_kmh, 1),
                "fire_weather": {name: round(value, 1) for name, value in fire_weather.daily.get(daily_key, {}).items()},
            },
            "places_within_24h": targets[:12],
            "places_within_24h_count": len(targets),
        })
    return {
        "label": LABEL,
        "method": scenario.FORECAST_METHOD,
        "horizons_h": list(HORIZONS_H),
        "report": scenario.FORECAST_REPORT,
        "states": states,
    }
