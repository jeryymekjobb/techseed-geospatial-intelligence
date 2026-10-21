"""Meteosat's fire pixels over the incident (LSA SAF MSG FRP-Pixel; tools/fetch_meteosat_frp.py).

A geostationary satellite stands over the equator; at 60 N it sees the ground about 20 degrees
above the horizon, so its pixels there cover about 26 km² against 9 km² straight below it, and
only the most intense hours of a fire show. The maps draw each pixel as a rectangle of its area,
SAMPLING_KM wide east-west times the slant distance and the rest north-south: the shape is an
approximation, the area is the product's. The log has a line for each quarter with any pixel. A scenario may name a comparison area
(METEOSAT_FRP_COMPARE): a nearby fire Meteosat saw where it missed the scenario's own, which the
panel and the log set against the empty map area, once a day.
Archive data, not live; the screens say so.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from app.backend import scenario

FILE = scenario.METEOSAT_FRP_FILE
LABEL = "Meteosat (geostationär, LSA SAF)"
# In the form EUMETSAT's data policy (article 6.3) asks for, with the year the demo shows it.
ATTRIBUTION = "Contains modified EUMETSAT Meteosat product 2026 (LSA SAF MSG FRP-Pixel, CC BY 4.0)"
# LSA SAF's satellite codes and the names the screens give them.
SATELLITE_NAMES = {"MSG1": "Meteosat-8", "MSG2": "Meteosat-9", "MSG3": "Meteosat-10", "MSG4": "Meteosat-11"}
SAMPLING_KM = 3.0  # SEVIRI's sampling straight below the satellite
GEO_RADIUS_KM = 42164.0
GEO_HEIGHT_KM = 35786.0
EARTH_RADIUS_KM = 6378.137
KM_PER_DEGREE = 111.2


def slant_km(latitude: float, longitude: float, sub_longitude: float = 0.0) -> float:
    """The distance from a satellite over the equator at `sub_longitude` to a point on the ground."""
    cosine = math.cos(math.radians(latitude)) * math.cos(math.radians(longitude - sub_longitude))
    return math.sqrt(GEO_RADIUS_KM ** 2 + EARTH_RADIUS_KM ** 2 - 2 * GEO_RADIUS_KM * EARTH_RADIUS_KM * cosine)


def footprint(latitude: float, longitude: float, area_km2: float) -> list[list[float]]:
    """An approximate pixel round its centre, [[lat, lon], ...] south-west first: SAMPLING_KM east-west
    stretched by the slant distance, and north-south what makes the product's area."""
    east_km = SAMPLING_KM * slant_km(latitude, longitude) / GEO_HEIGHT_KM
    north_km = area_km2 / east_km
    half_lat = north_km / 2 / KM_PER_DEGREE
    half_lon = east_km / 2 / (KM_PER_DEGREE * math.cos(math.radians(latitude)))
    return [[round(latitude + dlat, 5), round(longitude + dlon, 5)]
            for dlat, dlon in ((-half_lat, -half_lon), (-half_lat, half_lon), (half_lat, half_lon), (half_lat, -half_lon))]


@lru_cache(maxsize=1)
def pixels() -> tuple[dict[str, Any], ...]:
    """The scenario's Meteosat fire pixels in time order, each with its satellite's name and footprint."""
    if FILE is None or not FILE.is_file():
        return ()
    found = []
    for feature in json.loads(FILE.read_text(encoding="utf-8"))["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        item = feature["properties"]
        found.append({
            "time_utc": item["time_utc"], "satellite": SATELLITE_NAMES.get(item["satellite"], item["satellite"]),
            "latitude": lat, "longitude": lon, "frp_mw": item["frp_mw"], "pixel_area_km2": item["pixel_area_km2"],
            "area": item.get("area", "incident"),
            "footprint": footprint(lat, lon, item["pixel_area_km2"]),
        })
    return tuple(sorted(found, key=lambda item: item["time_utc"]))


def quarters(items: tuple[dict[str, Any], ...] | None = None) -> list[dict[str, Any]]:
    """For the log: each quarter with any pixel, its satellite, how many and the strongest."""
    grouped: dict[str, dict[str, Any]] = {}
    for item in pixels() if items is None else items:
        if item.get("area", "incident") != "incident":
            continue
        quarter = grouped.setdefault(item["time_utc"], {"time_utc": item["time_utc"], "satellite": item["satellite"],
                                                        "pixels": 0, "max_frp_mw": 0.0})
        quarter["pixels"] += 1
        quarter["max_frp_mw"] = max(quarter["max_frp_mw"], item["frp_mw"] or 0.0)
    return [grouped[key] for key in sorted(grouped)]


def compare_days(items: tuple[dict[str, Any], ...] | None = None) -> list[dict[str, Any]]:
    """For the log: each day Meteosat saw the comparison area's fire, at its first quarter that day,
    with that quarter's pixels and strongest power (what was seen by then, not the day's total)."""
    days: dict[str, dict[str, Any]] = {}
    for item in sorted(pixels() if items is None else items, key=lambda entry: entry["time_utc"]):
        if item.get("area") != "compare":
            continue
        day = days.setdefault(item["time_utc"][:10], {"time_utc": item["time_utc"], "satellite": item["satellite"],
                                                       "pixels": 0, "max_frp_mw": 0.0})
        if item["time_utc"] != day["time_utc"]:
            continue
        day["pixels"] += 1
        day["max_frp_mw"] = max(day["max_frp_mw"], item["frp_mw"] or 0.0)
    # Whether Meteosat had seen the scenario's own fire that day by then.
    own = [item["time_utc"] for item in (pixels() if items is None else items) if item.get("area", "incident") == "incident"]
    return [{**day, "incident_seen": any(key == time[:10] and time <= day["time_utc"] for time in own)}
            for key, day in sorted(days.items())]


def layer() -> dict[str, Any] | None:
    """The maps' layer, the log's quarters and, where the scenario names one, the comparison area with
    the days Meteosat saw its fire; None where the scenario has no pixels."""
    if not pixels():
        return None
    compare = scenario.METEOSAT_FRP_COMPARE
    return {"label": LABEL, "attribution": ATTRIBUTION, "pixels": list(pixels()), "quarters": quarters(),
            "compare": {**{key: value for key, value in compare.items() if key != "bbox"}, "days": compare_days()} if compare else None}
