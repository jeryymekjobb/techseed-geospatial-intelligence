"""The satellites' passes over the incident, computed as the screens compute them.

The scenario clock slows down round each pass, so the backend needs the passes the
satellite monitor shows (app/frontend/orbits.js). This is the same computation: the
latest element set at or before the time, SGP4 (the `sgp4` package, as satellite.js),
the point below the satellite on the WGS 84 ellipsoid with satellite.js's sidereal time,
and a pass while that point lies within half the swath of the incident - sampled at a
step that cannot jump a swath and each edge found to a second. Satellites whose radar
looks to the side (Sentinel-1) have their catalogue acquisitions instead.

Without the `sgp4` package (app/requirements-orbits.txt) there are no computed passes.
"""

from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

try:
    from sgp4.api import Satrec, jday
except ImportError:  # the clock then slows only round the known acquisitions
    Satrec = None

EARTH_RADIUS_KM = 6371.0  # the great-circle distance on the ground, as orbits.js
WGS84_A, WGS84_B = 6378.137, 6356.7523142
ACQUISITION_SECONDS = 25  # a catalogue acquisition as a pass, as orbits.js


def available() -> bool:
    return Satrec is not None


def gmst(moment: datetime) -> float:
    """Greenwich mean sidereal time in radians, as satellite.js's gstime."""
    jd, fraction = jday(moment.year, moment.month, moment.day, moment.hour, moment.minute,
                        moment.second + moment.microsecond / 1e6)
    tut1 = (jd + fraction - 2451545.0) / 36525.0
    seconds = (-6.2e-6 * tut1 ** 3 + 0.093104 * tut1 ** 2 + (876600.0 * 3600 + 8640184.812866) * tut1 + 67310.54841)
    return (math.radians(seconds) / 240.0) % (2 * math.pi)


def geodetic(position: Sequence[float], sidereal: float) -> tuple[float, float]:
    """Latitude and longitude in degrees of an ECI position, as satellite.js's eciToGeodetic."""
    x, y, z = position
    flattening = (WGS84_A - WGS84_B) / WGS84_A
    e2 = 2 * flattening - flattening * flattening
    r = math.hypot(x, y)
    longitude = ((math.atan2(y, x) - sidereal + math.pi) % (2 * math.pi)) - math.pi
    latitude = math.atan2(z, r)
    for _ in range(20):
        c = 1 / math.sqrt(1 - e2 * math.sin(latitude) ** 2)
        latitude = math.atan2(z + WGS84_A * c * e2 * math.sin(latitude), r)
    return math.degrees(latitude), math.degrees(longitude)


def ground_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


class Orbit:
    """One satellite's element sets, each propagated by SGP4."""

    def __init__(self, elements: Sequence[dict[str, str]]) -> None:
        self.epochs = [datetime.fromisoformat(item["epoch_utc"].replace("Z", "+00:00")) for item in elements]
        self.records = [Satrec.twoline2rv(item["line1"], item["line2"]) for item in elements]

    def subpoint(self, moment: datetime) -> tuple[float, float] | None:
        index = max(0, bisect.bisect_right(self.epochs, moment) - 1)
        jd, fraction = jday(moment.year, moment.month, moment.day, moment.hour, moment.minute,
                            moment.second + moment.microsecond / 1e6)
        error, position, _ = self.records[index].sgp4(jd, fraction)
        if error:
            return None
        return geodetic(position, gmst(moment))


def passes_between(orbit: Orbit, start: datetime, end: datetime, latitude: float, longitude: float,
                   half_swath_km: float) -> list[tuple[datetime, datetime]]:
    """Every pass over the point between two times, as orbits.js's passesBetween."""
    def inside(ms: int) -> bool:
        point = orbit.subpoint(datetime.fromtimestamp(ms / 1000, timezone.utc))
        return point is not None and ground_distance_km(point[0], point[1], latitude, longitude) <= half_swath_km

    def edge(outside: int, inside_ms: int) -> int:
        low, high = outside, inside_ms
        wanted = inside(high)
        while abs(high - low) > 1000:
            middle = round((low + high) / 2)
            if inside(middle) == wanted:
                high = middle
            else:
                low = middle
        return high

    step = min(30000, max(2000, math.floor(half_swath_km / 7 * 1000)))
    start_ms, end_ms = round(start.timestamp() * 1000), round(end.timestamp() * 1000)
    found: list[tuple[int, int]] = []
    previous, was_inside = start_ms, inside(start_ms)
    current = start_ms if was_inside else None
    for ms in range(start_ms + step, end_ms + 1, step):
        is_inside = inside(ms)
        if is_inside and not was_inside:
            current = edge(previous, ms)
        elif not is_inside and was_inside:
            found.append((current, edge(ms, previous) + 1000))
            current = None
        previous, was_inside = ms, is_inside
    if current is not None:
        found.append((current, end_ms))
    as_time = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc)  # noqa: E731
    return [(as_time(a), as_time(b)) for a, b in found]


def incident_passes(satellites: Sequence[dict[str, Any]], start: datetime, end: datetime,
                    centre: tuple[float, float]) -> list[tuple[datetime, datetime, str]]:
    """The passes of every satellite with a swath or acquisitions over the incident: start, end, name."""
    found: list[tuple[datetime, datetime, str]] = []
    for satellite in satellites:
        if satellite.get("acquisitions"):
            for text in satellite["acquisitions"]:
                moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if start <= moment < end:
                    found.append((moment, moment + timedelta(seconds=ACQUISITION_SECONDS), satellite["name"]))
        elif satellite.get("half_swath_km") and available():
            orbit = Orbit(satellite["elements"])
            found += [(a, b, satellite["name"]) for a, b in passes_between(orbit, start, end, *centre, satellite["half_swath_km"])]
    return sorted(found)
