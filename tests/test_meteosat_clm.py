"""Tests for Meteosat's cloud mask (tools/fetch_meteosat_clm.py, app/backend/meteosat_clm.py)."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy
import pytest

from app.backend import meteosat_clm
from tools import fetch_meteosat_clm as fetch


def test_read_grib_decodes_zip_message_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    message = b"GRIB message"
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr("product.grb", message)

    handle = object()
    arrays = {"latitudes": [60.0, 61.0, 62.0, 63.0], "longitudes": [15.0, 16.0, 17.0, 18.0]}
    decoded_messages: list[bytes] = []
    released: list[object] = []

    def new_from_message(data: bytes) -> object:
        decoded_messages.append(data)
        return handle

    def get(current: object, key: str) -> int:
        assert current is handle
        assert key == "Nx"
        return 2

    def get_values(current: object) -> list[int]:
        assert current is handle
        return [0, 1, 2, 3]

    def get_array(current: object, key: str) -> list[float]:
        assert current is handle
        return arrays[key]

    def release(current: object) -> None:
        released.append(current)

    monkeypatch.setitem(sys.modules, "eccodes", SimpleNamespace(
        codes_new_from_message=new_from_message,
        codes_get=get,
        codes_get_values=get_values,
        codes_get_array=get_array,
        codes_release=release,
    ))

    size, values, lats, lons = fetch.read_grib(zipped.getvalue(), positions=True)
    assert size == 2
    assert values == [0, 1, 2, 3]
    assert lats == arrays["latitudes"]
    assert lons == arrays["longitudes"]
    assert decoded_messages == [message]
    assert released == [handle]


def test_the_fetch_source_uses_the_display_attribution() -> None:
    assert fetch.PRODUCT_ATTRIBUTION == meteosat_clm.ATTRIBUTION


def test_the_cloudy_share_leaves_out_pixels_without_data() -> None:
    # 0 clear water, 1 clear land, 2 cloud, 3 no data.
    assert fetch.cloud_pct(numpy.array([2, 2, 2, 0, 1, 3, 3])) == 60
    assert fetch.cloud_pct(numpy.array([3, 3])) is None


def test_only_the_positions_are_turned_to_find_the_area() -> None:
    lats = numpy.array([60.0, 60.0, 62.9, 62.9])  # as ecCodes gives them, turned against the values
    lons = numpy.array([10.0, 17.7, 10.0, 17.7])
    # Turned back, the position 62.9 N, 17.7 E belongs to the first value.
    assert fetch.area_index(lats, lons, 2, (17.2, 62.6, 18.3, 63.2)).tolist() == [0]


def test_every_hour_and_the_quarter_nearest_each_image_are_fetched() -> None:
    times = fetch.wanted_times(datetime(2026, 8, 15, 12, tzinfo=timezone.utc), datetime(2026, 8, 15, 14, 30, tzinfo=timezone.utc),
                               ["2026-08-08T10:16:01Z", "2026-08-15T13:08:00Z"])
    assert [moment.strftime("%d %H:%M") for moment in times] == ["08 10:15", "15 12:00", "15 13:00", "15 13:15", "15 14:00"]


def test_each_scene_gets_meteosat_s_cloudy_share(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "clm.json"
    path.write_text(json.dumps({"pixels_in_area": 101, "hours": [{"time_utc": "2026-08-15T12:00:00Z", "cloud_pct": 100}],
                                "images": [{"scene": "S1C", "cloud_pct": 100}, {"scene": "S2C", "cloud_pct": None}]}), encoding="utf-8")
    monkeypatch.setattr(meteosat_clm, "FILE", path)
    meteosat_clm.data.cache_clear()
    try:
        layer = meteosat_clm.with_cloud({"scenes": [{"scene": "S1C"}, {"scene": "S2C"}, {"scene": "L8"}]})
        assert [scene.get("meteosat_cloud_pct") for scene in layer["scenes"]] == [100, None, None]
        assert meteosat_clm.layer()["hours"][0]["cloud_pct"] == 100
        assert meteosat_clm.with_cloud(None) is None
    finally:
        meteosat_clm.data.cache_clear()
