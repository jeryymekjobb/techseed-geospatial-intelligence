"""Synthetic IoT sensors in the fire area – illustrative, not measurements.

There were no TechSeed sensors in the forest in 2014. To show how ground sensors
would confirm a satellite detection, the demo places a few invented sensors around
the fire and computes what they could have shown at the scenario clock:

- the front is the convex hull of all FIRMS detections so far (as in forecast.py);
- the temperature is the ERA5-Land 2 m temperature at the nearest grid point plus
  a heat term HEAT_MAX_C * exp(-distance / HEAT_SCALE_M) that is largest at and
  inside the front;
- smoke is DETECTED within SMOKE_NEAR_M of the front, or within SMOKE_DOWNWIND_M
  when the sensor lies downwind of the front (within SMOKE_SECTOR_DEG of the
  direction the ERA5-Land wind blows to at the fire);
- a sensor confirms the fire when it detects smoke or its heat term is at least
  CONFIRM_HEAT_C.

The positions, the constants and therefore the values are invented for the demo;
they are not a physical model and must be shown as synthetic.
"""

from __future__ import annotations

import bisect
import math
from datetime import datetime
from functools import lru_cache
from typing import Any, Sequence

from tools import fire_spread as fs

LABEL = "Syntetiska sensorer – beräknade ur brandfront och väder, inte mätningar"
# Invented positions around the fire (id, name, latitude, longitude).
SENSORS = (
    ("sensor-17", "Sensor 17", 59.905, 16.135),
    ("sensor-08", "Sensor 08", 59.950, 16.235),
    ("sensor-23", "Sensor 23", 59.985, 16.060),
)
HEAT_MAX_C = 25.0
HEAT_SCALE_M = 1500.0
CONFIRM_HEAT_C = 5.0
SMOKE_NEAR_M = 1000.0
SMOKE_DOWNWIND_M = 6000.0
SMOKE_SECTOR_DEG = 30.0

Detection = tuple[datetime, float, float]  # time, latitude, longitude


class SyntheticSensors:
    def __init__(self, detections: Sequence[Detection], wind: dict[str, Any], centre: tuple[float, float]) -> None:
        ordered = sorted(detections)
        self.projector = fs.Projector(*centre)
        self.times = [moment for moment, _, _ in ordered]
        self.points = [self.projector.xy(lat, lon) for _, lat, lon in ordered]
        self.wind = wind
        self.wind_times = [datetime.fromisoformat(text.replace("Z", "+00:00")) for text in wind["times_utc"]]
        self.wind_points = [self.projector.xy(lat, lon) for lat, lon in wind["points"]]
        self.sensors = [(sensor_id, name, lat, lon, self.projector.xy(lat, lon)) for sensor_id, name, lat, lon in SENSORS]
        self.hull = lru_cache(maxsize=64)(self._hull)

    def _hull(self, count: int) -> tuple[fs.Point, ...]:
        return tuple(fs.convex_hull(self.points[:count]))

    def _nearest_wind_point(self, point: fs.Point) -> int:
        return min(range(len(self.wind_points)), key=lambda index: math.dist(point, self.wind_points[index]))

    def _hour(self, clock: datetime) -> int | None:
        index = bisect.bisect_right(self.wind_times, clock) - 1
        return index if index >= 0 else None

    def at(self, clock: datetime, failed: Sequence[str | None] = (), placed: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
        """The sensors at the scenario clock; `failed` are sensor ids mission control failed,
        `placed` the sensors the operator placed on the map (id, name, latitude, longitude),
        computed in the same way after the fixed ones."""
        hull = self.hull(bisect.bisect_right(self.times, clock))
        hour = self._hour(clock)
        blows_to = None
        if hull and hour is not None:
            _, wind_from, _ = self.wind["values"][hour][self._nearest_wind_point(fs.centroid(hull))]
            blows_to = (wind_from + 180) % 360
        sensors = []
        extra = [(item["id"], item["name"], item["latitude"], item["longitude"], self.projector.xy(item["latitude"], item["longitude"]))
                 for item in placed]
        for index, (sensor_id, name, lat, lon, point) in enumerate([*self.sensors, *extra]):
            item: dict[str, Any] = {"id": sensor_id, "name": name, "latitude": lat, "longitude": lon, "synthetic": True,
                                    "placed": index >= len(self.sensors)}
            if sensor_id in failed:
                sensors.append({**item, "status": "failed", "temp_c": None, "smoke": None, "distance_km": None, "confirms": False})
                continue
            distance = fs.distance_to_hull(point, hull) if hull else math.inf
            heat = HEAT_MAX_C * math.exp(-distance / HEAT_SCALE_M) if math.isfinite(distance) else 0.0
            air = None if hour is None else self.wind["values"][hour][self._nearest_wind_point(point)][2]
            downwind = False
            if blows_to is not None and distance <= SMOKE_DOWNWIND_M:
                centre = fs.centroid(hull)
                downwind = fs.angle_difference(fs.bearing(point[0] - centre[0], point[1] - centre[1]), blows_to) <= SMOKE_SECTOR_DEG
            smoke = distance <= SMOKE_NEAR_M or downwind
            sensors.append({
                **item,
                "status": "ok",
                "temp_c": None if air is None else round(air + heat, 1),
                "smoke": "DETECTED" if smoke else "NONE",
                "distance_km": round(distance / 1000.0, 2) if math.isfinite(distance) else None,
                "confirms": smoke or heat >= CONFIRM_HEAT_C,
            })
        operating = [item for item in sensors if item["status"] == "ok"]
        return {
            "label": LABEL,
            "sensors": sensors,
            "confirms": sum(1 for item in operating if item["confirms"]),
            "operating": len(operating),
        }
