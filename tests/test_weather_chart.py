"""Tests for tools/weather_chart.py: the weather chart's rain image and lightning."""

from __future__ import annotations

import base64
import io

import pytest

np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")

from tools import weather_chart as wc  # noqa: E402


def test_the_projection_is_meps_s_lambert_grid() -> None:
    # Points of MEPS's grid with their projection metres (read from a 2018 file).
    x, y = wc.lambert_xy(np.array([63.0]), np.array([15.0]))
    assert x[0] == pytest.approx(0.0, abs=1e-6) and y[0] == pytest.approx(0.0, abs=1e-6)
    x, y = wc.lambert_xy(np.array([61.95]), np.array([15.43]))
    assert x[0] == pytest.approx(22_500, abs=2_000) and y[0] == pytest.approx(-117_000, abs=2_000)


def test_rain_is_coloured_by_class_and_dry_ground_is_transparent() -> None:
    xs = np.arange(-500_000, 500_001, 20_000.0)
    ys = np.arange(-500_000, 500_001, 20_000.0)
    rain = np.zeros((len(ys), len(xs)))
    rain[25, 25] = 12.0  # at the projection's origin, 63 N 15 E
    image = Image.open(io.BytesIO(base64.b64decode(wc.rain_png(rain, xs, ys, (10.0, 60.0, 20.0, 66.0)).split(",", 1)[1])))
    pixels = np.asarray(image)
    assert image.size == (100, 120)
    centre = pixels[round((66 - 63) * 20), round((15 - 10) * 10)]
    assert tuple(centre) == wc.RAIN_CLASSES[-1][1] and pixels[0, 0, 3] == 0


def test_lightning_is_thinned_to_one_per_area_strongest_first() -> None:
    latitudes, longitudes = np.meshgrid(np.linspace(63, 61, 21), np.linspace(14, 18, 21), indexing="ij")
    index = np.zeros((21, 21))
    index[10, 10], index[10, 11], index[0, 0] = 0.9, 0.8, 0.7
    marks = wc.thunder_marks(index, latitudes, longitudes)
    assert [mark["index"] for mark in marks] == [0.9, 0.7]  # 0.8 is within THUNDER_SPACING_KM of 0.9
