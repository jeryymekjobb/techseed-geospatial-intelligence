"""Tests for tools/fetch_osm_targets.py with SYNTHETIC Overpass elements (not OSM data)."""

from __future__ import annotations

from tools import fetch_osm_targets as targets


def test_places_buildings_roads_and_railways_are_classified() -> None:
    payload = {"elements": [
        {"type": "node", "id": 1, "lat": 59.9, "lon": 16.2, "tags": {"place": "village", "name": "By"}},
        {"type": "way", "id": 2, "center": {"lat": 59.91, "lon": 16.21}, "tags": {"building": "house"}},
        {"type": "way", "id": 3, "tags": {"highway": "secondary", "ref": "68"},
         "geometry": [{"lat": 59.9, "lon": 16.2}, {"lat": 59.95, "lon": 16.25}]},
        {"type": "way", "id": 4, "tags": {"railway": "rail"}, "geometry": [{"lat": 59.9, "lon": 16.1}, {"lat": 59.9, "lon": 16.3}]},
        {"type": "way", "id": 5, "tags": {"highway": "secondary"}, "geometry": [{"lat": 59.9, "lon": 16.1}]},
    ]}

    collection = targets.to_geojson(payload, bbox=(59.75, 15.85, 60.08, 16.45), fetched_at="2026-10-01T15:00:00Z")

    assert [feature["properties"]["kind"] for feature in collection["features"]] == ["place", "building", "road", "railway"]
    assert collection["features"][0]["properties"]["name"] == "By"
    assert collection["features"][2]["properties"]["ref"] == "68"
    assert collection["metadata"]["attribution"].startswith("© OpenStreetMap contributors")
    assert "place" in targets.overpass_query(59.75, 15.85, 60.08, 16.45) and "out center" in targets.overpass_query(1, 2, 3, 4)
