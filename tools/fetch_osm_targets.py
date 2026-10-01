#!/usr/bin/env python3
"""Fetch OpenStreetMap places, buildings, roads and railways for one area.

These are the targets for which the fire-spread analysis estimates when a fire
front would reach them. One Overpass request; buildings become centre points,
roads and railways keep their line geometry. Writes GeoJSON with source and
licence. OSM shows the current state, not 2014.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.fetch_osm_terrain import ATTRIBUTION, fetch_query

PLACE_TYPES = ("town", "village", "hamlet", "isolated_dwelling", "locality", "farm", "neighbourhood")
ROAD_TYPES = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified")


def overpass_query(south: float, west: float, north: float, east: float) -> str:
    bbox = f"{south},{west},{north},{east}"
    places = "|".join(PLACE_TYPES)
    roads = "|".join(ROAD_TYPES)
    return (
        "[out:json][timeout:180];("
        f'node["place"~"^({places})$"]({bbox});'
        f'way["highway"~"^({roads})$"]({bbox});'
        f'way["railway"="rail"]({bbox});'
        ");out geom;"
        f'(way["building"]({bbox}););out center;'
    )


def to_geojson(payload: dict[str, Any], *, bbox: tuple[float, float, float, float], fetched_at: str) -> dict[str, Any]:
    features = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        osm_id = f"{element['type']}/{element['id']}"
        name = tags.get("name")
        if element["type"] == "node" and "place" in tags:
            kind, geometry = "place", {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
            detail = tags["place"]
        elif element["type"] == "way" and "building" in tags and "center" in element:
            centre = element["center"]
            kind, geometry = "building", {"type": "Point", "coordinates": [round(centre["lon"], 6), round(centre["lat"], 6)]}
            detail = tags["building"]
        elif element["type"] == "way" and ("highway" in tags or tags.get("railway") == "rail"):
            line = [[round(node["lon"], 6), round(node["lat"], 6)] for node in element.get("geometry", [])]
            if len(line) < 2:
                continue
            kind = "railway" if tags.get("railway") == "rail" else "road"
            geometry = {"type": "LineString", "coordinates": line}
            detail = tags.get("highway", "rail")
        else:
            continue
        properties = {"kind": kind, "type": detail, "osm_id": osm_id}
        if name:
            properties["name"] = name
        if tags.get("ref"):
            properties["ref"] = tags["ref"]
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})
    south, west, north, east = bbox
    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "OpenStreetMap via Overpass API",
            "attribution": ATTRIBUTION,
            "fetched_at_utc": fetched_at,
            "bbox_wgs84": {"south": south, "west": west, "north": north, "east": east},
            "note": "Current OSM state, not 2014.",
        },
        "features": features,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--bbox", required=True, help="south,west,north,east in WGS 84")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--save-raw", type=Path)
    parser.add_argument("--from-raw", type=Path)
    args = parser.parse_args(argv)
    bbox = tuple(float(value) for value in args.bbox.split(","))
    if args.from_raw:
        payload = json.loads(args.from_raw.read_text(encoding="utf-8"))
        fetched_at = payload.get("osm3s", {}).get("timestamp_osm_base") or "unknown"
    else:
        payload = fetch_query(overpass_query(*bbox))  # type: ignore[arg-type]
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if args.save_raw:
            args.save_raw.write_text(json.dumps(payload), encoding="utf-8")
    collection = to_geojson(payload, bbox=bbox, fetched_at=fetched_at)  # type: ignore[arg-type]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    kinds: dict[str, int] = {}
    for feature in collection["features"]:
        kinds[feature["properties"]["kind"]] = kinds.get(feature["properties"]["kind"], 0) + 1
    print(f"{kinds} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
