"""Tests for ERA5 wind over the sea (tools/fetch_era5_sea.py). SYNTHETIC values."""

from __future__ import annotations

import pytest

from tools import fetch_era5_sea as sea


def test_era5_is_interpolated_to_the_missing_grid_points_at_sea() -> None:
    latitudes = [62.75, 62.5, 62.25]  # north to south, as ERA5 has them
    longitudes = [17.5, 17.75, 18.0]
    field = [[0.0, 1.0, 2.0], [10.0, 11.0, 12.0], [20.0, 21.0, 22.0]]
    assert sea.bilinear(latitudes, longitudes, field, 62.5, 17.75) == pytest.approx(11.0)
    assert sea.bilinear(latitudes, longitudes, field, 62.6, 17.6) == pytest.approx(6.4)
    assert len(sea.grid_points(62.6, 16.9, 62.2, 17.8)) == 50  # the ERA5-Land grid of the area
