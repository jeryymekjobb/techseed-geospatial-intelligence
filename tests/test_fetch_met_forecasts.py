"""Tests for tools/fetch_met_forecasts.py without the network."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tools import fetch_met_forecasts as fetch


def test_the_runs_are_every_six_hours_through_the_period() -> None:
    runs = fetch.runs(datetime(2018, 7, 12, tzinfo=timezone.utc), datetime(2018, 8, 8, 18, tzinfo=timezone.utc))
    assert len(runs) == 28 * 4 and runs[0].hour == 0 and runs[1].hour == 6 and runs[-1] == datetime(2018, 8, 8, 18, tzinfo=timezone.utc)
    assert fetch.run_url(runs[21]) == \
        "https://thredds.met.no/thredds/dodsC/meps25epsarchive/2018/07/17/meps_mbr0_pp_2_5km_20180717T06Z.nc"


def test_the_grid_s_wind_is_turned_to_compass_directions() -> None:
    # On the central meridian the grid's north is true north: a wind blowing west comes from the east.
    assert fetch.true_wind(-2.0, 0.0, 15.0) == (2.0, 90)
    assert fetch.true_wind(0.0, -3.0, 15.0) == (3.0, 0)
    # Ten degrees east of it the grid's north is turned by sin(63°) * 10 ≈ 8.9°.
    speed, direction = fetch.true_wind(1.0, 0.0, 25.0)
    assert speed == pytest.approx(1.0) and direction == 279


def test_the_licence_and_the_attribution_name_met_norway() -> None:
    assert "CC BY 4.0" in fetch.LICENCE and "MET Norway" in fetch.ATTRIBUTION
