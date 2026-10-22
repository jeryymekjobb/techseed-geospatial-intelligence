#!/usr/bin/env python3
"""Place the scenario's synthetic level sensors at its documented road and railway damage.

Each of the scenario's ROUTE_IMPACTS with a "site" (a road or railway the report says was
damaged, at an approximate place) gets a synthetic level sensor, which follows the nearest of
the scenario's SMHI flow stations (hydro.py) with a record, and so does each of its
LEVEL_SENSOR_SITES (places chosen where the reports name too few). The points go to LEVEL_SENSOR_FILE,
as tools/derive_level_sensor_points.py writes them for Skåne, and level_sensors.py drives them.

    TECHSEED_SCENARIO=vasternorrland2025 .venv/bin/python -m tools.derive_impact_sensor_points
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.backend import hydro, scenario
from app.backend.flood_sensors import distance_km


def points(impacts: list[dict[str, Any]], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """The sensors as a GeoJSON FeatureCollection, numbered in the order of the impacts."""
    stations = [station for station in stations if station.get("earlier_max")]
    features = []
    for item in impacts:
        if not item.get("site"):
            continue
        nearest = min(stations, key=lambda station: distance_km(item["latitude"], item["longitude"], station["latitude"], station["longitude"]))
        number = len(features) + 1
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [item["longitude"], item["latitude"]]},
                         "properties": {"id": f"ng-{number:02d}", "name": f"NG{number} {item['site']}", "river": None,
                                        "road": item["site"], "station": nearest["id"]}})
    return {"type": "FeatureCollection", "features": features}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.LEVEL_SENSOR_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    data = hydro.stations()
    if args.out is None or data is None or not (scenario.ROUTE_IMPACTS or scenario.LEVEL_SENSOR_SITES):
        parser.exit(1, f"derive_impact_sensor_points: the scenario {scenario.NAME} has no damage sites, flows or LEVEL_SENSOR_FILE\n")
    collection = points([*scenario.ROUTE_IMPACTS, *scenario.LEVEL_SENSOR_SITES], data["stations"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(collection, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for feature in collection["features"]:
        print(f"{feature['properties']['name']}: {feature['properties']['station']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
