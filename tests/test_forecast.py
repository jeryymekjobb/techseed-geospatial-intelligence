"""Tests for the fire-map forecast (built from the committed FIRMS, SMHI and OSM data)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.backend import forecast


def test_one_state_per_pass_with_bands_for_every_horizon() -> None:
    data = forecast.forecasts()

    assert data["label"].startswith("Modellprognos med stor osäkerhet")
    assert len(data["states"]) == 38
    for state in data["states"]:
        assert set(state["forecast"]) == {"3", "6", "12", "24"}
        assert all(set(bands) == {"low", "central", "high"} for bands in state["forecast"].values())
        assert len(state["front"]) >= 3


def test_forecasts_use_only_the_past() -> None:
    states = forecast.forecasts()["states"]

    for state in states:
        pass_time = datetime.fromisoformat(state["pass_utc"].replace("Z", "+00:00"))
        observed = state["observed_spread"]
        if observed:
            assert datetime.fromisoformat(observed["to_utc"]) <= pass_time
    counts = [state["detections_so_far"] for state in states]
    assert counts == sorted(counts)


def test_the_4_august_afternoon_forecast_points_north_west() -> None:
    state = next(item for item in forecast.forecasts()["states"] if item["pass_utc"] == "2014-08-04T13:09:00Z")

    assert state["observed_spread"]["towards"] == "NV"
    assert state["model"]["towards"] == "NV"
    speeds = state["model"]["head_km_per_h"]
    assert speeds["low"] < speeds["central"] < speeds["high"]
    assert state["model"]["fire_weather"]["fwi"] > 25
    assert all(place["span"] for place in state["places_within_24h"])


def test_span_text() -> None:
    assert forecast._span({"high": 3, "central": 6, "low": 12}) == "3–12 h"
    assert forecast._span({"high": 2, "central": None, "low": None}) == "2–>24 h"
    assert forecast._span({"high": 1, "central": 1, "low": 1}) == "1 h"
    assert forecast._span({"high": None}) == ""


def test_pass_times_are_utc() -> None:
    first = forecast.forecasts()["states"][0]["pass_utc"]
    assert datetime.fromisoformat(first.replace("Z", "+00:00")).tzinfo == timezone.utc
