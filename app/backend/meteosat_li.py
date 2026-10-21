"""MTG's Lightning Imager flashes over the incident (tools/fetch_meteosat_li.py).

Meteosat-12 sees lightning from space, cloud flashes as well as flashes to the ground, beside
SMHI's observed flashes to the ground (lightning.py). The maps draw the flashes of the hour before
the clock (`at`, /api/meteosat-li), the panel counts those in the map area, and the log says when an
hour's count in the map area rises past RISE and when it falls below FALL again, so a line comes
when a thunderstorm begins, not every hour. The Nordic area lies at the edge of the instrument's
view. Observations, archived, not live.
"""

from __future__ import annotations

import bisect
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from app.backend import scenario

FILE = scenario.METEOSAT_LI_FILE
LABEL = "Blixtar från rymden (Meteosat)"
# In the form EUMETSAT's data policy (article 6.3) asks for, with the year the demo shows it.
ATTRIBUTION = "Contains modified EUMETSAT Meteosat product 2026 (MTG LI Lightning Flashes, CC BY 4.0)"
WINDOW = timedelta(hours=1)
RISE, FALL = 10, 3  # flashes an hour in the map area


@lru_cache(maxsize=1)
def flashes() -> tuple[tuple[int, float, float], ...]:
    """Every flash as (epoch seconds, latitude, longitude), in time order."""
    if FILE is None or not FILE.is_file():
        return ()
    return tuple(tuple(item) for item in json.loads(FILE.read_text(encoding="utf-8"))["flashes"])


def in_area(latitude: float, longitude: float) -> bool:
    west, south, east, north = scenario.MAP_BBOX
    return south <= latitude <= north and west <= longitude <= east


def hours(items: tuple[tuple[int, float, float], ...] | None = None) -> list[dict[str, Any]]:
    """For each whole hour of the playback, the flashes in the map area during the hour before it."""
    every = flashes() if items is None else items
    counts: dict[int, int] = {}
    for seconds, lat, lon in every:
        if in_area(lat, lon):
            end = (seconds // 3600 + 1) * 3600
            counts[end] = counts.get(end, 0) + 1
    start = int(scenario.PLAYBACK_START.timestamp()) // 3600 * 3600 + 3600
    stop = int(scenario.PLAYBACK_END.timestamp())
    return [{"time_utc": datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "count": counts.get(end, 0)}
            for end in range(start, stop + 1, 3600)]


def events(series: list[dict[str, Any]], rise: int = RISE, fall: int = FALL) -> list[dict[str, Any]]:
    """The hours the count rises to RISE or more after being below it, and falls below FALL again."""
    found, active = [], False
    for item in series:
        if not active and item["count"] >= rise:
            found.append({**item, "kind": "up"})
            active = True
        elif active and item["count"] < fall:
            found.append({**item, "kind": "down"})
            active = False
    return found


def at(clock: datetime, items: tuple[tuple[int, float, float], ...] | None = None) -> dict[str, Any]:
    """The flashes of the hour before `clock`, each with its age in minutes, and how many were in the map area."""
    every = flashes() if items is None else items
    end = int(clock.timestamp())
    times = [item[0] for item in every]
    recent = every[bisect.bisect_right(times, end - int(WINDOW.total_seconds())):bisect.bisect_right(times, end)]
    return {"flashes": [{"latitude": lat, "longitude": lon, "age_min": (end - seconds) // 60} for seconds, lat, lon in recent],
            "in_area": sum(in_area(lat, lon) for _, lat, lon in recent)}


def layer() -> dict[str, Any] | None:
    """The label, credit, hourly counts and the log's events, or None without data."""
    if not flashes():
        return None
    series = hours()
    return {"label": LABEL, "attribution": ATTRIBUTION, "hours": series, "events": events(series), "rise": RISE}
