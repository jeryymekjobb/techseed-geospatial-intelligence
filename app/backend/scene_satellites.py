"""Where each image's satellite was when it took the image, for a scenario that shows no orbits.

tools/fetch_scene_elements.py keeps, per scene, the element set nearest the image (Space-Track
gp_history). A catalogue's time is not when the satellite was over the incident: Sentinel-2's is
the start of the whole datatake, which begins far north (2 000-3 800 km from Falsterbo), so the
moment taken is when the satellite came nearest the incident between OVERPASS_BEFORE before and
OVERPASS_AFTER after that time. SGP4 (passes.py's propagation and WGS 84 conversion) gives the
point below the satellite then, its height and how far and in which direction that point lies from
the incident. The position is computed, not observed; the screens say so.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from app.backend import passes, scenario

ELEMENTS_FILE = scenario.SCENE_ELEMENTS_FILE
DIRECTIONS = ("norr", "nordost", "öster", "sydost", "söder", "sydväst", "väster", "nordväst")
LABEL = "Läge när bilden togs, beräknat ur banelement (SGP4) – inte en observation"
OVERPASS_BEFORE, OVERPASS_AFTER = timedelta(minutes=10), timedelta(minutes=30)


def direction(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """The compass direction, in eight points, from the first point to the second."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta = math.radians(lon2 - lon1)
    bearing = math.degrees(math.atan2(math.sin(delta) * math.cos(phi2),
                                      math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta)))
    return DIRECTIONS[round((bearing % 360) / 45) % 8]


def position(element: dict[str, str], moment: datetime) -> dict[str, float] | None:
    """The point below the satellite and its height above the WGS 84 ellipsoid at the moment."""
    if not passes.available():
        return None
    record = passes.Satrec.twoline2rv(element["line1"], element["line2"])
    jd, fraction = passes.jday(moment.year, moment.month, moment.day, moment.hour, moment.minute,
                               moment.second + moment.microsecond / 1e6)
    error, xyz, velocity = record.sgp4(jd, fraction)
    if error:
        return None
    latitude, longitude = passes.geodetic(xyz, passes.gmst(moment))
    # The height over the ellipsoid along its normal at that latitude.
    flattening = (passes.WGS84_A - passes.WGS84_B) / passes.WGS84_A
    e2 = 2 * flattening - flattening * flattening
    phi = math.radians(latitude)
    normal = passes.WGS84_A / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    height = math.hypot(xyz[0], xyz[1]) / math.cos(phi) - normal
    return {"latitude": round(latitude, 4), "longitude": round(longitude, 4), "height_km": round(height, 1),
            "speed_km_s": round(math.sqrt(sum(value * value for value in velocity)), 2)}


def overpass(element: dict[str, str], around: datetime, centre: tuple[float, float]) -> tuple[datetime, dict[str, float]] | None:
    """The moment the satellite came nearest the centre near `around`, and its position then:
    every 10 s over the window, then every second round the nearest."""
    def distance(moment: datetime) -> tuple[float, dict[str, float] | None]:
        point = position(element, moment)
        return (math.inf, None) if point is None else (
            passes.ground_distance_km(centre[0], centre[1], point["latitude"], point["longitude"]), point)

    steps = int((OVERPASS_BEFORE + OVERPASS_AFTER).total_seconds() // 10)
    coarse = min((around - OVERPASS_BEFORE + timedelta(seconds=10 * step) for step in range(steps + 1)), key=lambda moment: distance(moment)[0])
    first, last = around - OVERPASS_BEFORE, around + OVERPASS_AFTER
    best = min((moment for moment in (coarse + timedelta(seconds=second) for second in range(-10, 11)) if first <= moment <= last),
               key=lambda moment: distance(moment)[0])
    point = distance(best)[1]
    return None if point is None else (best, point)


@lru_cache(maxsize=1)
def positions() -> dict[str, dict[str, Any]]:
    """Each scene's satellite at the time of its image, by scene id; empty without the file."""
    if ELEMENTS_FILE is None or not ELEMENTS_FILE.is_file():
        return {}
    centre_lat, centre_lon = scenario.FIRE_CENTRE
    found = {}
    for scene, element in json.loads(ELEMENTS_FILE.read_text(encoding="utf-8"))["scenes"].items():
        moment = datetime.fromisoformat(element["acquired_utc"].replace("Z", "+00:00"))
        nearest = overpass(element, moment, (centre_lat, centre_lon))
        if nearest is None:
            continue
        over, point = nearest
        found[scene] = {
            **point, "norad": element["norad"], "satellite": element["satellite"], "epoch_utc": element["epoch_utc"],
            "time_utc": over.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "distance_km": round(passes.ground_distance_km(centre_lat, centre_lon, point["latitude"], point["longitude"])),
            "direction": direction(centre_lat, centre_lon, point["latitude"], point["longitude"]),
        }
    return found


def with_positions(layer: dict[str, Any] | None) -> dict[str, Any] | None:
    """The image layer with each scene's satellite at its time (`satellite_at`) where known."""
    found = positions()
    if layer is None or not found:
        return layer
    scenes = [{**scene, "satellite_at": found[scene["scene"]]} if scene["scene"] in found else scene for scene in layer["scenes"]]
    return {**layer, "scenes": scenes, "satellite_label": LABEL}
