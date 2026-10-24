"""Tests for Meteosat's fire pixels (tools/fetch_meteosat_frp.py, app/backend/meteosat.py, app/frontend/meteosat.js)."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.backend import meteosat
from tools import fetch_meteosat_frp as fetch

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "meteosat.js"


def test_the_tool_asks_for_every_quarter_of_the_period() -> None:
    start = datetime(2014, 8, 4, tzinfo=timezone.utc)
    quarters = fetch.slots(start, datetime(2014, 8, 5, tzinfo=timezone.utc))
    assert len(quarters) == 96 and quarters[-1] == datetime(2014, 8, 4, 23, 45, tzinfo=timezone.utc)
    assert fetch.url(start).endswith("/HDF5/2014/08/04/HDF5_LSASAF_MSG_FRP-PIXEL-ListProduct_MSG-Disk_201408040000")


def test_the_tool_keeps_the_scaled_pixels_inside_the_map_area() -> None:
    columns = {"LATITUDE": fetch.scaled([5994, 4000, 19000], 100, 19000), "LONGITUDE": fetch.scaled([1616, 1616, 1616], 100, 19000),
               "FRP": fetch.scaled([26048, 100, -999], 10, -999), "PIXEL_SIZE": fetch.scaled([2602, 900, -999], 100, -999)}
    kept = fetch.pixels_in(columns, (15.5, 59.55, 16.8, 60.3), datetime(2014, 8, 4, 12, tzinfo=timezone.utc), "MSG3")
    assert kept == [{"time_utc": "2014-08-04T12:00:00Z", "satellite": "MSG3", "latitude": 59.94, "longitude": 16.16,
                     "frp_mw": 2604.8, "pixel_area_km2": 26.02}]


def test_a_pixel_is_drawn_with_its_area_wider_north_south_far_from_the_equator() -> None:
    corners = meteosat.footprint(59.94, 16.16, 26.02)
    east_km = (corners[1][1] - corners[0][1]) * meteosat.KM_PER_DEGREE * math.cos(math.radians(59.94))
    north_km = (corners[2][0] - corners[1][0]) * meteosat.KM_PER_DEGREE
    assert east_km == pytest.approx(3.31, abs=0.02) and north_km == pytest.approx(7.86, abs=0.02)
    assert east_km * north_km == pytest.approx(26.02, rel=0.01)
    assert meteosat.slant_km(0.0, 0.0) == pytest.approx(meteosat.GEO_HEIGHT_KM, abs=1)


def test_the_pixels_are_read_with_their_satellite_and_grouped_by_quarter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def feature(time: str, lat: float, frp: float) -> dict:
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [16.16, lat]},
                "properties": {"time_utc": time, "satellite": "MSG3", "frp_mw": frp, "pixel_area_km2": 26.0}}
    path = tmp_path / "frp-pixels.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        feature("2014-08-04T12:15:00Z", 59.94, 2592.4), feature("2014-08-04T12:00:00Z", 59.94, 2604.8),
        feature("2014-08-04T12:15:00Z", 59.88, 600.0)]}), encoding="utf-8")
    monkeypatch.setattr(meteosat, "FILE", path)
    meteosat.pixels.cache_clear()
    try:
        assert [item["satellite"] for item in meteosat.pixels()] == ["Meteosat-10"] * 3
        assert meteosat.quarters() == [
            {"time_utc": "2014-08-04T12:00:00Z", "satellite": "Meteosat-10", "pixels": 1, "max_frp_mw": 2604.8},
            {"time_utc": "2014-08-04T12:15:00Z", "satellite": "Meteosat-10", "pixels": 2, "max_frp_mw": 2592.4},
        ]
        assert meteosat.layer()["label"] == meteosat.LABEL and "CC BY 4.0" in meteosat.layer()["attribution"]
        assert meteosat.layer()["attribution"].startswith("Contains modified EUMETSAT Meteosat product ")
        monkeypatch.setattr(meteosat, "FILE", tmp_path / "missing.geojson")
        meteosat.pixels.cache_clear()
        assert meteosat.layer() is None
    finally:
        meteosat.pixels.cache_clear()


def test_the_fetch_source_uses_the_display_attribution() -> None:
    assert fetch.PRODUCT_ATTRIBUTION == meteosat.ATTRIBUTION


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_maps_show_a_pixel_from_its_quarter_on() -> None:
    code = (f"const m = require({json.dumps(str(SCRIPT))});"
            " const pixels = [{time_utc: '2014-08-04T12:00:00Z'}, {time_utc: '2014-08-04T13:45:00Z'}];"
            " console.log(JSON.stringify([m.meteosatPixelsAt(pixels, Date.parse('2014-08-04T13:00:00Z')).length,"
            " m.meteosatOpacity(0), m.meteosatOpacity(6000),"
            " m.meteosatText({satellite: 'Meteosat-10', frp_mw: 2604.8, pixel_area_km2: 26.02}, '4 aug 14:00')]));")
    shown, low, high, text = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert shown == 1 and low == 0.1 and high == pytest.approx(0.3)
    assert text.startswith("Meteosat-10 (SEVIRI): 2605 MW i en pixel på 26 km²") and "inte live" in text


def test_the_comparison_area_has_a_day_line_and_not_the_quarters() -> None:
    def pixel(time: str, area: str, frp: float) -> dict:
        return {"time_utc": time, "satellite": "Meteosat-11", "frp_mw": frp, "area": area}
    items = (pixel("2018-07-16T17:45:00Z", "compare", 3115.6), pixel("2018-07-16T17:00:00Z", "compare", 1000.0),
             pixel("2018-07-16T17:00:00Z", "compare", 900.0),
             pixel("2018-07-17T00:00:00Z", "compare", 736.1), pixel("2018-07-17T12:00:00Z", "incident", 50.0),
             pixel("2018-07-16T16:00:00Z", "incident", 40.0))
    assert [quarter["time_utc"] for quarter in meteosat.quarters(items)] == ["2018-07-16T16:00:00Z", "2018-07-17T12:00:00Z"]
    assert meteosat.compare_days(items) == [
        # The first quarter's pixels, not the day's total: the log says what was seen by then.
        {"time_utc": "2018-07-16T17:00:00Z", "satellite": "Meteosat-11", "pixels": 2, "max_frp_mw": 1000.0, "incident_seen": True},
        # The own fire's pixel at 12:00 comes after this line, so it is not counted yet.
        {"time_utc": "2018-07-17T00:00:00Z", "satellite": "Meteosat-11", "pixels": 1, "max_frp_mw": 736.1, "incident_seen": False},
    ]
