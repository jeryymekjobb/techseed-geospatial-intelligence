"""Tests for the pure conversions in tools/fetch_era5_land.py (SYNTHETIC values)."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tools import fetch_era5_land as era5

UTC = timezone.utc


def test_wind_direction_is_where_the_wind_comes_from() -> None:
    assert era5.wind(0.0, 3.0) == (3.0, 180.0)        # blowing north: from the south
    speed, direction = era5.wind(-2.0, 2.0)            # blowing north-west: from the south-east
    assert math.isclose(speed, math.hypot(2, 2)) and math.isclose(direction, 135.0)
    assert math.isclose(era5.wind(3.0, 0.0)[1], 270.0)  # blowing east: from the west


def test_relative_humidity_from_temperature_and_dewpoint() -> None:
    assert era5.relative_humidity(20.0, 20.0) == 100.0
    assert 35 < era5.relative_humidity(31.5, 14.5) < 38


def test_precipitation_is_de_accumulated_from_00_utc() -> None:
    day = datetime(2014, 8, 4, tzinfo=UTC)
    accumulated = {day + timedelta(hours=hour): value for hour, value in [(0, 0.004), (1, 0.001), (2, 0.0015), (3, 0.0015)]}

    hourly = era5.hourly_precipitation(accumulated)

    assert math.isnan(hourly[day])  # needs the previous day's 23 UTC value
    assert [round(hourly[day + timedelta(hours=hour)], 3) for hour in (1, 2, 3)] == [1.0, 0.5, 0.0]


def test_requests_are_split_per_month_with_all_hours() -> None:
    requests = era5.requests_for(date(2014, 7, 30), date(2014, 8, 2))

    assert [(item["month"], item["day"]) for item in requests] == [("07", ["30", "31"]), ("08", ["01", "02"])]
    assert len(requests[0]["time"]) == 24


def test_rows_keep_the_period_and_derive_columns() -> None:
    start = datetime(2014, 8, 3, 23, tzinfo=UTC)
    records = [
        {"time": start + timedelta(hours=hour), "latitude": 59.9, "longitude": 16.2,
         "u10": -2.0, "v10": 2.0, "t2m": 304.65, "d2m": 287.65, "tp": 0.002 if hour == 0 else 0.0}
        for hour in range(3)
    ]

    rows = era5.rows_from(records, date(2014, 8, 4), date(2014, 8, 4))

    assert [row["time_utc"] for row in rows] == ["2014-08-04T00:00:00Z", "2014-08-04T01:00:00Z"]
    assert (rows[0]["wind_from_deg"], rows[0]["t2m_c"], rows[0]["d2m_c"]) == (135, 31.5, 14.5)
    assert rows[1]["precip_mm"] == 0.0


def test_a_point_at_sea_without_values_is_left_out() -> None:
    moment = datetime(2026, 8, 16, 6, tzinfo=UTC)
    land = {"time": moment, "latitude": 62.4, "longitude": 17.3, "u10": 3.0, "v10": 0.0, "t2m": 288.15, "d2m": 286.15, "tp": 0.0}
    sea = {**land, "longitude": 17.8, "u10": math.nan, "v10": math.nan, "t2m": math.nan, "d2m": math.nan, "tp": math.nan}

    rows = era5.rows_from([land, sea], date(2026, 8, 16), date(2026, 8, 16))

    assert [(row["latitude"], row["longitude"]) for row in rows] == [(62.4, 17.3)]


def test_main_writes_a_source_sidecar_for_the_derived_csv(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "era5-land-2014-08.nc"
    record = {"time": datetime(2014, 8, 4, 1, tzinfo=UTC), "latitude": 59.5, "longitude": 15.5,
              "u10": 1.0, "v10": 0.0, "t2m": 293.15, "d2m": 288.15, "tp": 0.001}
    monkeypatch.setattr(era5, "download", lambda area, start, end, raw_dir: [raw])
    monkeypatch.setattr(era5, "read_netcdf", lambda path: [record])
    output = tmp_path / "era5-land-test.csv"

    assert era5.main(["--area", "60,15,59,16", "--start", "2014-08-04", "--end", "2014-08-04",
                      "--raw-dir", str(tmp_path / "raw"), "--out", str(output)]) == 0

    source = json.loads(output.with_suffix(".SOURCE.json").read_text(encoding="utf-8"))
    assert source["dataset"] == "reanalysis-era5-land"
    assert source["doi"] == "10.24381/cds.e2161bac"
    assert source["licence"] == "CC BY 4.0" and "Copernicus Climate Change Service" in source["attribution"]
    assert source["request_period_utc"] == ["2014-08-03", "2014-08-04"]
    assert source["raw_files"] == [raw.name]
