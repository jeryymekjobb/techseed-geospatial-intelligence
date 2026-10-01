"""Fire-spread estimation and hindcast for the Västmanland 2014 scenario.

Building blocks:

- Canadian Fire Weather Index system (Van Wagner 1987; hourly fine fuel moisture,
  Van Wagner 1977) from ERA5-Land weather;
- Canadian Fire Behaviour Prediction rate of spread for boreal conifer fuel
  (FBP C-2 and C-3, Forestry Canada 1992) and elliptical wind-driven growth;
- observed spread from FIRMS detections between satellite passes;
- forecasts made at each pass with data up to that pass only, compared with
  later detections (hindcast).

All functions use the standard library. Distances are metres in a local
equirectangular projection around the fire; times are UTC.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Sequence

Point = tuple[float, float]

# ---------------------------------------------------------------- geometry


@dataclass(frozen=True)
class Projector:
    lat0: float
    lon0: float

    def xy(self, lat: float, lon: float) -> Point:
        return ((lon - self.lon0) * 111_320.0 * math.cos(math.radians(self.lat0)), (lat - self.lat0) * 110_540.0)

    def latlon(self, x: float, y: float) -> tuple[float, float]:
        return (self.lat0 + y / 110_540.0, self.lon0 + x / (111_320.0 * math.cos(math.radians(self.lat0))))


def convex_hull(points: Iterable[Point]) -> list[Point]:
    """Counter-clockwise hull without repeating the first point (Andrew's monotone chain)."""
    unique = sorted(set(points))
    if len(unique) <= 2:
        return unique

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[Point] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def polygon_area(polygon: Sequence[Point]) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, [*polygon[1:], polygon[0]]))) / 2.0


def centroid(points: Sequence[Point]) -> Point:
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def _segment_distance(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def inside_convex(point: Point, hull: Sequence[Point]) -> bool:
    if len(hull) < 3:
        return False
    for a, b in zip(hull, [*hull[1:], hull[0]]):
        if (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]) < 0:
            return False
    return True


def distance_to_hull(point: Point, hull: Sequence[Point]) -> float:
    """0 inside, otherwise the distance to the hull boundary (or to its points if degenerate)."""
    if not hull:
        return math.inf
    if len(hull) < 3:
        return min(_segment_distance(point, a, b) for a, b in zip(hull, [*hull[1:], hull[0]]))
    if inside_convex(point, hull):
        return 0.0
    return min(_segment_distance(point, a, b) for a, b in zip(hull, [*hull[1:], hull[0]]))


def bearing(dx: float, dy: float) -> float:
    """Compass bearing of a vector, 0 = north, 90 = east."""
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def angle_difference(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


# ---------------------------------------------------------- fire weather index

_DMC_DAY_LENGTH = [6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0]
_DC_DAY_LENGTH = [-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6]
FWI_START = (85.0, 6.0, 15.0)  # FFMC, DMC, DC at the start of the season


def _ffmc_rain(mo: float, rain: float) -> float:
    if mo > 150.0:
        mo = mo + 42.5 * rain * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rain)) + 0.0015 * (mo - 150.0) ** 2 * math.sqrt(rain)
    else:
        mo = mo + 42.5 * rain * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rain))
    return min(mo, 250.0)


def _ffmc_step(ffmc0: float, t: float, rh: float, wind_kmh: float, rain: float, rate: float, rain_threshold: float) -> float:
    """One FFMC step; `rate` is 0.581 for a day and 0.0579 for an hour (Van Wagner 1977)."""
    mo = 147.2 * (101.0 - ffmc0) / (59.5 + ffmc0)
    if rain > rain_threshold:
        mo = _ffmc_rain(mo, rain - rain_threshold if rain_threshold else rain)
    ed = 0.942 * rh ** 0.679 + 11.0 * math.exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - t) * (1.0 - math.exp(-0.115 * rh))
    if mo > ed:
        ko = 0.424 * (1.0 - (rh / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind_kmh) * (1.0 - (rh / 100.0) ** 8)
        m = ed + (mo - ed) * 10.0 ** (-ko * rate * math.exp(0.0365 * t))
    else:
        ew = 0.618 * rh ** 0.753 + 10.0 * math.exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - t) * (1.0 - math.exp(-0.115 * rh))
        if mo < ew:
            k1 = 0.424 * (1.0 - ((100.0 - rh) / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind_kmh) * (1.0 - ((100.0 - rh) / 100.0) ** 8)
            m = ew - (ew - mo) * 10.0 ** (-k1 * rate * math.exp(0.0365 * t))
        else:
            m = mo
    return max(0.0, min(101.0, 59.5 * (250.0 - m) / (147.2 + m)))


def ffmc_daily(ffmc0: float, t: float, rh: float, wind_kmh: float, rain: float) -> float:
    return _ffmc_step(ffmc0, t, rh, wind_kmh, rain, 0.581, 0.5)


def ffmc_hourly(ffmc0: float, t: float, rh: float, wind_kmh: float, rain: float) -> float:
    return _ffmc_step(ffmc0, t, rh, wind_kmh, rain, 0.0579, 0.0)


def dmc_daily(dmc0: float, t: float, rh: float, rain: float, month: int) -> float:
    t = max(t, -1.1)
    rk = 1.894 * (t + 1.1) * (100.0 - rh) * _DMC_DAY_LENGTH[month - 1] * 1e-4
    if rain > 1.5:
        rw = 0.92 * rain - 1.27
        wmi = 20.0 + 280.0 / math.exp(0.023 * dmc0)
        if dmc0 <= 33.0:
            b = 100.0 / (0.5 + 0.3 * dmc0)
        elif dmc0 <= 65.0:
            b = 14.0 - 1.3 * math.log(dmc0)
        else:
            b = 6.2 * math.log(dmc0) - 17.2
        wmr = wmi + 1000.0 * rw / (48.77 + b * rw)
        pr = max(0.0, 43.43 * (5.6348 - math.log(wmr - 20.0)))
    else:
        pr = dmc0
    return pr + rk


def dc_daily(dc0: float, t: float, rain: float, month: int) -> float:
    t = max(t, -2.8)
    pe = max(0.0, (0.36 * (t + 2.8) + _DC_DAY_LENGTH[month - 1]) / 2.0)
    if rain > 2.8:
        rd = 0.83 * rain - 1.27
        qr = 800.0 * math.exp(-dc0 / 400.0) + 3.937 * rd
        dr = max(0.0, 400.0 * math.log(800.0 / qr))
    else:
        dr = dc0
    return dr + pe


def isi(ffmc: float, wind_kmh: float) -> float:
    fm = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    return 19.115 * math.exp(-0.1386 * fm) * (1.0 + fm ** 5.31 / 4.93e7) * math.exp(0.05039 * wind_kmh)


def bui(dmc: float, dc: float) -> float:
    if dmc == 0 and dc == 0:
        return 0.0
    if dmc <= 0.4 * dc:
        value = 0.8 * dmc * dc / (dmc + 0.4 * dc)
    else:
        value = dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)
    return max(0.0, value)


def fwi(isi_value: float, bui_value: float) -> float:
    if bui_value <= 80.0:
        bb = 0.1 * isi_value * (0.626 * bui_value ** 0.809 + 2.0)
    else:
        bb = 0.1 * isi_value * (1000.0 / (25.0 + 108.64 * math.exp(-0.023 * bui_value)))
    return bb if bb <= 1.0 else math.exp(2.72 * (0.434 * math.log(bb)) ** 0.647)


# ------------------------------------------------------ fire behaviour (FBP)

FUELS = {
    # a, b, c of the rate-of-spread curve; q, BUI0 of the build-up effect
    "C-2": (110.0, 0.0282, 1.5, 0.7, 64.0),
    "C-3": (110.0, 0.0444, 3.0, 0.75, 62.0),
}


def rate_of_spread(isi_value: float, bui_value: float, fuel: str = "C-2") -> float:
    """Head fire rate of spread in m/min for a conifer fuel type."""
    a, b, c, q, bui0 = FUELS[fuel]
    rsi = a * (1.0 - math.exp(-b * isi_value)) ** c
    effect = math.exp(50.0 * math.log(q) * (1.0 / bui_value - 1.0 / bui0)) if bui_value > 0 else 0.0
    return rsi * effect


def length_to_breadth(wind_kmh: float) -> float:
    return 1.0 + 8.729 * (1.0 - math.exp(-0.030 * wind_kmh)) ** 2.155


def back_isi(isi_value: float, wind_kmh: float) -> float:
    """ISI for the back fire: the wind function reversed."""
    return isi_value * math.exp(-2.0 * 0.05039 * wind_kmh)


# ----------------------------------------------------------- spread modelling


@dataclass(frozen=True)
class Weather:
    """Hourly weather at the fire: wind towards which the fire is pushed, plus fire-weather inputs."""

    time: datetime
    temp_c: float
    rh_pct: float
    wind_kmh: float
    wind_from_deg: float
    precip_mm: float


@dataclass
class FireWeather:
    """Daily DMC/DC/BUI and hourly FFMC/ISI, computed forward in time only."""

    hourly: list[Weather]
    noon_hour_utc: int = 11
    ffmc_hour: dict[datetime, float] = field(default_factory=dict)
    daily: dict[str, dict[str, float]] = field(default_factory=dict)

    def compute(self, start: tuple[float, float, float] = FWI_START) -> "FireWeather":
        ffmc, dmc, dc = start
        rain_since_noon = 0.0
        hourly_ffmc = None
        for item in self.hourly:
            rain_since_noon += item.precip_mm
            if item.time.hour == self.noon_hour_utc:
                ffmc = ffmc_daily(ffmc, item.temp_c, item.rh_pct, item.wind_kmh, rain_since_noon)
                dmc = dmc_daily(dmc, item.temp_c, item.rh_pct, rain_since_noon, item.time.month)
                dc = dc_daily(dc, item.temp_c, rain_since_noon, item.time.month)
                b = bui(dmc, dc)
                i = isi(ffmc, item.wind_kmh)
                self.daily[item.time.date().isoformat()] = {
                    "ffmc": ffmc, "dmc": dmc, "dc": dc, "isi": i, "bui": b, "fwi": fwi(i, b), "rain_24h_mm": rain_since_noon,
                }
                rain_since_noon = 0.0
                if hourly_ffmc is None:
                    hourly_ffmc = ffmc
            if hourly_ffmc is not None:
                hourly_ffmc = ffmc_hourly(hourly_ffmc, item.temp_c, item.rh_pct, item.wind_kmh, item.precip_mm)
                self.ffmc_hour[item.time] = hourly_ffmc
        return self

    def bui_at(self, moment: datetime) -> float:
        """BUI of the latest daily computation at or before `moment` (no look-ahead)."""
        day = moment.date() if moment.hour >= self.noon_hour_utc else (moment - timedelta(days=1)).date()
        return self.daily.get(day.isoformat(), {}).get("bui", 0.0)


@dataclass(frozen=True)
class Pass:
    time: datetime
    points: tuple[Point, ...]


def group_passes(detections: Sequence[tuple[datetime, Point]], gap_minutes: float = 20.0) -> list[Pass]:
    """Detections close in time belong to one satellite pass."""
    passes: list[Pass] = []
    current: list[tuple[datetime, Point]] = []
    for moment, point in sorted(detections):
        if current and (moment - current[-1][0]).total_seconds() > gap_minutes * 60:
            passes.append(Pass(current[0][0], tuple(p for _, p in current)))
            current = []
        current.append((moment, point))
    if current:
        passes.append(Pass(current[0][0], tuple(p for _, p in current)))
    return passes


def observed_advance(previous_hull: Sequence[Point], new_points: Sequence[Point], min_distance_m: float = 300.0) -> tuple[float, float | None]:
    """90th-percentile distance of new detections outside the previous hull, and their mean direction."""
    outside = []
    for point in new_points:
        distance = distance_to_hull(point, previous_hull)
        if distance > min_distance_m:
            outside.append((distance, point))
    if not outside:
        return 0.0, None
    distances = sorted(distance for distance, _ in outside)
    p90 = distances[min(len(distances) - 1, int(0.9 * len(distances)))]
    centre = centroid(previous_hull) if previous_hull else (0.0, 0.0)
    dx = sum((point[0] - centre[0]) * distance for distance, point in outside)
    dy = sum((point[1] - centre[1]) * distance for distance, point in outside)
    return p90, bearing(dx, dy)


def ellipse_points(origin: Point, head_m: float, back_m: float, lb: float, towards_deg: float, samples: int = 16) -> list[Point]:
    """Points of a fire ellipse grown from `origin` (rear focus convention simplified to the ignition point)."""
    a = (head_m + back_m) / 2.0
    b = a / lb
    offset = (head_m - back_m) / 2.0
    theta = math.radians(towards_deg)
    ux, uy = math.sin(theta), math.cos(theta)  # downwind unit vector
    vx, vy = uy, -ux                           # crosswind unit vector
    cx, cy = origin[0] + ux * offset, origin[1] + uy * offset
    points = []
    for index in range(samples):
        angle = 2.0 * math.pi * index / samples
        along, across = a * math.cos(angle), b * math.sin(angle)
        points.append((cx + ux * along + vx * across, cy + uy * along + vy * across))
    return points


def grow(hull: Sequence[Point], ros_m_per_h: float, back_m_per_h: float, lb: float, towards_deg: float, hours: float = 1.0) -> list[Point]:
    """Huygens step: every hull vertex grows an ellipse; the new front is the hull of all of them."""
    if ros_m_per_h <= 0:
        return list(hull)
    points = list(hull)
    for vertex in hull:
        points.extend(ellipse_points(vertex, ros_m_per_h * hours, back_m_per_h * hours, lb, towards_deg))
    return convex_hull(points)


@dataclass(frozen=True)
class SpreadStep:
    ros_m_per_h: float
    back_m_per_h: float
    lb: float
    towards_deg: float


def model_step(fire_weather: FireWeather, weather: Weather, fuel: str, factor: float, ffmc_override: float | None = None) -> SpreadStep:
    ffmc = ffmc_override if ffmc_override is not None else fire_weather.ffmc_hour.get(weather.time, 0.0)
    head_isi = isi(ffmc, weather.wind_kmh)
    b = fire_weather.bui_at(weather.time)
    ros = rate_of_spread(head_isi, b, fuel) * 60.0 * factor
    back = rate_of_spread(back_isi(head_isi, weather.wind_kmh), b, fuel) * 60.0 * factor
    return SpreadStep(ros, back, length_to_breadth(weather.wind_kmh), (weather.wind_from_deg + 180.0) % 360.0)


def forecast(
    hull: Sequence[Point],
    steps: Sequence[SpreadStep],
) -> list[list[Point]]:
    """Fronts after each hourly step."""
    fronts = []
    current = list(hull)
    for step in steps:
        current = grow(current, step.ros_m_per_h, step.back_m_per_h, step.lb, step.towards_deg)
        fronts.append(current)
    return fronts
