"""SMHI's observed lightning at the scenario clock (tools/fetch_smhi_lightning.py).

The screens show the flashes to the ground of the last WINDOW before the clock, over the weather
chart's area, each with its age, and every flash within NEAR_KM of the incident since the data's
first day up to the clock, which stays on the map (where lightning struck near the fire, as on
14 July 2018 at Kårböle). The satellite monitor's log says, at most once an hour, how
many struck within NEAR_KM of the incident in the hour before. Cloud flashes are left out: the
screens speak of "blixtnedslag". Observations, not forecasts; the screens say so.
"""

from __future__ import annotations

import bisect
import json
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from app.backend import scenario

DIRECTORY = scenario.LIGHTNING_DIR
WINDOW = timedelta(minutes=60)
NEAR_KM = 30.0
NEAR_HISTORY_MAX = 1000  # the newest, should a scenario have more near the incident
LABEL = "Observerade blixtnedslag (SMHI) – senaste timmen före scenariotiden"
ATTRIBUTION = "Blixtdata: SMHI öppna data (CC BY 4.0)"


def distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    north = (lat_a - lat_b) * 111.2
    east = (lon_a - lon_b) * 111.2 * math.cos(math.radians((lat_a + lat_b) / 2))
    return math.hypot(north, east)


@lru_cache(maxsize=1)
def flashes() -> tuple[tuple[int, float, float, int], ...]:
    """Every flash to the ground of the fetched days, as (epoch seconds, latitude, longitude, kA), in time order."""
    if DIRECTORY is None or not DIRECTORY.is_dir():
        return ()
    found = []
    for path in sorted(DIRECTORY.glob("????-??-??.json")):
        found += [(t, lat, lon, ka) for t, lat, lon, ka, cloud in json.loads(path.read_text(encoding="utf-8"))["strikes"] if not cloud]
    return tuple(sorted(found))


@lru_cache(maxsize=1)
def near_flashes(all_flashes: tuple[tuple[int, float, float, int], ...] | None = None) -> tuple[tuple[int, float, float, int], ...]:
    """The flashes to the ground within NEAR_KM of the incident, in time order (worked out once)."""
    lat0, lon0 = scenario.FIRE_CENTRE
    return tuple(item for item in (flashes() if all_flashes is None else all_flashes) if distance_km(item[1], item[2], lat0, lon0) <= NEAR_KM)


def at(clock: datetime, all_flashes: tuple[tuple[int, float, float, int], ...] | None = None) -> dict[str, Any]:
    """The flashes of the last WINDOW before `clock`, each with its age in minutes, and how many were near the incident."""
    every = flashes() if all_flashes is None else all_flashes
    end = int(clock.timestamp())
    start = end - int(WINDOW.total_seconds())
    times = [item[0] for item in every]
    recent = every[bisect.bisect_right(times, start):bisect.bisect_right(times, end)]
    lat0, lon0 = scenario.FIRE_CENTRE
    near = [item for item in (near_flashes() if all_flashes is None else near_flashes.__wrapped__(all_flashes)) if item[0] <= end]
    return {
        "label": LABEL,
        "near_history": [{"latitude": lat, "longitude": lon, "utc": datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "ka": ka} for t, lat, lon, ka in near[-NEAR_HISTORY_MAX:]],
        "window_minutes": int(WINDOW.total_seconds() // 60),
        "strikes": [{"latitude": lat, "longitude": lon, "age_min": round((end - t) / 60), "ka": ka} for t, lat, lon, ka in recent],
        "near": sum(1 for _, lat, lon, _ in recent if distance_km(lat, lon, lat0, lon0) <= NEAR_KM),
        "near_km": NEAR_KM,
    }


def events(all_flashes: tuple[tuple[int, float, float, int], ...] | None = None) -> list[dict[str, Any]]:
    """For the log: at the end of each hour with flashes within NEAR_KM of the incident, how many there were."""
    lat0, lon0 = scenario.FIRE_CENTRE
    hours: dict[int, int] = {}
    for t, lat, lon, _ in flashes() if all_flashes is None else all_flashes:
        if distance_km(lat, lon, lat0, lon0) <= NEAR_KM:
            end = (t // 3600 + 1) * 3600
            hours[end] = hours.get(end, 0) + 1
    return [{"at_utc": datetime.fromtimestamp(end, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "count": count}
            for end, count in sorted(hours.items())]
