"""Tests for tools/fire_spread.py. Weather and detections here are SYNTHETIC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools import fire_spread as fs

UTC = timezone.utc


def test_fwi_matches_the_van_wagner_and_pickett_reference_day() -> None:
    # Standard test: T 17 °C, RH 42 %, wind 25 km/h, no rain, April, from 85/6/15.
    ffmc = fs.ffmc_daily(85.0, 17.0, 42.0, 25.0, 0.0)
    dmc = fs.dmc_daily(6.0, 17.0, 42.0, 0.0, 4)
    dc = fs.dc_daily(15.0, 17.0, 0.0, 4)
    isi = fs.isi(ffmc, 25.0)
    bui = fs.bui(dmc, dc)

    assert [round(value, 1) for value in (ffmc, dmc, dc, isi, bui, fs.fwi(isi, bui))] == [87.7, 8.5, 19.0, 10.9, 8.5, 10.1]


def test_rain_wets_the_codes() -> None:
    assert fs.ffmc_daily(90.0, 15.0, 80.0, 10.0, 10.0) < 60.0
    assert fs.dmc_daily(40.0, 15.0, 80.0, 10.0, 8) < 40.0
    assert fs.dc_daily(400.0, 15.0, 20.0, 8) < 400.0


def test_rate_of_spread_rises_with_isi_and_bui() -> None:
    assert fs.rate_of_spread(10, 80) > fs.rate_of_spread(5, 80) > 0
    assert fs.rate_of_spread(10, 120) > fs.rate_of_spread(10, 40)
    assert fs.length_to_breadth(0) == 1.0 and fs.length_to_breadth(30) > 2.0


def test_hull_inside_and_distance() -> None:
    square = fs.convex_hull([(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)])

    assert len(square) == 4 and fs.polygon_area(square) == 100
    assert fs.inside_convex((5, 5), square) and not fs.inside_convex((15, 5), square)
    assert fs.distance_to_hull((15, 5), square) == 5 and fs.distance_to_hull((5, 5), square) == 0


def test_growth_goes_downwind() -> None:
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]

    grown = fs.grow(square, ros_m_per_h=1000.0, back_m_per_h=100.0, lb=2.0, towards_deg=0.0)

    ys = [y for _, y in grown]
    assert max(ys) > 1000 and min(ys) > -150  # far north, little south


def test_observed_advance_and_bearing() -> None:
    hull = fs.convex_hull([(0, 0), (1000, 0), (1000, 1000), (0, 1000)])

    advance, direction = fs.observed_advance(hull, [(500, 2000), (520, 2500), (500, 500)])

    assert advance >= 1000
    assert fs.angle_difference(direction, 0.0) < 10  # northwards
    assert fs.bearing(1, 0) == 90.0


def test_passes_group_detections_close_in_time() -> None:
    t0 = datetime(2014, 8, 4, 1, 36, tzinfo=UTC)
    detections = [(t0, (0.0, 0.0)), (t0 + timedelta(minutes=2), (1.0, 1.0)), (t0 + timedelta(hours=8), (2.0, 2.0))]

    passes = fs.group_passes(detections)

    assert [len(item.points) for item in passes] == [2, 1]


def test_fire_weather_uses_only_past_daily_values() -> None:
    start = datetime(2014, 8, 1, 0, tzinfo=UTC)
    hourly = [fs.Weather(start + timedelta(hours=h), 25.0, 30.0, 15.0, 135.0, 0.0) for h in range(48)]

    fire_weather = fs.FireWeather(hourly).compute()

    assert set(fire_weather.daily) == {"2014-08-01", "2014-08-02"}
    # Before noon on 2 August the 1 August value applies.
    assert fire_weather.bui_at(start + timedelta(hours=30)) == fire_weather.daily["2014-08-01"]["bui"]
    assert fire_weather.bui_at(start + timedelta(hours=36)) == fire_weather.daily["2014-08-02"]["bui"]
    # Hourly FFMC starts at the first daily computation and dries further in warm, dry air.
    assert min(fire_weather.ffmc_hour) == start + timedelta(hours=11)
    assert fire_weather.ffmc_hour[start + timedelta(hours=47)] > fire_weather.ffmc_hour[start + timedelta(hours=11)]
