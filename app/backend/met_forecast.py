"""MET Norway's weather forecast at the scenario clock, as it was issued then (Kårböle 2018).

tools/fetch_met_forecasts.py keeps every MEPS run of the scenario's period: hourly 0-66 h at
the fire and a coarse grid over the map. At a moment of the scenario clock the screens get the
latest run that had been issued and published by then (its reference time plus AVAILABLE_AFTER),
so they never show a forecast before it existed, and from it:

- the hours from the clock to the end of the run (wind, gust, temperature, humidity, hourly
  precipitation, cloud and thunderstorm index at the fire);
- a summary for the next SUMMARY_HOURS hours;
- short notices for the rescue service when the run says something that matters: a wind
  shift, strong gusts, rain or none, low humidity, a risk of thunder (thresholds below);
- the fire weather index (FWI) of the coming days, computed by the demo's own FWI code from
  SMHI's observations up to the run and the forecast after it - computed, not MET Norway's;
- the forecast wind over the map WIND_AHEAD_H hours ahead, for the map's arrows;
- the weather chart: the run's isobars at the next synoptic hour (00, 03 ... 21 UTC) after the
  clock, the forecast one looks up at 01 to see 03 UTC (tools/isobars.py).

It is a forecast as issued, not live; the screens say so.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from app.backend import scenario
from tools import fire_spread as fs
from tools import fire_spread_analysis as analysis

DIRECTORY = scenario.MET_FORECAST_DIR
# MEPS runs were published about two and a half hours after their reference time (an
# assumption, rounded up): the screens take a run only from then.
AVAILABLE_AFTER = timedelta(hours=3)
SUMMARY_HOURS = (6, 12, 24, 48)
LABEL = "Historisk prognos från MET Norway (MEPS) – som den utfärdades, inte live"
ATTRIBUTION = "Väderprognos: MET Norway (MEPS, MetCoOp), NLOD/CC BY 4.0"
# A notice when: the wind turns at least this much within 24 h (and blows at least WIND_SHIFT_MIN_MS),
# the gust reaches GUST_MS, rain sums to RAIN_MM in 24 h (none: below DRY_MM), the humidity falls
# to LOW_HUMIDITY, or the thunderstorm index reaches THUNDER.
WIND_SHIFT_DEG = 60
WIND_SHIFT_MIN_MS = 2.0
GUST_MS = 10.0
RAIN_MM = 2.0
DRY_MM = 0.2
LOW_HUMIDITY = 30.0
THUNDER = 0.3
COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV"]
COMPASS_WORDS = {"N": "norr", "NO": "nordost", "O": "öster", "SO": "sydost", "S": "söder", "SV": "sydväst", "V": "väster", "NV": "nordväst"}


def parse(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def compass(degrees: float, points: int = 16) -> str:
    names = COMPASS if points == 16 else COMPASS[::2]
    return names[round(degrees / (360 / points)) % points]


@lru_cache(maxsize=1)
def runs() -> tuple[dict[str, Any], ...]:
    """Every fetched run, oldest first; none without the directory."""
    if DIRECTORY is None or not DIRECTORY.is_dir():
        return ()
    found = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(DIRECTORY.glob("*Z.json"))]
    return tuple(sorted(found, key=lambda run: run["issued_utc"]))


def run_at(clock: datetime, all_runs: tuple[dict[str, Any], ...] | None = None) -> dict[str, Any] | None:
    """The latest run published by `clock`."""
    latest = None
    for run in runs() if all_runs is None else all_runs:
        if parse(run["issued_utc"]) + AVAILABLE_AFTER <= clock:
            latest = run
    return latest


def hourly(run: dict[str, Any]) -> list[dict[str, Any]]:
    """The run's hours at the fire, with the hourly precipitation from the accumulated sums."""
    point = run["point"]
    hours, previous = [], 0.0
    for index, moment in enumerate(run["times_utc"]):
        accumulated = point["precipitation_acc_mm"][index]
        rain = None if accumulated is None else max(0.0, round(accumulated - previous, 1))
        previous = accumulated if accumulated is not None else previous
        temperature = point["temperature_k"][index]
        hours.append({
            "time_utc": moment,
            "wind_ms": point["wind_ms"][index],
            "wind_from_deg": point["wind_from_deg"][index],
            "gust_ms": point["gust_ms"][index],
            "temperature_c": None if temperature is None else round(temperature - 273.15, 1),
            "humidity_pct": point["humidity"][index],
            "precipitation_mm": rain if index else 0.0,
            "cloud_pct": point["cloud_pct"][index],
            "thunderstorm_index": point["thunderstorm_index"][index],
        })
    return hours


def mean_direction(hours: list[dict[str, Any]]) -> tuple[float, float]:
    """The hours' mean wind (vector mean): the direction it blows from and its speed."""
    east = sum(-item["wind_ms"] * math.sin(math.radians(item["wind_from_deg"])) for item in hours) / len(hours)
    north = sum(-item["wind_ms"] * math.cos(math.radians(item["wind_from_deg"])) for item in hours) / len(hours)
    return (math.degrees(math.atan2(-east, -north)) + 360) % 360, math.hypot(east, north)


def summary(ahead: list[dict[str, Any]], hours: int) -> dict[str, Any] | None:
    if len(ahead) < hours:  # the run does not reach that far
        return None
    window = ahead[:hours]
    direction, speed = mean_direction(window)
    return {
        "hours": hours,
        "wind_from": compass(direction),
        "wind_ms": round(speed, 1),
        "gust_max_ms": round(max(item["gust_ms"] for item in window), 1),
        "precipitation_mm": round(sum(item["precipitation_mm"] or 0.0 for item in window), 1),
        "humidity_min_pct": round(min(item["humidity_pct"] for item in window)),
        "temperature_max_c": round(max(item["temperature_c"] for item in window), 1),
        "thunderstorm_max": round(max(item["thunderstorm_index"] or 0.0 for item in window), 2),
    }


def hours_word(hours: int) -> str:
    return "1 timme" if hours == 1 else f"{hours} timmar"


def when(hours: int) -> str:
    """When something comes: "nu" in the hour at hand, else "om 3 timmar"."""
    return "nu" if hours == 0 else f"om {hours_word(hours)}"


def notices(ahead: list[dict[str, Any]]) -> list[dict[str, str]]:
    """What the next 24 hours of the run mean for the rescue service: { kind, text } with a short
    Swedish line; the kinds are wind_shift, gust, rain, dry, humidity and thunder."""
    day = ahead[:24]
    if len(day) < 6:
        return []
    found = []
    now_direction, now_speed = mean_direction(day[:3])
    for start in range(3, len(day) - 2):
        direction, speed = mean_direction(day[start:start + 3])
        if speed >= WIND_SHIFT_MIN_MS and now_speed >= WIND_SHIFT_MIN_MS and fs.angle_difference(direction, now_direction) >= WIND_SHIFT_DEG:
            found.append({"kind": "wind_shift", "text": f"Vindvridning från {COMPASS_WORDS[compass(now_direction, 8)]} till "
                                                        f"{COMPASS_WORDS[compass(direction, 8)]} om cirka {hours_word(start)}"})
            break
    gust = max(day, key=lambda item: item["gust_ms"])
    if gust["gust_ms"] >= GUST_MS:
        found.append({"kind": "gust", "text": f"Byvind upp till {round(gust['gust_ms'])} meter per sekund {when(day.index(gust))}"})
    rain = sum(item["precipitation_mm"] or 0.0 for item in day)
    if rain >= RAIN_MM:
        found.append({"kind": "rain", "text": f"Regn, {round(rain)} millimeter de närmaste 24 timmarna"})
    elif rain < DRY_MM:
        found.append({"kind": "dry", "text": "Inget regn de närmaste 24 timmarna"})
    driest = min(day, key=lambda item: item["humidity_pct"])
    if driest["humidity_pct"] <= LOW_HUMIDITY:
        found.append({"kind": "humidity", "text": f"Låg luftfuktighet, ned till {round(driest['humidity_pct'])} procent"})
    thunder = max(day, key=lambda item: item["thunderstorm_index"] or 0.0)
    if (thunder["thunderstorm_index"] or 0.0) >= THUNDER:
        found.append({"kind": "thunder", "text": f"Risk för åska {when(day.index(thunder))}, nya bränder kan tändas"})
    return found


@lru_cache(maxsize=1)
def observed_weather() -> tuple[fs.Weather, ...]:
    files = scenario.FORECAST_WEATHER_FILES
    return tuple(analysis.load_weather_smhi_csv(files)) if files else ()


def fire_weather_index(run: dict[str, Any], hours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The FWI at noon of each day the run reaches past its issue, from SMHI's observations up
    to the run and the run's forecast after it (computed by the demo's FWI code)."""
    issued = parse(run["issued_utc"])
    observed = [item for item in observed_weather() if item.time < issued]
    if not observed:
        return []
    forecast = [fs.Weather(parse(item["time_utc"]), item["temperature_c"], item["humidity_pct"], item["wind_ms"] * 3.6,
                           item["wind_from_deg"], item["precipitation_mm"] or 0.0)
                for item in hours if parse(item["time_utc"]) >= issued and item["temperature_c"] is not None]
    daily = fs.FireWeather(observed + forecast).compute().daily
    days = sorted({parse(item["time_utc"]).date().isoformat() for item in hours
                   if parse(item["time_utc"]) > issued and parse(item["time_utc"]).hour == fs.FireWeather.noon_hour_utc})
    return [{"date": day, "fwi": round(daily[day]["fwi"], 1)} for day in days if day in daily]


WIND_AHEAD_H = 6
# The map's forecast arrows at least this far apart, so they do not crowd the ERA5-Land ones.
WIND_SPACING_KM = 9.0


def wind_hour(run: dict[str, Any], clock: datetime) -> int:
    """The run's hour nearest WIND_AHEAD_H hours after the clock."""
    times = [parse(moment) for moment in run["times_utc"]]
    target = clock + timedelta(hours=WIND_AHEAD_H)
    return min(range(len(times)), key=lambda i: abs((times[i] - target).total_seconds()))


def wind_grid(run: dict[str, Any], clock: datetime) -> list[dict[str, Any]]:
    """The forecast wind over the map WIND_AHEAD_H hours after the clock (the hour nearest it)."""
    index = wind_hour(run, clock)
    kept: list[dict[str, Any]] = []
    for cell in run["grid"]:
        if all(distance_km(cell, other) >= WIND_SPACING_KM for other in kept):
            kept.append(cell)
    return [{"latitude": cell["latitude"], "longitude": cell["longitude"], "wind_ms": cell["wind_ms"][index],
             "wind_from_deg": cell["wind_from_deg"][index]} for cell in kept]


def distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    north = (a["latitude"] - b["latitude"]) * 111.2
    east = (a["longitude"] - b["longitude"]) * 111.2 * math.cos(math.radians(a["latitude"]))
    return math.hypot(north, east)


def isobars_at(run: dict[str, Any], clock: datetime) -> dict[str, Any] | None:
    """The run's weather chart at the next synoptic hour after the clock (its last when the clock is
    past them all, as after a run missing from the archive), or None without charts."""
    charts = run.get("isobars", [])
    return next((chart for chart in charts if parse(chart["valid_utc"]) > clock), charts[-1] if charts else None)


def at(clock: datetime) -> dict[str, Any] | None:
    """The forecast the screens show at `clock`, or None before the first run was published."""
    run = run_at(clock)
    if run is None:
        return None
    hours = hourly(run)
    ahead = [item for item in hours if parse(item["time_utc"]) >= clock.replace(minute=0, second=0, microsecond=0)]
    return {
        "label": LABEL,
        "issued_utc": run["issued_utc"],
        "available_utc": (parse(run["issued_utc"]) + AVAILABLE_AFTER).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hours": hours,
        "summaries": [item for item in (summary(ahead, hours_ahead) for hours_ahead in SUMMARY_HOURS) if item],
        "notices": notices(ahead),
        "fwi": fire_weather_index(run, hours),
        "wind_grid": wind_grid(run, clock),
        "wind_grid_hours_ahead": WIND_AHEAD_H,
        "wind_grid_valid_utc": run["times_utc"][wind_hour(run, clock)],
        "isobars": isobars_at(run, clock),
    }


def issues() -> list[dict[str, Any]]:
    """Every run's publication for the log: its notices for the next 24 hours from then, and
    `news`, those of a kind the run before did not have (so "no rain" is not said every run)."""
    found, previous = [], set()
    for run in runs():
        available = parse(run["issued_utc"]) + AVAILABLE_AFTER
        ahead = [item for item in hourly(run) if parse(item["time_utc"]) >= available]
        said = notices(ahead)
        found.append({"available_utc": available.strftime("%Y-%m-%dT%H:%M:%SZ"), "issued_utc": run["issued_utc"],
                      "notices": said, "news": [item["text"] for item in said if item["kind"] not in previous]})
        previous = {item["kind"] for item in said}
    return found
