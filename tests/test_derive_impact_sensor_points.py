"""Tests for provenance on synthetic sensors derived from reported damage sites."""

from __future__ import annotations

from datetime import datetime, timezone

from tools.derive_impact_sensor_points import points, with_measurement_provenance


def test_impact_sensor_points_keep_site_sources_and_mark_the_collection_synthetic() -> None:
    impacts = [
        {"site": "Road A", "latitude": 59.0, "longitude": 16.0, "source_label": "Report A"},
        {"site": "Road B", "latitude": 59.01, "longitude": 16.01},
    ]
    stations = [{"id": "station-1", "latitude": 59.0, "longitude": 16.0, "earlier_max": {"value": 1.0}}]

    collection = points(impacts, stations, default_source="Scenario report")

    assert collection["sources"] == ["Report A", "Scenario report"]
    assert collection["synthetic"] is True
    assert "simulated" in collection["note"]
    assert [feature["properties"]["source"] for feature in collection["features"]] == ["Report A", "Scenario report"]
    assert all(feature["properties"]["station"] == "station-1" for feature in collection["features"])


def test_sensor_collection_records_the_flow_attribution_and_derivation_time() -> None:
    collection = {"type": "FeatureCollection", "features": [], "sources": ["Scenario report"], "synthetic": True}
    derived = with_measurement_provenance(collection, "SMHI open data, CC BY 4.0 SE",
                                          datetime(2026, 10, 24, tzinfo=timezone.utc))

    assert derived["attribution"] == "SMHI open data, CC BY 4.0 SE"
    assert derived["derived_utc"] == "2026-10-24T00:00:00Z"
