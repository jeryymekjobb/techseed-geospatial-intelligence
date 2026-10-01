"""Tests for tools/fetch_osm_terrain.py with SYNTHETIC Overpass elements (not OSM data)."""

from __future__ import annotations

from tools import fetch_osm_terrain as terrain


def node(lon: float, lat: float) -> dict[str, float]:
    return {"lon": lon, "lat": lat}


def test_tags_map_to_terrain_classes_with_natural_first() -> None:
    assert terrain.terrain_class({"landuse": "forest"}) == ("skog", "landuse=forest")
    assert terrain.terrain_class({"natural": "wetland", "landuse": "forest"}) == ("myr", "natural=wetland")
    assert terrain.terrain_class({"landuse": "military"}) is None


def test_multipolygon_members_are_joined_into_rings_with_holes() -> None:
    element = {
        "type": "relation", "id": 7, "tags": {"natural": "wetland"},
        "members": [
            {"type": "way", "role": "outer", "geometry": [node(0, 0), node(4, 0), node(4, 4)]},
            {"type": "way", "role": "outer", "geometry": [node(0, 0), node(0, 4), node(4, 4)]},
            {"type": "way", "role": "inner", "geometry": [node(1, 1), node(2, 1), node(2, 2), node(1, 1)]},
        ],
    }

    geometry = terrain.element_geometry(element)

    assert geometry["type"] == "Polygon"
    outer, inner = geometry["coordinates"]
    assert outer[0] == outer[-1] and len(outer) == 5
    assert inner == [(1, 1), (2, 1), (2, 2), (1, 1)]


def test_open_ways_are_dropped_and_rings_stay_closed_after_simplification() -> None:
    assert terrain.element_geometry({"type": "way", "id": 1, "geometry": [node(0, 0), node(1, 0), node(1, 1)]}) is None
    ring = [(0.0, 0.0), (0.5, 0.00001), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]

    simplified = terrain.simplify(ring, 0.0001)

    assert simplified == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]


def test_geojson_carries_attribution_and_classes() -> None:
    payload = {"elements": [
        {"type": "way", "id": 3, "tags": {"landuse": "forest", "name": "Skog"},
         "geometry": [node(16.1, 59.9), node(16.2, 59.9), node(16.2, 60.0), node(16.1, 59.9)]},
        {"type": "way", "id": 4, "tags": {"highway": "track"}, "geometry": [node(16.1, 59.9), node(16.2, 59.9)]},
    ]}

    collection = terrain.to_geojson(payload, bbox=(59.75, 15.85, 60.08, 16.45), fetched_at="2026-10-01T13:07:00Z")

    assert collection["metadata"]["attribution"].startswith("© OpenStreetMap contributors, ODbL")
    assert [feature["properties"] for feature in collection["features"]] == [
        {"terrain": "skog", "osm_tag": "landuse=forest", "osm_id": "way/3", "name": "Skog"},
    ]
