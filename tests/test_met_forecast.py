"""Tests for MET Norway's forecast at the scenario clock (app/backend/met_forecast.py), with synthetic runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.backend import met_forecast as mf
from tools import fire_spread as fs

ISSUED = datetime(2018, 7, 17, 6, tzinfo=timezone.utc)


def run(issued: datetime = ISSUED, wind_from: list[int] | None = None, gust: list[float] | None = None, rain_acc: list[float] | None = None,
        humidity: list[float] | None = None, thunder: list[float] | None = None) -> dict:
    hours = 25
    return {
        "issued_utc": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "times_utc": [(issued + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ") for hour in range(hours)],
        "point": {
            "latitude": 61.95, "longitude": 15.43,
            "wind_ms": [4.0] * hours, "wind_from_deg": wind_from or [135] * hours, "gust_ms": gust or [6.0] * hours,
            "temperature_k": [300.0] * hours, "humidity": humidity or [45.0] * hours,
            "precipitation_acc_mm": rain_acc or [0.0] * hours, "cloud_pct": [10.0] * hours, "thunderstorm_index": thunder or [0.0] * hours,
        },
        "grid": [{"latitude": 62.0, "longitude": 15.4, "wind_ms": [3.0] * hours, "wind_from_deg": [90] * hours, "precipitation_acc_mm": [0.0] * hours}],
    }


def test_a_run_is_shown_only_from_when_it_was_published() -> None:
    runs = (run(ISSUED - timedelta(hours=6)), run(ISSUED))
    assert mf.run_at(ISSUED + timedelta(hours=2, minutes=59), runs)["issued_utc"] == "2018-07-17T00:00:00Z"
    assert mf.run_at(ISSUED + mf.AVAILABLE_AFTER, runs)["issued_utc"] == "2018-07-17T06:00:00Z"
    assert mf.run_at(ISSUED - timedelta(hours=4), runs) is None


def test_the_hours_carry_the_hourly_rain_and_celsius() -> None:
    hours = mf.hourly(run(rain_acc=[0.0, 0.4, 1.0] + [1.0] * 22))
    assert [item["precipitation_mm"] for item in hours[:4]] == [0.0, 0.4, 0.6, 0.0]
    assert hours[0]["temperature_c"] == pytest.approx(26.9)


def test_the_notices_tell_the_rescue_service_what_matters() -> None:
    texts = lambda forecast: [item["text"] for item in mf.notices(mf.hourly(forecast))]  # noqa: E731
    assert texts(run()) == ["Inget regn de närmaste 24 timmarna"]
    turning = run(wind_from=[135] * 9 + [315] * 16, gust=[6.0] * 14 + [14.2] + [6.0] * 10, rain_acc=[0.0] * 20 + [3.0] * 5,
                  humidity=[45.0] * 10 + [27.0] + [45.0] * 14, thunder=[0.0] * 16 + [0.5] + [0.0] * 8)
    assert texts(turning) == [
        "Vindvridning från sydost till nordväst om cirka 9 timmar",  # from hour 9
        "Byvind upp till 14 meter per sekund från nordväst om 14 timmar",
        "Regn, 3 millimeter de närmaste 24 timmarna",
        "Låg luftfuktighet, ned till 27 procent",
        "Risk för åska om 16 timmar, nya bränder kan tändas",
    ]


def test_the_log_gets_only_the_news_of_each_run(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = (run(ISSUED - timedelta(hours=12)), run(ISSUED - timedelta(hours=6)), run(ISSUED, thunder=[0.0] * 10 + [0.6] + [0.0] * 14))
    monkeypatch.setattr(mf, "runs", lambda: runs)
    assert [item["news"] for item in mf.issues()] == [
        ["Inget regn de närmaste 24 timmarna"], [], ["Risk för åska om 7 timmar, nya bränder kan tändas"]]
    assert mf.issues()[2]["available_utc"] == "2018-07-17T09:00:00Z"
    # In the hour at hand: "nu", not "om 0 timmar".
    assert mf.notices(mf.hourly(run(thunder=[0.6] + [0.0] * 24)))[-1]["text"] == "Risk för åska nu, nya bränder kan tändas"


def test_the_screens_get_the_forecast_at_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mf, "runs", lambda: (run(),))
    # SMHI's observations from 1 July up to the run: dry and warm.
    observed = tuple(fs.Weather(datetime(2018, 7, 1, tzinfo=timezone.utc) + timedelta(hours=hour), 25.0, 35.0, 15.0, 135.0, 0.0)
                     for hour in range(16 * 24 + 6))
    monkeypatch.setattr(mf, "observed_weather", lambda: observed)
    assert mf.at(ISSUED) is None
    forecast = mf.at(ISSUED + timedelta(hours=3, minutes=20))
    assert forecast["label"].startswith("Historisk prognos från MET Norway") and forecast["issued_utc"] == "2018-07-17T06:00:00Z"
    assert [item["hours"] for item in forecast["summaries"]] == [6, 12]  # the run reaches 24 h from its issue, not 48 from the clock
    assert forecast["summaries"][0]["wind_from"] == "SO" and forecast["summaries"][0]["gust_max_ms"] == 6.0
    assert forecast["fwi"] and forecast["fwi"][0]["date"] == "2018-07-17" and forecast["fwi"][0]["fwi"] > 0
    assert forecast["wind_grid"][0]["wind_from_deg"] == 90 and forecast["wind_grid_hours_ahead"] == 6


def test_the_weather_chart_is_the_next_synoptic_hour_after_the_clock() -> None:
    forecast = run()
    forecast["isobars"] = [{"valid_utc": f"2018-07-17T{hour:02d}:00:00Z", "lines": [], "centres": []} for hour in (6, 9, 12)]
    # At 08:00 UTC one looks up the forecast for 09 UTC; at 09:00 the one for 12 UTC.
    assert mf.isobars_at(forecast, ISSUED + timedelta(hours=2))["valid_utc"] == "2018-07-17T09:00:00Z"
    assert mf.isobars_at(forecast, ISSUED + timedelta(hours=3))["valid_utc"] == "2018-07-17T12:00:00Z"
    assert mf.isobars_at(forecast, ISSUED + timedelta(hours=7))["valid_utc"] == "2018-07-17T12:00:00Z"  # past them all: the last
    assert mf.isobars_at(run(), ISSUED + timedelta(hours=6)) is None  # a run fetched before the isobars


def test_a_flood_hears_of_heavy_rain_snow_and_thunder_not_of_fires() -> None:
    texts = lambda forecast, **kw: [item["text"] for item in mf.notices(mf.hourly(forecast), "flood", **kw)]  # noqa: E731
    rainy = run(rain_acc=[0.0] * 5 + [6.0] + [8.0] * 19, gust=[6.0] * 20 + [12.0] * 5, thunder=[0.0] * 8 + [0.5] + [0.0] * 16)
    assert texts(rainy) == [
        "Kraftigt regn, upp till 6 millimeter på en timme om 5 timmar",
        "Nederbörd, 8 millimeter de närmaste 24 timmarna",
        "Byvind upp till 12 meter per sekund från sydost om 20 timmar",
        "Risk för åska och skyfall om 8 timmar",
    ]
    cold = run(rain_acc=[0.0] + [float(hour) for hour in range(1, 25)])
    for hour in range(25):
        cold["point"]["temperature_k"][hour] = 272.0
    assert "Nederbörden faller mest som snö" in texts(cold)
    assert texts(run()) == ["Ingen nederbörd de närmaste 24 timmarna"]
    # Without a thunder variable (AROME-MetCoOp in 2014) no thunder is said, whatever the threshold.
    silent = run()
    silent["point"]["thunderstorm_index"] = None
    assert all(item["thunderstorm_index"] is None for item in mf.hourly(silent))


def test_the_log_line_starts_with_the_mean_wind_of_the_first_six_hours() -> None:
    def hour(from_deg: float, ms: float) -> dict:
        return {"wind_from_deg": from_deg, "wind_ms": ms}
    # South-east and east-south-east average to south-east; a calm hour lowers the speed.
    assert mf.wind_now([hour(135, 6.0)] * 3 + [hour(112, 6.0)] * 2 + [hour(135, 0.0)]) == {"from": "sydost", "ms": 5}
    assert mf.wind_now([hour(270, 4.0)] * 5) is None  # a run shorter than six hours
