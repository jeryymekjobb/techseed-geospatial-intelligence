"""Simulated level sensors where larger roads cross MCF's 100-year flow, as in the scenarios
(app/backend/level_sensors.py): the points of tools/derive_level_sensor_points.py, each following
the live flow of its SMHI station.

There are no such level sensors along the rivers. To show how ground sensors would confirm a high flow,
each point gets a simulated sensor driven by its station's latest 15-minute flow: it alarms, as in
the scenarios, when that flow is above the highest daily flow in SMHI's archive (the monitoring's
record, sources.flow_statistics), and gives the flow as a share of it. Every value is simulated and
the screens say so; a sensor whose station gave no flow says that instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LABEL = "Simulerade nivågivare – följer SMHI:s uppmätta flöde, inte mätningar"


def load(points_file: Path | None, stations: set[str] | None = None) -> list[dict[str, Any]]:
    """The sensors' points, or none when the scenarios' file is not there (it is unversioned); with
    `stations`, only those following a station the area monitors live (a scenario's archived or
    modelled stations give nothing to follow)."""
    if points_file is None or not points_file.is_file():
        return []
    points = []
    for feature in json.loads(points_file.read_text(encoding="utf-8"))["features"]:
        props = feature["properties"]
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        # The scenarios name a station with SMHI's parameter (1273:2), the monitoring without it.
        station = props["station"].split(":", 1)[0]
        if stations is not None and station not in stations:
            continue
        points.append({"id": props["id"], "name": props["name"], "road": props.get("road"), "river": props.get("river"),
                       "station": station, "latitude": latitude, "longitude": longitude})
    return points


def readings(points: list[dict[str, Any]], flows: list[dict[str, Any]], limits: dict[str, Any]) -> list[dict[str, Any]]:
    """Each sensor with its station's latest flow, its share of the record and whether it alarms."""
    latest = {item["station"]: item for item in flows if item.get("readings")}
    found = []
    for point in points:
        flow = latest.get(point["station"])
        record = (limits.get(point["station"]) or {}).get("record")
        value = flow["readings"][-1]["value"] if flow else None
        found.append({**point, "kind": "level", "simulated": True, "station_name": flow["name"] if flow else point["station"],
                      "value": value, "time_utc": flow["readings"][-1]["time_utc"] if flow else None, "record": record,
                      "percent": round(100 * value / record) if value is not None and record else None,
                      "alarm": bool(value is not None and record and value > record)})
    return found
