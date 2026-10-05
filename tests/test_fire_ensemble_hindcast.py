"""Tests for the geometry of the filter hindcast (tools/fire_ensemble_hindcast.py)."""

from __future__ import annotations

import pytest

from tools import fire_spread as fs
from tools.fire_ensemble_hindcast import quantile_front, ray_distance, reach_hours


def square(half: float) -> list[fs.Point]:
    return [(-half, -half), (half, -half), (half, half), (-half, half)]


def test_a_ray_from_the_centre_meets_the_square_at_its_edge() -> None:
    assert ray_distance((0.0, 0.0), 0.0, square(10.0)) == pytest.approx(10.0)
    assert ray_distance((0.0, 0.0), 45.0, square(10.0)) == pytest.approx(10.0 * 2 ** 0.5)
    assert ray_distance((0.0, 0.0), 90.0, [(0.0, 0.0), (1.0, 1.0)]) == 0.0  # degenerate


def test_the_quantile_front_lies_between_the_members() -> None:
    fronts = [square(10.0), square(20.0), square(30.0), square(40.0)]
    reached_by_all = quantile_front((0.0, 0.0), fronts, 1.0)
    reached_by_half = quantile_front((0.0, 0.0), fronts, 0.5)
    reached_by_one = quantile_front((0.0, 0.0), fronts, 0.25)
    assert reached_by_all[0] == pytest.approx((0.0, 10.0))  # the ray towards north
    assert reached_by_half[0] == pytest.approx((0.0, 30.0))
    assert reached_by_one[0] == pytest.approx((0.0, 40.0))


def test_the_reach_hour_is_the_first_front_that_contains_the_point() -> None:
    fronts = [square(float(size)) for size in (1, 2, 3, 4, 5)]
    assert reach_hours((2.5, 0.0), fronts) == 3
    assert reach_hours((0.0, 0.0), fronts) == 1
    assert reach_hours((9.0, 0.0), fronts) is None
