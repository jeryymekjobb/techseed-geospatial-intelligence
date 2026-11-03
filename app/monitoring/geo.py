"""Coordinates and simple geometry for the monitoring: SWEREF 99 TM to WGS 84, distances, and
points and polygons in GeoJSON's (longitude, latitude) order."""

from __future__ import annotations

import math
from typing import Any, Iterable

EARTH_RADIUS_KM = 6371.0


def sweref99tm_to_wgs84(northing: float, easting: float) -> tuple[float, float]:
    """Latitude and longitude (degrees) of a SWEREF 99 TM point: Lantmäteriet's formulas for the
    inverse Gauss-Krüger projection on GRS 80, central meridian 15 E, scale 0.9996, false easting 500 km."""
    axis, flattening = 6378137.0, 1 / 298.257222101
    central, scale, false_easting = math.radians(15.0), 0.9996, 500000.0
    e2 = flattening * (2 - flattening)
    n = flattening / (2 - flattening)
    a_roof = axis / (1 + n) * (1 + n * n / 4 + n ** 4 / 64)
    d1 = n / 2 - 2 * n ** 2 / 3 + 37 * n ** 3 / 96 - n ** 4 / 360
    d2 = n ** 2 / 48 + n ** 3 / 15 - 437 * n ** 4 / 1440
    d3 = 17 * n ** 3 / 480 - 37 * n ** 4 / 840
    d4 = 4397 * n ** 4 / 161280
    xi = northing / (scale * a_roof)
    eta = (easting - false_easting) / (scale * a_roof)
    xi_prim = (xi - d1 * math.sin(2 * xi) * math.cosh(2 * eta) - d2 * math.sin(4 * xi) * math.cosh(4 * eta)
               - d3 * math.sin(6 * xi) * math.cosh(6 * eta) - d4 * math.sin(8 * xi) * math.cosh(8 * eta))
    eta_prim = (eta - d1 * math.cos(2 * xi) * math.sinh(2 * eta) - d2 * math.cos(4 * xi) * math.sinh(4 * eta)
                - d3 * math.cos(6 * xi) * math.sinh(6 * eta) - d4 * math.cos(8 * xi) * math.sinh(8 * eta))
    phi_star = math.asin(math.sin(xi_prim) / math.cosh(eta_prim))
    delta_lambda = math.atan(math.sinh(eta_prim) / math.cos(xi_prim))
    a = e2 + e2 ** 2 + e2 ** 3 + e2 ** 4
    b = -(7 * e2 ** 2 + 17 * e2 ** 3 + 30 * e2 ** 4) / 6
    c = (224 * e2 ** 3 + 889 * e2 ** 4) / 120
    d = -(4279 * e2 ** 4) / 1260
    s2 = math.sin(phi_star) ** 2
    phi = phi_star + math.sin(phi_star) * math.cos(phi_star) * (a + b * s2 + c * s2 ** 2 + d * s2 ** 3)
    return math.degrees(phi), math.degrees(central + delta_lambda)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def polygons(geometry: dict[str, Any] | None) -> list[list[list[list[float]]]]:
    """A GeoJSON Polygon or MultiPolygon as a list of polygons (rings of [lon, lat])."""
    if not geometry:
        return []
    if geometry.get("type") == "Polygon":
        return [geometry["coordinates"]]
    if geometry.get("type") == "MultiPolygon":
        return list(geometry["coordinates"])
    return []


def _in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def contains(geometry: dict[str, Any] | None, lat: float, lon: float) -> bool:
    """Whether the point lies in the polygon(s), holes left out."""
    for polygon in polygons(geometry):
        if polygon and _in_ring(lon, lat, polygon[0]) and not any(_in_ring(lon, lat, hole) for hole in polygon[1:]):
            return True
    return False


def _vertices(geometry: dict[str, Any] | None) -> Iterable[tuple[float, float]]:
    for polygon in polygons(geometry):
        for ring in polygon[:1]:
            for lon, lat, *_ in ring:
                yield lat, lon


def tile_pixel(lat: float, lon: float, z: int, x: int, y: int, size: int = 256) -> tuple[float, float]:
    """A point's pixel position in the Web Mercator tile z/x/y."""
    n = 2 ** z
    px = ((lon + 180.0) / 360.0 * n - x) * size
    py = ((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n - y) * size
    return px, py


def overlaps(first: dict[str, Any] | None, second: dict[str, Any] | None) -> bool:
    """Whether two polygons share land: a corner of one lies in the other. Two polygons that only
    cross without either having a corner inside the other are missed; for a county's warning area
    against a municipality that does not happen."""
    return (any(contains(second, lat, lon) for lat, lon in _vertices(first))
            or any(contains(first, lat, lon) for lat, lon in _vertices(second)))
