"""SMHI's forecast grid (snow1g), live: the wind arrows over the area and the weather chart over
Scandinavia, as the scenarios show ERA5-Land's wind and MET Norway's weather chart
(app/backend/server.py wind_field, app/backend/met_forecast.py, tools/isobars.py).

Each poll asks when SMHI's latest run was made (createdtime.json) and fetches the grid again only
for a new run or a new hour: the wind speed and direction at every WIND_DOWNSAMPLE-th grid point
inside the area, and at every CHART_DOWNSAMPLE-th point over CHART_BBOX the pressure at sea level
(isobars every ISOBAR_HPA hPa with the highs and lows), the rain of the hour (an image in the
radar's classes) and the probability of thunder (a mark where it reaches THUNDER_PERCENT, one per
THUNDER_SPACING_KM). All of it is a forecast for the next whole hour, not an observation.
"""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw

from app.monitoring import geo
from tools import fetch_smhi_radar, isobars

API = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1"
ATTRIBUTION = "SMHI:s väderprognos (snow1g), öppna data (CC BY 4.0 SE); prognos, inte observationer"
CHART_BBOX = (4.0, 55.0, 31.0, 70.0)  # west, south, east, north: Scandinavia, as the scenarios' weather chart
WIND_DOWNSAMPLE = 4  # about 10 km
CHART_DOWNSAMPLE = 10  # about 25 km
ISOBAR_HPA = 2
THUNDER_PERCENT = 30.0
THUNDER_SPACING_KM = 100.0
RAIN_PIXELS_PER_DEGREE = (10, 20)  # longitude, latitude
RAIN_DOT_PX = 7

Fetch = Callable[[str], bytes]


def grid_url(moment: datetime, parameter: str, downsample: int) -> str:
    return f"{API}/geotype/multipoint/time/{moment:%Y%m%dT%H0000Z}/parameter/{parameter}/data.json?downsample={downsample}"


def next_hour(now: datetime) -> datetime:
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def grid(data: dict[str, Any], parameter: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The answer's latitudes, longitudes and values as 2D arrays: the points come row by row, and a
    row ends where the longitude goes back west."""
    points = data["geometry"]["coordinates"]
    values = data["timeSeries"][0]["data"][parameter]
    width = next((index for index in range(1, len(points)) if points[index][0] < points[index - 1][0]), len(points))
    rows = len(points) // width
    coords = np.asarray(points[:rows * width], dtype=float).reshape(rows, width, 2)
    field = np.asarray(values[:rows * width], dtype=float).reshape(rows, width)
    return coords[..., 1], coords[..., 0], field


def crop(lat: np.ndarray, lon: np.ndarray, bbox: tuple[float, float, float, float], margin: int = 1) -> tuple[slice, slice]:
    """The smallest block of the grid that holds every point inside the box, and a margin."""
    west, south, east, north = bbox
    inside = (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
    rows, cols = np.nonzero(inside)
    if not rows.size:
        return slice(0, 0), slice(0, 0)
    return (slice(max(rows.min() - margin, 0), rows.max() + margin + 1),
            slice(max(cols.min() - margin, 0), cols.max() + margin + 1))


def rain_png(lat: np.ndarray, lon: np.ndarray, rain: np.ndarray, bbox: tuple[float, float, float, float]) -> str:
    """The hour's rain as a PNG data URL over the box, each grid point a dot in the radar's classes."""
    west, south, east, north = bbox
    width = round((east - west) * RAIN_PIXELS_PER_DEGREE[0])
    height = round((north - south) * RAIN_PIXELS_PER_DEGREE[1])
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    colours = fetch_smhi_radar.colours(np.where(rain > 0.05, rain, np.nan))
    half = RAIN_DOT_PX / 2
    for (y, x) in zip(*np.nonzero(colours[..., 3])):
        px = (lon[y, x] - west) / (east - west) * width
        py = (north - lat[y, x]) / (north - south) * height
        draw.rectangle((px - half, py - half, px + half, py + half), fill=tuple(int(v) for v in colours[y, x]))
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def thunder_marks(lat: np.ndarray, lon: np.ndarray, probability: np.ndarray) -> list[list[float]]:
    """A mark where thunder is likely, one per THUNDER_SPACING_KM, the likeliest first."""
    marks: list[list[float]] = []
    for flat in np.argsort(-probability, axis=None):
        y, x = np.unravel_index(flat, probability.shape)
        if probability[y, x] < THUNDER_PERCENT:
            break
        point = [round(float(lat[y, x]), 3), round(float(lon[y, x]), 3)]
        if all(geo.distance_km(*point, *other) > THUNDER_SPACING_KM for other in marks):
            marks.append(point)
    return marks


class Weather:
    """The latest wind and weather chart, fetched again for a new run or a new hour."""

    def __init__(self, bbox: tuple[float, float, float, float], fetch: Fetch) -> None:
        self.bbox = bbox
        self.fetch = fetch
        self.key: tuple[str, str] | None = None
        self.latest: dict[str, Any] | None = None

    def _get(self, moment: datetime, parameter: str, downsample: int) -> dict[str, Any]:
        return json.loads(self.fetch(grid_url(moment, parameter, downsample)))

    def update(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        created = json.loads(self.fetch(f"{API}/createdtime.json"))["createdTime"]
        moment = next_hour(now)
        key = (created, f"{moment:%Y-%m-%dT%H:%M:%SZ}")
        if key == self.key and self.latest is not None:
            return self.latest
        speed = self._get(moment, "wind_speed", WIND_DOWNSAMPLE)
        direction = self._get(moment, "wind_from_direction", WIND_DOWNSAMPLE)
        lat, lon, speeds = grid(speed, "wind_speed")
        _, _, froms = grid(direction, "wind_from_direction")
        west, south, east, north = self.bbox
        inside = (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
        wind = [{"latitude": round(float(a), 4), "longitude": round(float(o), 4), "speed_ms": round(float(v), 1),
                 "from_deg": int(round(float(d))) % 360}
                for a, o, v, d in zip(lat[inside], lon[inside], speeds[inside], froms[inside])]
        pressure_data = self._get(moment, "air_pressure_at_mean_sea_level", CHART_DOWNSAMPLE)
        clat, clon, pressure = grid(pressure_data, "air_pressure_at_mean_sea_level")
        rows, cols = crop(clat, clon, CHART_BBOX)
        clat, clon, pressure = clat[rows, cols], clon[rows, cols], pressure[rows, cols]
        _, _, rain = grid(self._get(moment, "precipitation_amount_mean", CHART_DOWNSAMPLE), "precipitation_amount_mean")
        _, _, thunder = grid(self._get(moment, "thunderstorm_probability", CHART_DOWNSAMPLE), "thunderstorm_probability")
        rain, thunder = rain[rows, cols], thunder[rows, cols]
        chart = isobars.isobars(pressure, clat, clon, interval=ISOBAR_HPA)
        centre = min(wind, key=lambda item: geo.distance_km(item["latitude"], item["longitude"], (south + north) / 2,
                                                            (west + east) / 2)) if wind else None
        self.latest = {"created_utc": created, "valid_utc": key[1], "attribution": ATTRIBUTION, "wind": wind, "centre_wind": centre,
                       "chart": {**chart, "bbox": list(CHART_BBOX), "rain_png": rain_png(clat, clon, rain, CHART_BBOX),
                                 "thunder": thunder_marks(clat, clon, thunder)}}
        self.key = key
        return self.latest

    def summary(self) -> dict[str, Any] | None:
        """What the state carries: the times and the wind at the area's middle; the rest at /api/weather."""
        if not self.latest:
            return None
        return {key: self.latest[key] for key in ("created_utc", "valid_utc", "centre_wind", "attribution")}
