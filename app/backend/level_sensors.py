"""Synthetic level sensors where roads cross a river's 100-year flow (the river flood scenario).

There were no TechSeed sensors along Skåne's rivers in 2024. To show how ground sensors would
confirm a flood, the points of tools/derive_level_sensor_points.py are given a synthetic level
sensor driven by the real measurements of its SMHI station (hydro.py): it alarms when the
station's latest flow or lake level is above the highest measured there before, and shows that
value as a share of it. A scenario whose stations stayed below their records (Västernorrland
2025) sets a rise instead: the sensor alarms when its station's flow is at least that many times
its flow at the playback's start. A sensor the operator places takes the nearest station.

The sensors are shaped as the overflow sensors (flood_sensors.py), so failures, IOT ON/OFF and
placed sensors work the same, and the screens mark every value synthetic.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Sequence

from app.backend.flood_sensors import distance_km, parse_utc

LABEL = "Syntetiska nivågivare – larmet härleds ur SMHI:s uppmätta flöde eller nivå, inte mätningar"


def round_half_up(value: float) -> int:
    """`value` to a whole number with a half away from zero (2.5 to 3, -2.5 to -3), as the screens and
    the voice say it; Python's round() takes a half to the even number (2.5 to 2)."""
    return int(Decimal(repr(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def latest(station: dict[str, Any], clock: datetime) -> float | None:
    value = None
    for item in station["observations"]:
        if parse_utc(item["time_utc"]) > clock:
            break
        value = item["value"]
    return value


class LevelSensors:
    def __init__(self, points_file: Path | None, stations: Sequence[dict[str, Any]], *, rise: float | None = None,
                 start: datetime | None = None) -> None:
        self.rise, self.start = rise, start
        features = json.loads(points_file.read_text(encoding="utf-8"))["features"] if points_file and points_file.is_file() else []
        self.stations = {station["id"]: station for station in stations if station.get("earlier_max")}
        self.nodes = []
        for feature in features:
            props = feature["properties"]
            longitude, latitude = feature["geometry"]["coordinates"][:2]
            if props["station"] in self.stations:
                self.nodes.append({"id": props["id"], "name": props["name"], "latitude": latitude, "longitude": longitude,
                                   "river": props.get("river"), "road": props.get("road"), "station": props["station"]})

    def _nearest(self, latitude: float, longitude: float) -> str:
        return min(self.stations.values(), key=lambda item: distance_km(latitude, longitude, item["latitude"], item["longitude"]))["id"]

    def at(self, clock: datetime, failed: Sequence[str | None] = (), placed: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
        """The sensors at the clock; each alarms when its station is above its highest measured before."""
        extra = [{"id": item["id"], "name": item["name"], "latitude": item["latitude"], "longitude": item["longitude"], "river": None,
                  "road": None, "station": self._nearest(item["latitude"], item["longitude"])} for item in placed] if self.stations else []
        sensors = []
        for index, node in enumerate([*self.nodes, *extra]):
            station = self.stations[node["station"]]
            item: dict[str, Any] = {**{key: node[key] for key in ("id", "name", "latitude", "longitude", "river", "road")},
                                    "kind": "level", "synthetic": True, "placed": index >= len(self.nodes),
                                    "station": station["name"], "station_kind": station["kind"]}
            if node["id"] in failed:
                sensors.append({**item, "status": "failed", "value": None, "percent": None, "from_record_cm": None, "confirms": False})
                continue
            value = latest(station, clock)
            record = station["earlier_max"]["value"]
            if self.rise:
                baseline = latest(station, self.start) if self.start else None
                factor = round(value / baseline, 1) if value is not None and baseline else None
                sensors.append({**item, "status": "ok", "value": value, "earlier_max": record, "percent": None, "from_record_cm": None,
                                "rise": factor, "rise_rule": self.rise, "confirms": factor is not None and factor >= self.rise})
                continue
            # A flow as a share of its record; a level in centimetres from it, as its share of the
            # height above the station's zero says little.
            percent = round_half_up(100 * value / record) if value is not None and station["kind"] == "flow" else None
            from_record_cm = round_half_up(value - record) if value is not None and station["kind"] == "level" else None
            sensors.append({**item, "status": "ok", "value": value, "earlier_max": record, "percent": percent,
                            "from_record_cm": from_record_cm, "confirms": value is not None and value > record})
        operating = [item for item in sensors if item["status"] == "ok"]
        return {"label": LABEL, "sensors": sensors, "confirms": sum(1 for item in operating if item["confirms"]), "operating": len(operating)}
