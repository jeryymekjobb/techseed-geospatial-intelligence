#!/usr/bin/env python3
"""Fetch OpenStreetMap land cover for one area as a classified GeoJSON layer.

Queries the Overpass API once for land-use and natural areas inside a
latitude/longitude box, joins multipolygon members into rings, maps OSM tags to
a few terrain classes and writes a GeoJSON FeatureCollection with source,
licence and fetch time. OSM shows the current state, not a historical one.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator; one-off terrain extract)"
ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0, https://www.openstreetmap.org/copyright"

# (tag, value) -> terrain class shown in the GUI. The first matching tag wins.
TERRAIN_CLASSES: dict[tuple[str, str], str] = {
    ("natural", "water"): "vatten",
    ("natural", "wetland"): "myr",
    ("landuse", "forest"): "skog",
    ("natural", "wood"): "skog",
    ("natural", "scrub"): "buskmark",
    ("natural", "heath"): "hed",
    ("natural", "grassland"): "öppen mark",
    ("landuse", "meadow"): "öppen mark",
    ("landuse", "grass"): "öppen mark",
    ("landuse", "farmland"): "åker",
    ("natural", "bare_rock"): "berg i dagen",
    ("landuse", "residential"): "bebyggelse",
    ("landuse", "industrial"): "industri",
    ("landuse", "commercial"): "bebyggelse",
    ("landuse", "quarry"): "täkt",
}
_TAG_ORDER = ("natural", "landuse")


def overpass_query(south: float, west: float, north: float, east: float) -> str:
    bbox = f"{south},{west},{north},{east}"
    selectors = "".join(
        f'way["{tag}"="{value}"]({bbox});relation["{tag}"="{value}"]["type"="multipolygon"]({bbox});'
        for tag, value in TERRAIN_CLASSES
    )
    return f"[out:json][timeout:180];({selectors});out geom;"


def terrain_class(tags: dict[str, str]) -> tuple[str, str] | None:
    for tag in _TAG_ORDER:
        value = tags.get(tag)
        if value and (tag, value) in TERRAIN_CLASSES:
            return TERRAIN_CLASSES[(tag, value)], f"{tag}={value}"
    return None


def _point(node: dict[str, float]) -> tuple[float, float]:
    return (round(node["lon"], 5), round(node["lat"], 5))


def simplify(ring: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker in degrees; a closed ring stays closed with at least four points."""
    if tolerance <= 0 or len(ring) <= 4:
        return ring

    def distance(point, start, end) -> float:
        (x, y), (x1, y1), (x2, y2) = point, start, end
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5

    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    # The farthest point from the first splits the closed ring into two open lines.
    far = max(range(1, len(ring) - 1), key=lambda index: distance(ring[index], ring[0], ring[0]))
    keep[far] = True
    stack = [(0, far), (far, len(ring) - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        index = max(range(first + 1, last), key=lambda item: distance(ring[item], ring[first], ring[last]))
        if distance(ring[index], ring[first], ring[last]) > tolerance:
            keep[index] = True
            stack.extend([(first, index), (index, last)])
    result = [point for point, kept in zip(ring, keep) if kept]
    return result if len(result) >= 4 else ring


def join_rings(segments: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Join way segments that share end points into closed rings; open leftovers are dropped."""
    pending = [list(segment) for segment in segments if len(segment) >= 2]
    rings: list[list[tuple[float, float]]] = []
    while pending:
        ring = pending.pop(0)
        extended = True
        while ring[0] != ring[-1] and extended:
            extended = False
            for index, segment in enumerate(pending):
                if segment[0] == ring[-1]:
                    ring.extend(segment[1:])
                elif segment[-1] == ring[-1]:
                    ring.extend(reversed(segment[:-1]))
                elif segment[-1] == ring[0]:
                    ring[:0] = segment[:-1]
                elif segment[0] == ring[0]:
                    ring[:0] = list(reversed(segment[1:]))
                else:
                    continue
                pending.pop(index)
                extended = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
    return rings


def element_geometry(element: dict[str, Any], tolerance: float = 0.0) -> dict[str, Any] | None:
    if element["type"] == "way":
        ring = [_point(node) for node in element.get("geometry", [])]
        if len(ring) >= 4 and ring[0] == ring[-1]:
            return {"type": "Polygon", "coordinates": [simplify(ring, tolerance)]}
        return None
    outers = [[_point(node) for node in member.get("geometry", [])]
              for member in element.get("members", []) if member.get("type") == "way" and member.get("role") != "inner"]
    inners = [[_point(node) for node in member.get("geometry", [])]
              for member in element.get("members", []) if member.get("type") == "way" and member.get("role") == "inner"]
    outer_rings = [simplify(ring, tolerance) for ring in join_rings(outers)]
    inner_rings = [simplify(ring, tolerance) for ring in join_rings(inners)]
    if not outer_rings:
        return None
    # Holes are kept with the single outer ring; with several outers they are left out
    # rather than assigned to the wrong polygon.
    if len(outer_rings) == 1:
        return {"type": "Polygon", "coordinates": [outer_rings[0], *inner_rings]}
    return {"type": "MultiPolygon", "coordinates": [[ring] for ring in outer_rings]}


def to_geojson(
    payload: dict[str, Any], *, bbox: tuple[float, float, float, float], fetched_at: str, tolerance: float = 0.0
) -> dict[str, Any]:
    features = []
    for element in payload.get("elements", []):
        classified = terrain_class(element.get("tags", {}))
        geometry = element_geometry(element, tolerance) if classified else None
        if geometry is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "terrain": classified[0],
                "osm_tag": classified[1],
                "osm_id": f"{element['type']}/{element['id']}",
                **({"name": element["tags"]["name"]} if element.get("tags", {}).get("name") else {}),
            },
        })
    south, west, north, east = bbox
    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "OpenStreetMap via Overpass API",
            "attribution": ATTRIBUTION,
            "fetched_at_utc": fetched_at,
            "bbox_wgs84": {"south": south, "west": west, "north": north, "east": east},
            "simplification_tolerance_degrees": tolerance,
            "note": "Current OSM land cover, not the state in 2014.",
        },
        "features": features,
    }


def simplify_collection(collection: dict[str, Any], tolerance: float) -> dict[str, Any]:
    """Simplify every ring of an earlier output; coordinates are lists after JSON loading."""
    for feature in collection["features"]:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        simplified = [[simplify([tuple(point) for point in ring], tolerance) for ring in polygon] for polygon in polygons]
        geometry["coordinates"] = simplified[0] if geometry["type"] == "Polygon" else simplified
    collection["metadata"]["simplification_tolerance_degrees"] = tolerance
    return collection


def fetch(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    return fetch_query(overpass_query(*bbox))


def fetch_query(query: str) -> dict[str, Any]:
    body = urlencode({"data": query}).encode("utf-8")
    request = Request(OVERPASS_URL, data=body, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=240) as response:
        return json.load(response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--bbox", required=True, help="south,west,north,east in WGS 84")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=0.0001, help="simplification in degrees (about 6-11 m)")
    parser.add_argument("--save-raw", type=Path, help="also write the Overpass response here")
    parser.add_argument("--from-raw", type=Path, help="convert a saved Overpass response instead of fetching")
    parser.add_argument("--from-geojson", type=Path, help="re-simplify an earlier output of this tool instead of fetching")
    args = parser.parse_args(argv)
    bbox = tuple(float(value) for value in args.bbox.split(","))
    if len(bbox) != 4:
        parser.error("bbox is south,west,north,east")
    if args.from_geojson:
        collection = json.loads(args.from_geojson.read_text(encoding="utf-8"))
        collection = simplify_collection(collection, args.tolerance)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{len(collection['features'])} features -> {args.out}")
        return 0
    if args.from_raw:
        payload = json.loads(args.from_raw.read_text(encoding="utf-8"))
        fetched_at = payload.get("osm3s", {}).get("timestamp_osm_base") or "unknown"
    else:
        payload = fetch(bbox)  # type: ignore[arg-type]
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if args.save_raw:
            args.save_raw.write_text(json.dumps(payload), encoding="utf-8")
    collection = to_geojson(payload, bbox=bbox, fetched_at=fetched_at, tolerance=args.tolerance)  # type: ignore[arg-type]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(collection['features'])} features -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
