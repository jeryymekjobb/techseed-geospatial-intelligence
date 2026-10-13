"""Tests for tools/isobars.py with synthetic pressure fields."""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from tools import isobars  # noqa: E402


def grid(rows: int = 40, cols: int = 40) -> tuple:
    latitudes, longitudes = np.meshgrid(np.linspace(70, 55, rows), np.linspace(5, 30, cols), indexing="ij")
    return latitudes, longitudes


def test_a_low_gives_closed_rings_every_hpa_and_an_l() -> None:
    latitudes, longitudes = grid()
    y, x = np.mgrid[0:40, 0:40]
    pressure = 1000 + 0.15 * ((y - 20) ** 2 + (x - 20) ** 2)  # a low of 1000 hPa in the middle
    result = isobars.isobars(pressure, latitudes, longitudes)
    levels = sorted({line["hpa"] for line in result["lines"]})
    assert levels[:3] == [1001, 1002, 1003] and levels == list(range(1001, levels[-1] + 1))
    ring = next(line for line in result["lines"] if line["hpa"] == 1004)
    assert ring["coords"][0] == pytest.approx(ring["coords"][-1], abs=1e-3)  # closed
    assert [(item["kind"], item["hpa"]) for item in result["centres"]] == [("L", 1000)]
    centre = result["centres"][0]
    assert centre["latitude"] == pytest.approx(62.3, abs=0.5) and centre["longitude"] == pytest.approx(17.8, abs=0.5)


def test_a_gradient_gives_straight_lines_and_no_centres() -> None:
    latitudes, longitudes = grid()
    pressure = np.tile(np.linspace(1024, 1008, 40), (40, 1))  # falling to the east
    result = isobars.isobars(pressure, latitudes, longitudes)
    assert sorted({line["hpa"] for line in result["lines"]}) == list(range(1009, 1024))
    assert all(len(line["coords"]) >= 30 for line in result["lines"]) and result["centres"] == []


def test_pieces_join_into_one_line() -> None:
    pieces = [((0.0, 0.5), (0.5, 1.0)), ((1.5, 2.0), (0.5, 1.0)), ((1.5, 2.0), (2.0, 2.5))]
    assert isobars.join(pieces) == [[(0.0, 0.5), (0.5, 1.0), (1.5, 2.0), (2.0, 2.5)]]
