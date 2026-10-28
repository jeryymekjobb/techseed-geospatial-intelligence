"""Tests for a dam as a marked "if" (tools/derive_dam_exposure.py, app/backend/dam.py). SYNTHETIC lines."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.backend import dam
from tools import derive_dam_exposure as derive


def test_the_stream_is_kept_below_the_dam() -> None:
    collection = {"features": [
        {"geometry": {"type": "LineString", "coordinates": [[17.2795, 62.3776], [17.2810, 62.3800], [17.2805, 62.3850]]}},
        {"geometry": {"type": "LineString", "coordinates": [[17.2790, 62.3700], [17.2795, 62.3770]]}},  # above the dam
        {"geometry": {"type": "MultiLineString", "coordinates": [[[17.28, 62.39], [17.2799, 62.3926]]]}},
    ]}
    assert derive.downstream(collection, 62.3796) == {"type": "MultiLineString", "coordinates": [
        [[17.2810, 62.3800], [17.2805, 62.3850]], [[17.28, 62.39], [17.2799, 62.3926]]]}


def test_the_query_counts_buildings_within_the_distance_and_measures_the_places() -> None:
    sql = derive.exposure_sql({"type": "MultiLineString", "coordinates": [[[17.28, 62.38], [17.28, 62.39]]]}, 100,
                              [{"name": "Himlabadet", "latitude": 62.394, "longitude": 17.2892}])
    assert "ST_DWithin(t.geom::geography" in sql and ", 100)" in sql and "t.kind = 'building'" in sql
    assert "('Himlabadet', ST_SetSRID(ST_MakePoint(17.2892, 62.394), 4326))" in sql
    assert derive.extract_steps("/osm/x.osm.pbf", "Sidsjöbäcken", (16.9, 62.15, 17.8, 62.62))[0][-1] == "name = 'Sidsjöbäcken'"


def test_the_backend_gives_the_dam_without_its_geometry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "dam.json"
    path.write_text(json.dumps({"name": "Sidsjödammen", "buildings": 256, "stream_geometry": {"type": "MultiLineString"}}), encoding="utf-8")
    monkeypatch.setattr(dam.scenario, "DAM_FILE", path)
    dam.layer.cache_clear()
    assert dam.layer() == {"name": "Sidsjödammen", "buildings": 256}
    monkeypatch.setattr(dam.scenario, "DAM_FILE", None)
    dam.layer.cache_clear()
    assert dam.layer() is None
    dam.layer.cache_clear()
