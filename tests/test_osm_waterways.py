"""Tests for the rivers' and streams' names (tools/fetch_osm_waterways.py). SYNTHETIC ways round Ljungan."""

from __future__ import annotations

import pytest

from tools import fetch_osm_waterways as waterways
from tools import fetch_scenario


def way(name: str, kind: str, points: list[tuple[float, float]]) -> dict:
    return {"type": "way", "tags": {"name": name, "waterway": kind}, "geometry": [{"lat": lat, "lon": lon} for lat, lon in points]}


def test_ways_are_joined_where_their_ends_meet_in_either_direction() -> None:
    joined = waterways.chains([[(0, 0), (0, 1)], [(0, 2), (0, 1)], [(0, 3), (0, 2)], [(5, 5), (5, 6)]])
    assert joined == [[(0, 0), (0, 1), (0, 2), (0, 3)], [(5, 5), (5, 6)]]


def test_labels_go_in_the_middle_or_every_spacing() -> None:
    assert waterways.positions(4.0, 6.0) == [2.0]
    assert waterways.positions(25.0, 10.0) == [7.5, 17.5]


def test_the_text_runs_along_the_water_and_is_never_upside_down() -> None:
    east = [(62.3, 17.0), (62.3, 17.1)]
    north = [(62.3, 17.0), (62.4, 17.0)]
    assert waterways.angle(east, 2.5) == 0.0 and waterways.angle(east[::-1], 2.5) == 0.0
    assert abs(waterways.angle(north, 5.0)) == 90.0
    north_east = [(62.3, 17.0), (62.35, 17.1)]
    assert -90 < waterways.angle(north_east, 3.0) < 0  # rising to the right: turned anticlockwise on screen


def test_a_label_moves_along_its_chain_away_from_a_marked_point() -> None:
    chain = [(62.3, 17.0), (62.3, 17.2)]
    middle = waterways.length(chain) / 2
    moved = waterways.free_position(chain, middle, 6.0, [waterways.along(chain, middle)])
    assert waterways.km(waterways.along(chain, moved), waterways.along(chain, middle)) >= waterways.AVOID_KM


def test_named_waterways_get_labels_inside_the_map_area_and_short_ones_none() -> None:
    elements = [way("Ljungan", "river", [(62.36, 16.9), (62.36, 17.3)]), way("Kort bäck", "stream", [(62.3, 17.0), (62.3, 17.01)]),
                way("Utanför", "stream", [(61.0, 15.0), (61.0, 15.2)]), {"type": "way", "tags": {"waterway": "ditch", "name": "Dike"}}]
    found = waterways.labels(elements, [], (16.9, 62.15, 17.8, 62.62))
    assert [feature["properties"]["name"] for feature in found] == ["Ljungan", "Ljungan"]
    assert found[0]["properties"]["min_zoom"] == 9 and found[0]["properties"]["angle_deg"] == pytest.approx(0.0, abs=0.1)


def test_the_names_are_a_step_of_the_ljungan_scenario() -> None:
    plan = {step.key: step for step in fetch_scenario.steps("ljungan-aug2023")}
    assert not plan["osm-waterways"].optional and plan["osm-waterways"].account is None
