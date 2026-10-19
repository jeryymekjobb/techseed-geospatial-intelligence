#!/usr/bin/env python3
"""Place the scenario's synthetic overflow sensors at its reported damage, driven by SMHI's radar.

A cloudburst can fall between SMHI's gauges: in Kramfors on 15 August 2026 both hourly stations lay
outside the cell. Each of the scenario's ROUTE_IMPACTS with a "site" (a road or building the reports
say was flooded, at an approximate place) gets a synthetic overflow sensor, and this tool records
the rain SMHI's radar estimates fell there in each hour of the playback (as
tools/derive_route_exposure.py: every 5-minute image, Z = 200 R^1.6, about 2 km pixels).
flood_sensors.py runs that rain through its reservoir instead of the nearest gauge's. It is the
radar's estimate of the rain, not a measurement at the place, and the sensors are synthetic.

    TECHSEED_SCENARIO=kramfors2026 .venv/bin/python -m tools.derive_radar_sensor_points

SMHI open data is licensed under Creative Commons Attribution 4.0 SE. Numpy and Pillow from the .venv.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.backend import scenario
from tools.derive_route_exposure import STEP_MINUTES, hourly_sums, radar_frames


def sites(impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The impacts with a place, in their order."""
    return [item for item in impacts if item.get("site")]


def points(impacts: list[dict[str, Any]], rain: np.ndarray, start: datetime) -> dict[str, Any]:
    """The sensors as a GeoJSON FeatureCollection, numbered in the order of the impacts; `rain` is the
    millimetres of each hour (rows) at each site (columns)."""
    features = []
    for index, item in enumerate(sites(impacts)):
        number = index + 1
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [item["longitude"], item["latitude"]]},
                         "properties": {"id": f"dv-{number:02d}", "name": f"DV{number} {item['site']}", "site": item["site"],
                                        "rain_mm": [round(float(value), 1) for value in rain[:, index]]}})
    return {"type": "FeatureCollection", "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "hours": int(rain.shape[0]),
            "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "processing": (f"SMHI's radar composite every {STEP_MINUTES} minutes at each reported site, Z = 200 R^1.6, "
                           "summed by the hour from the playback's start; sites approximate"),
            "attribution": "SMHI öppna data, väderradar (CC BY 4.0 SE), regn beräknat; platser enligt lokala medier, ungefärliga",
            "features": features}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.RADAR_SENSOR_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"derive_radar_sensor_points: the scenario {scenario.NAME} has no RADAR_SENSOR_FILE\n")
    chosen = sites(scenario.ROUTE_IMPACTS)
    if not chosen:
        parser.exit(1, f"derive_radar_sensor_points: the scenario {scenario.NAME} has no ROUTE_IMPACTS with a site\n")
    start, end = scenario.PLAYBACK_START, scenario.PLAYBACK_END
    hours = int((end - start).total_seconds() // 3600)
    frames = radar_frames(np.array([item["latitude"] for item in chosen]), np.array([item["longitude"] for item in chosen]), start, end)
    sums = hourly_sums(frames, start, hours)
    rain = np.diff(sums, axis=0, prepend=np.zeros((1, sums.shape[1])))
    collection = points(scenario.ROUTE_IMPACTS, rain, start)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    for feature in collection["features"]:
        props = feature["properties"]
        print(f"{props['name']}: {sum(props['rain_mm']):.1f} mm, most {max(props['rain_mm']):.1f} mm in an hour")
    print(f"{len(collection['features'])} sensors from {len(frames)} radar images -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
