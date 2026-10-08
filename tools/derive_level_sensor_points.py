#!/usr/bin/env python3
"""Choose the points of a river flood's synthetic level sensors from PostGIS.

There were no TechSeed sensors along Skåne's rivers in 2024. To show how ground sensors would
confirm a flood, the scenario places synthetic level sensors (app/backend/level_sensors.py)
where larger OSM roads cross MCF's 100-year flow of a watercourse that one of SMHI's stations
measures (the scenario's LEVEL_SENSOR_RIVERS). The tool asks the scenario's PostGIS database
(tools/load_postgis.py) for those crossings, keeps at most MAX_POINTS at least SPACING_KM apart,
taking the watercourses in turn and the larger roads first, gives each the nearest of its
watercourse's stations and writes the scenario's LEVEL_SENSOR_FILE.

    TECHSEED_SCENARIO=skane2024 .venv/bin/python -m tools.derive_level_sensor_points
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from app.backend import hydro, scenario
from app.backend.flood_sensors import distance_km
from tools.load_postgis import run_psql

MAX_POINTS = 8
SPACING_KM = 2.0
ROAD_RANK = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4}
CROSSINGS = """SELECT coalesce(json_agg(r), '[]'::json) FROM (
  SELECT t.type, t.name, round(ST_Y(p)::numeric, 5) AS latitude, round(ST_X(p)::numeric, 5) AS longitude
  FROM targets t JOIN (SELECT ST_Union(geom) AS geom FROM flood_areas WHERE kind = '100ar' AND name LIKE {pattern}) a
    ON ST_Intersects(t.geom, a.geom),
    LATERAL ST_PointOnSurface(ST_Intersection(t.geom, a.geom)) AS p
  WHERE t.kind = 'road' AND t.type IN ({types})
) r;"""


def crossings(river: str) -> list[dict[str, Any]]:
    pattern = "'" + river.replace("'", "''") + " (%'"
    types = ", ".join(f"'{name}'" for name in ROAD_RANK)
    return json.loads(run_psql(CROSSINGS.format(pattern=pattern, types=types)).strip())


def choose(by_river: dict[str, list[dict[str, Any]]], count: int = MAX_POINTS, spacing_km: float = SPACING_KM) -> list[dict[str, Any]]:
    """At most `count` crossings `spacing_km` apart, the watercourses in turn, named and larger roads first."""
    queues = {river: sorted(items, key=lambda item: (item["name"] is None, ROAD_RANK[item["type"]], item["latitude"], item["longitude"]))
              for river, items in by_river.items()}
    chosen: list[dict[str, Any]] = []
    while len(chosen) < count and any(queues.values()):
        for river, queue in queues.items():
            while queue:
                item = queue.pop(0)
                if all(distance_km(item["latitude"], item["longitude"], other["latitude"], other["longitude"]) >= spacing_km for other in chosen):
                    chosen.append({**item, "river": river})
                    break
            if len(chosen) == count:
                break
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.parse_args(argv)
    data = hydro.stations()
    if not scenario.LEVEL_SENSOR_RIVERS or scenario.LEVEL_SENSOR_FILE is None or data is None:
        parser.exit(1, f"derive_level_sensor_points: the scenario {scenario.NAME} has no level sensors or no SMHI stations\n")
    stations = {station["id"]: station for station in data["stations"]}
    points = choose({river: crossings(river) for river in scenario.LEVEL_SENSOR_RIVERS})
    features = []
    for index, item in enumerate(points, start=1):
        station = min((stations[key] for key in scenario.LEVEL_SENSOR_RIVERS[item["river"]]),
                      key=lambda entry: distance_km(item["latitude"], item["longitude"], entry["latitude"], entry["longitude"]))
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(item["longitude"]), float(item["latitude"])]},
                         "properties": {"id": f"ng-{index:02d}", "name": f"NG{index} {item['name'] or item['river']}", "river": item["river"],
                                        "road": item["name"], "road_type": item["type"], "station": station["id"]}})
        print(f"NG{index}: {item['name'] or item['type']} över {item['river']} ({item['latitude']}, {item['longitude']}) – {station['name']}")
    scenario.LEVEL_SENSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    scenario.LEVEL_SENSOR_FILE.write_text(json.dumps({
        "type": "FeatureCollection", "features": features,
        "source": "Vägar © OpenStreetMap contributors korsar MCF:s klimatanpassade 100-årsflöde; stationer SMHI öppna data",
        "note": "synthetic sensor points, chosen by tools/derive_level_sensor_points.py",
        "derived_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(features)} points -> {scenario.LEVEL_SENSOR_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
