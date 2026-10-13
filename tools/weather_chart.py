"""The weather chart's rain and lightning from a MEPS run (tools/fetch_met_forecasts.py).

The rain of the three hours up to the chart's time becomes a transparent PNG on a regular grid of
latitude and longitude, which both maps lay over the chart's area; each pixel takes the nearest
MEPS grid point, found through MEPS's Lambert conformal projection. The lightning is a symbol where
MEPS's combined thunderstorm index reaches THUNDER, one per THUNDER_SPACING_KM.
"""

from __future__ import annotations

import base64
import io
import math
from typing import Any, Sequence

EARTH_RADIUS_M = 6_371_000.0
STANDARD_PARALLEL = 63.0
CENTRAL_MERIDIAN = 15.0
# The rain's classes in the three hours (mm, at least) and their colours, light blue to purple.
RAIN_CLASSES = [(0.3, (155, 211, 255, 150)), (1.0, (79, 163, 224, 175)), (3.0, (31, 95, 168, 195)), (10.0, (123, 47, 191, 210))]
PIXELS_PER_DEGREE = (10, 20)  # longitude, latitude: about 5 km each way at 62° N
# A symbol where the model's thunder variable reaches this: MEPS's combined thunderstorm index (2018)
# and its lightning index (from 2024); AROME-MetCoOp (2014) has none.
THUNDER_THRESHOLDS = {"thunderstorm_index_combined": 0.6, "lightning_index": 0.6}
THUNDER = THUNDER_THRESHOLDS["thunderstorm_index_combined"]
THUNDER_SPACING_KM = 100.0


def lambert_xy(latitude: Any, longitude: Any) -> tuple[Any, Any]:
    """MEPS's projection (lat_0 = lat_1 = lat_2 = 63, lon_0 = 15, a sphere of R 6371 km) in metres."""
    import numpy as np

    phi1 = math.radians(STANDARD_PARALLEL)
    n = math.sin(phi1)
    f = math.cos(phi1) * math.tan(math.pi / 4 + phi1 / 2) ** n / n
    rho0 = EARTH_RADIUS_M * f / math.tan(math.pi / 4 + phi1 / 2) ** n
    rho = EARTH_RADIUS_M * f / np.tan(math.pi / 4 + np.radians(latitude) / 2) ** n
    theta = n * np.radians(np.asarray(longitude) - CENTRAL_MERIDIAN)
    return rho * np.sin(theta), rho0 - rho * np.cos(theta)


def rain_png(rain_mm: Any, xs: Sequence[float], ys: Sequence[float], area: Sequence[float]) -> str:
    """The rain over `area` (west, south, east, north) as a PNG data URI: each pixel the nearest grid
    point (grid rows `ys` and columns `xs` in projection metres), transparent where it is dry."""
    import numpy as np
    from PIL import Image

    west, south, east, north = area
    width = round((east - west) * PIXELS_PER_DEGREE[0])
    height = round((north - south) * PIXELS_PER_DEGREE[1])
    longitudes = west + (np.arange(width) + 0.5) / PIXELS_PER_DEGREE[0]
    latitudes = north - (np.arange(height) + 0.5) / PIXELS_PER_DEGREE[1]
    lon_grid, lat_grid = np.meshgrid(longitudes, latitudes)
    x, y = lambert_xy(lat_grid, lon_grid)
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    col = np.rint((x - xs[0]) / (xs[1] - xs[0])).astype(int)
    row = np.rint((y - ys[0]) / (ys[1] - ys[0])).astype(int)
    inside = (col >= 0) & (col < len(xs)) & (row >= 0) & (row < len(ys))
    values = np.zeros((height, width))
    values[inside] = np.asarray(rain_mm, dtype=float)[row[inside], col[inside]]
    rgba = np.zeros((height, width, 4), dtype="u1")
    for limit, colour in RAIN_CLASSES:
        rgba[np.nan_to_num(values) >= limit] = colour
    buffer = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def thunder_marks(index: Any, latitudes: Any, longitudes: Any, threshold: float = THUNDER) -> list[dict[str, float]]:
    """Where the thunder index reaches `threshold`, strongest first, one per THUNDER_SPACING_KM."""
    import numpy as np

    values = np.nan_to_num(np.asarray(index, dtype=float))
    rows, cols = np.where(values >= threshold)
    order = np.argsort(-values[rows, cols])
    kept: list[dict[str, float]] = []
    for k in order:
        lat, lon = float(latitudes[rows[k], cols[k]]), float(longitudes[rows[k], cols[k]])
        if all(math.hypot((lat - other["latitude"]) * 111.2, (lon - other["longitude"]) * 111.2 * math.cos(math.radians(lat)))
               >= THUNDER_SPACING_KM for other in kept):
            kept.append({"latitude": round(lat, 4), "longitude": round(lon, 4), "index": round(float(values[rows[k], cols[k]]), 2)})
    return kept
