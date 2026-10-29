#!/usr/bin/env python3
"""Fetch the named rivers, streams and canals of the map area from OpenStreetMap and place their names.

Asks Overpass (as tools/fetch_osm_terrain.py, with its waits when Overpass is busy) for the named
waterways in MAP_BBOX, joins each name's ways into chains where their ends meet and places a label
along each chain: one in the middle of a chain shorter than its kind's spacing (SPACING_KM), else one
every spacing, inside MAP_BBOX. A label is moved along its chain, at most half a spacing, away from what the screens
mark (flow stations, sensors and stormwater points: AVOID_KM), and carries the chain's direction there,
so the screens can write the name along the water, beside it rather than on it. Chains shorter than
MIN_KM get no label. It writes WATERWAY_LABELS_FILE, a GeoJSON of label points.

    TECHSEED_SCENARIO=ljungan-aug2023 .venv/bin/python -m tools.fetch_osm_waterways

OSM shows the current state, not that of the scenario's year.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.backend import scenario
from tools.fetch_osm_terrain import ATTRIBUTION, fetch_query

KINDS = ("river", "canal", "stream")
# Between two labels of the same chain, and the zoom each kind's labels show from.
SPACING_KM = {"river": 10.0, "canal": 8.0, "stream": 6.0}
MIN_ZOOM = {"river": 9, "canal": 11, "stream": 12}
MIN_KM = 1.0
# A label keeps this far from the points the screens mark, where its chain allows.
AVOID_KM = 0.8
# The direction is taken over this length of the chain round the label.
DIRECTION_KM = 0.6


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return (f'[out:json][timeout:180];way["waterway"~"^({"|".join(KINDS)})$"]["name"]'
            f"({south},{west},{north},{east});out tags geom;")


def chains(ways: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """The ways ([lat, lon] lists) joined end to end where their ends meet, in either direction."""
    pending = [list(way) for way in ways if len(way) >= 2]
    result = []
    while pending:
        chain = pending.pop(0)
        grown = True
        while grown:
            grown = False
            for index, way in enumerate(pending):
                if way[0] == chain[-1]:
                    chain += way[1:]
                elif way[-1] == chain[-1]:
                    chain += way[-2::-1]
                elif way[-1] == chain[0]:
                    chain = way[:-1] + chain
                elif way[0] == chain[0]:
                    chain = way[:0:-1] + chain
                else:
                    continue
                pending.pop(index)
                grown = True
                break
        result.append(chain)
    return result


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 111.2, (a[1] - b[1]) * 111.2 * math.cos(math.radians(a[0])))


def along(chain: list[tuple[float, float]], distance: float) -> tuple[float, float]:
    """The point this far along the chain."""
    walked = 0.0
    for a, b in zip(chain, chain[1:]):
        step = km(a, b)
        if walked + step >= distance and step > 0:
            share = (distance - walked) / step
            return a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share
        walked += step
    return chain[-1]


def length(chain: list[tuple[float, float]]) -> float:
    return sum(km(a, b) for a, b in zip(chain, chain[1:]))


def angle(chain: list[tuple[float, float]], distance: float) -> float:
    """The chain's direction at a distance as the clockwise turn from east of text written along it
    (CSS's rotate), kept between -90 and 90 degrees so the text is never upside down."""
    total = length(chain)
    a = along(chain, max(0.0, distance - DIRECTION_KM / 2))
    b = along(chain, min(total, distance + DIRECTION_KM / 2))
    east = (b[1] - a[1]) * math.cos(math.radians(a[0]))
    north = b[0] - a[0]
    degrees = -math.degrees(math.atan2(north, east))
    if degrees > 90:
        degrees -= 180
    elif degrees <= -90:
        degrees += 180
    return round(degrees, 1)


def positions(total: float, spacing: float) -> list[float]:
    """Where along a chain its labels go: the middle, or every spacing from half a spacing in."""
    if total < spacing:
        return [total / 2]
    count = int(total // spacing)
    first = (total - (count - 1) * spacing) / 2
    return [first + index * spacing for index in range(count)]


def free_position(chain: list[tuple[float, float]], wanted: float, spacing: float, avoid: list[tuple[float, float]]) -> float:
    """The position nearest the wanted one, within half a spacing, that keeps AVOID_KM from the marked points."""
    total = length(chain)
    for offset in [step * 0.2 for step in range(int(spacing / 0.4) + 1)]:
        for distance in (wanted + offset, wanted - offset):
            if 0 <= distance <= total and all(km(along(chain, distance), point) >= AVOID_KM for point in avoid):
                return distance
    return wanted


def labels(elements: list[dict[str, Any]], avoid: list[tuple[float, float]],
           bbox: tuple[float, float, float, float] | None = None) -> list[dict[str, Any]]:
    """The label points; Overpass gives whole ways, so labels outside bbox are left out."""
    by_name: dict[tuple[str, str], list[list[tuple[float, float]]]] = {}
    for element in elements:
        tags = element.get("tags", {})
        if element.get("type") != "way" or tags.get("waterway") not in KINDS or not tags.get("name") or not element.get("geometry"):
            continue
        by_name.setdefault((tags["name"], tags["waterway"]), []).append([(point["lat"], point["lon"]) for point in element["geometry"]])
    features = []
    for (name, kind), ways in sorted(by_name.items()):
        for chain in chains(ways):
            total = length(chain)
            if total < MIN_KM:
                continue
            for wanted in positions(total, SPACING_KM[kind]):
                distance = free_position(chain, wanted, SPACING_KM[kind], avoid)
                lat, lon = along(chain, distance)
                if bbox and not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
                    continue
                features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
                                 "properties": {"name": name, "kind": kind, "angle_deg": angle(chain, distance),
                                                "min_zoom": MIN_ZOOM[kind]}})
    return features


def marked_points() -> list[tuple[float, float]]:
    """What the screens mark that a label should not cover: flow stations, level sensors, stormwater points."""
    points = []
    hydro = Path(scenario.HYDRO_DIR) / "stations.json" if scenario.HYDRO_DIR else None
    if hydro and hydro.is_file():
        points += [(item["latitude"], item["longitude"]) for item in json.loads(hydro.read_text(encoding="utf-8"))["stations"]]
    for path in (scenario.LEVEL_SENSOR_FILE, Path(scenario.MUNICIPAL_DIR) / "critical-stormwater.geojson" if scenario.MUNICIPAL_DIR else None):
        if path and Path(path).is_file():
            for feature in json.loads(Path(path).read_text(encoding="utf-8"))["features"]:
                if feature["geometry"] and feature["geometry"]["type"] == "Point":
                    lon, lat = feature["geometry"]["coordinates"][:2]
                    points.append((lat, lon))
    return points


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.WATERWAY_LABELS_FILE)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_osm_waterways: the scenario {scenario.NAME} has no waterway labels\n")
    elements = fetch_query(overpass_query(scenario.MAP_BBOX))["elements"]
    features = labels(elements, marked_points(), scenario.MAP_BBOX)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"type": "FeatureCollection", "attribution": ATTRIBUTION,
                                    "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "features": features}, ensure_ascii=False), encoding="utf-8")
    names = sorted({feature["properties"]["name"] for feature in features})
    print(f"fetch_osm_waterways: {len(features)} labels for {len(names)} waterways to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
