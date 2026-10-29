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


def test_a_passing_server_failure_is_tried_again(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)
    calls = []

    def flaky(value: int) -> int:
        calls.append(value)
        if len(calls) < 3:
            raise RuntimeError("NetCDF: DAP failure")
        return value * 2

    assert fetch.retried(flaky, 21) == 42 and len(calls) == 3
    with pytest.raises(RuntimeError):
        fetch.retried(lambda: (_ for _ in ()).throw(RuntimeError("down")))


def test_each_period_of_meps_takes_the_archive_s_file_of_its_time() -> None:
    # The archive holds the deterministic run as one file from 2020 to September 2023 and from 2025,
    # and as an NcML aggregation from October 2023 through 2024.
    at = lambda *parts: fetch.run_url(datetime(*parts, tzinfo=timezone.utc)).rsplit("/", 1)[1]  # noqa: E731
    assert at(2020, 2, 20, 0) == "meps_det_2_5km_20200220T00Z.nc"
    assert at(2023, 9, 30, 18) == "meps_det_2_5km_20230930T18Z.nc"
    assert at(2023, 10, 1, 0) == "meps_det_sfc_20231001T00Z.ncml" and at(2024, 1, 25, 6) == "meps_det_sfc_20240125T06Z.ncml"
    assert at(2025, 9, 6, 12) == "meps_det_2_5km_20250906T12Z.nc"
