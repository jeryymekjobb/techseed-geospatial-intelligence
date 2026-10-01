"""Tests for helpers in tools/fire_spread_analysis.py (SYNTHETIC geometry)."""

from __future__ import annotations

from tools import fire_spread_analysis as analysis


def square(size: float) -> list[tuple[float, float]]:
    return [(0.0, 0.0), (size, 0.0), (size, size), (0.0, size)]


def test_first_reaching_hour_finds_the_first_growing_front_within_reach() -> None:
    fronts = [square(1000.0 * hour) for hour in range(1, 25)]

    assert analysis.first_reaching_hour((5000.0, 5000.0), fronts) == 5
    assert analysis.first_reaching_hour((5700.0, 100.0), fronts) == 5  # within 750 m of the 5 km front
    assert analysis.first_reaching_hour((60000.0, 0.0), fronts) is None
    assert analysis.first_reaching_hour((1.0, 1.0), []) is None
