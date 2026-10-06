"""Synthetic overflow sensors at the municipality's critical stormwater points (the flood scenario).

There were no TechSeed sensors in Sundsvall's stormwater system in August 2026. To show how
ground sensors would confirm a flood, a few points are given a synthetic sensor shaped like
diwise's `Sewer` entity (level, fill percentage, overflow start, end and cumulative time;
diwise/iot-transform-fiware). Each is driven by the real hourly rain of its nearest gauge
through a simple reservoir: the rain, scaled up where the municipality's cloudburst model
gives deep water at the point, fills it; it drains at a fixed rate; it overflows when full.

The parameters are illustrative, not calibrated against any measurement, and the screens
mark every value synthetic.
"""

from __future__ import annotations

import bisect
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

LABEL = "Syntetiska bräddgivare – beräknade ur verkligt regn och kommunens skyfallsmodell, inte mätningar"
MAX_NODES = 8
MIN_MODEL_DEPTH_M = 0.1      # points where the 100-year model gives less water are not used
CAPACITY_MM = 15.0           # the reservoir, in millimetres of rain on its catchment
DRAIN_MM_PER_H = 6.0         # what the pipe carries away per hour
DEPTH_GAIN = 4.0             # inflow = rain x (1 + DEPTH_GAIN x model depth in metres)
WELL_DEPTH_M = 2.0           # the level runs from 0,2 m (empty) to the top of the well (full)
EMPTY_LEVEL_M = 0.2
HOUR = timedelta(hours=1)


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def format_utc(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * 111.2
    dx = (lon2 - lon1) * 111.2 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def choose_points(features: Sequence[dict[str, Any]], count: int = MAX_NODES) -> list[dict[str, Any]]:
    """The deepest modelled points, first one per area, then the next deepest."""
    usable = [item for item in features if (item["properties"].get("model_depth_100y_m") or 0) >= MIN_MODEL_DEPTH_M]
    usable.sort(key=lambda item: (-item["properties"]["model_depth_100y_m"], item["properties"].get("fid", 0)))
    chosen: list[dict[str, Any]] = []
    areas: set[str] = set()
    for item in usable:
        if item["properties"].get("omrade") not in areas:
            chosen.append(item)
            areas.add(item["properties"].get("omrade"))
    chosen += [item for item in usable if item not in chosen]
    return chosen[:count]


def reservoir(rain_mm: Sequence[float], inflow_factor: float) -> list[tuple[float, bool]]:
    """Storage (mm) and whether it overflows, after each hour of rain."""
    storage = 0.0
    states = []
    for rain in rain_mm:
        wanted = storage + rain * inflow_factor - DRAIN_MM_PER_H
        storage = min(CAPACITY_MM, max(0.0, wanted))
        states.append((storage, wanted > CAPACITY_MM))
    return states


class FloodSensors:
    def __init__(self, points_file: Path, stations: Sequence[dict[str, Any]], start: datetime, end: datetime) -> None:
        features = json.loads(points_file.read_text(encoding="utf-8"))["features"] if points_file.is_file() else []
        self.start = start
        self.hours = [start + HOUR * (index + 1) for index in range(int((end - start) / HOUR))]
        self.stations = list(stations)
        self.nodes = []
        for index, feature in enumerate(choose_points(features), start=1):
            props = feature["properties"]
            longitude, latitude = feature["geometry"]["coordinates"][:2]
            self.nodes.append(self._node(f"dv-{index:02d}", f"DV{index} {props.get('omrade') or ''}".strip(), latitude, longitude,
                                         props.get("model_depth_100y_m"), props))

    def _rain(self, station: dict[str, Any]) -> list[float]:
        # The municipality's gauges list only hours with rain: a missing hour is dry.
        by_hour = {observation["time_utc"]: observation.get("precip_mm") or 0.0 for observation in station["observations"]}
        return [by_hour.get(format_utc(moment), 0.0) for moment in self.hours]

    def _node(self, node_id: str, name: str, latitude: float, longitude: float, depth: float | None,
              props: dict[str, Any] | None = None) -> dict[str, Any]:
        station = min(self.stations, key=lambda item: distance_km(latitude, longitude, item["latitude"], item["longitude"]))
        factor = 1.0 + DEPTH_GAIN * (depth or 0.0)
        props = props or {}
        return {
            "id": node_id, "name": name, "latitude": latitude, "longitude": longitude, "model_depth_m": depth,
            "object": props.get("objekttyp"), "location": props.get("lokalisering"), "problem": props.get("problem"),
            "gauge": station["name"], "states": reservoir(self._rain(station), factor),
        }

    def at(self, clock: datetime, failed: Sequence[str | None] = (), placed: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
        """The sensors at the clock, shaped like diwise's Sewer; placed sensors have no model depth."""
        hour = bisect.bisect_right(self.hours, clock) - 1
        extra = [self._node(item["id"], item["name"], item["latitude"], item["longitude"], None) for item in placed] if self.stations else []
        sensors = []
        for index, node in enumerate([*self.nodes, *extra]):
            item: dict[str, Any] = {key: node[key] for key in ("id", "name", "latitude", "longitude", "model_depth_m", "object",
                                                              "location", "problem", "gauge")}
            item.update({"kind": "sewer", "synthetic": True, "placed": index >= len(self.nodes)})
            if node["id"] in failed:
                sensors.append({**item, "status": "failed", "level_m": None, "percent": None, "overflow": None, "confirms": False})
                continue
            states = node["states"][: hour + 1] if hour >= 0 else []
            storage, overflowing = states[-1] if states else (0.0, False)
            observed = ended = None
            for at, (_, flowing) in zip(self.hours, states):
                if flowing and (observed is None or ended is not None):
                    observed, ended = at - HOUR, None
                elif not flowing and observed is not None and ended is None:
                    ended = at - HOUR
            share = storage / CAPACITY_MM
            sensors.append({
                **item,
                "status": "ok",
                "level_m": round(EMPTY_LEVEL_M + share * (WELL_DEPTH_M - EMPTY_LEVEL_M), 2),
                "percent": round(100 * share),
                "overflow": "started" if overflowing else "stopped",
                "overflow_observed_at": format_utc(observed) if observed else None,
                "overflow_ended_at": format_utc(ended) if ended else None,
                "overflow_cumulative_h": sum(1 for _, flowing in states if flowing),
                "confirms": overflowing,
            })
        operating = [item for item in sensors if item["status"] == "ok"]
        return {
            "label": LABEL,
            "sensors": sensors,
            "confirms": sum(1 for item in operating if item["confirms"]),
            "operating": len(operating),
        }
