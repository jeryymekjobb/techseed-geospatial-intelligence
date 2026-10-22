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


def test_a_box_overpass_fails_on_is_split_and_the_answers_joined(monkeypatch) -> None:
    from urllib.error import HTTPError

    asked = []

    def overpass(query: str) -> dict:
        bbox = query.split("way[")[1].split("(")[1].split(")")[0]
        asked.append(bbox)
        south, west, north, east = (float(value) for value in bbox.split(","))
        if north - south > 1.0:  # the whole box: a gateway error, as Overpass gave Västernorrland
            raise HTTPError("https://overpass", 502, "Bad Gateway", None, None)
        # Way 1 touches every part (it is given whole each time); way 2 lies only in the north-east.
        elements = [{"type": "way", "id": 1, "tags": {"natural": "water"}, "geometry": []}]
        if south >= 63.0 and west >= 18.0:
            elements.append({"type": "way", "id": 2, "tags": {"landuse": "forest"}, "geometry": []})
        return {"version": 0.6, "osm3s": {"timestamp_osm_base": "2026-10-22T00:00:00Z"}, "elements": elements}

    monkeypatch.setattr(terrain, "fetch_query", overpass)
    payload = terrain.fetch((62.5, 17.2, 63.7, 18.9))
    assert len(asked) == 5 and asked[0] == "62.5,17.2,63.7,18.9"
    assert sorted((element["type"], element["id"]) for element in payload["elements"]) == [("way", 1), ("way", 2)]
    assert payload["osm3s"]["timestamp_osm_base"] == "2026-10-22T00:00:00Z"
    assert terrain.quarters((0.0, 0.0, 2.0, 4.0)) == [(0.0, 0.0, 1.0, 2.0), (0.0, 2.0, 1.0, 4.0), (1.0, 0.0, 2.0, 2.0), (1.0, 2.0, 2.0, 4.0)]


def test_a_refused_query_or_a_box_that_keeps_failing_is_not_split_for_ever(monkeypatch) -> None:
    from urllib.error import HTTPError

    import pytest

    asked = []

    def refused(query: str) -> dict:
        asked.append(query)
        raise HTTPError("https://overpass", 400, "Bad Request", None, None)

    monkeypatch.setattr(terrain, "fetch_query", refused)
    with pytest.raises(HTTPError):
        terrain.fetch((62.5, 17.2, 63.7, 18.9))
    assert len(asked) == 1  # a refused query is not split

    def silent(query: str) -> dict:
        asked.append(query)
        raise TimeoutError("The read operation timed out")

    asked.clear()
    monkeypatch.setattr(terrain, "fetch_query", silent)
    with pytest.raises(TimeoutError):
        terrain.fetch((62.5, 17.2, 63.7, 18.9), depth=2)
    assert len(asked) == 3  # the box, its first part and that part's first part, where the splitting stops
