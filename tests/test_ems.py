"""Tests for Copernicus EMS's perimeters (tools/fetch_ems_perimeters.py, app/backend/ems.py, ems.js). SYNTHETIC values."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import fetch_ems_perimeters as fetch

EMS_JS = Path(__file__).resolve().parents[1] / "app" / "frontend" / "ems.js"


def test_the_newest_version_of_each_product_of_the_area_is_found() -> None:
    page = ('<a href="https://s3/x/EMSR298_01ENSKOGEN_01DELINEATION_MAP_v1_vector.zip"> '
            '"https://s3/x/EMSR298_01ENSKOGEN_01DELINEATION_MONIT02_v1_vector.zip" '
            '"https://s3/x/EMSR298_01ENSKOGEN_01DELINEATION_MONIT02_v2_vector.zip" '
            '"https://s3/x/EMSR298_03TRANGSLET_01DELINEATION_MAP_v1_vector.zip"')
    urls = fetch.product_urls(page, "EMSR298", "01ENSKOGEN")
    assert list(urls) == ["MAP", "MONIT02"] and urls["MONIT02"].endswith("MONIT02_v2_vector.zip")


def test_a_product_is_dated_by_its_newest_image() -> None:
    rows = [{"source_nam": "Sentinel-2", "src_date": "02/07/2018"}, {"source_nam": "SPOT-6-7", "src_date": "20/07/2018"},
            {"source_nam": "CLC", "src_date": "2006"}, {"source_nam": "Not Applicable", "src_date": "Not Applicable"}]
    assert fetch.latest_source(rows) == ("2018-07-20", "SPOT-6-7")
    assert fetch.latest_source([]) is None


def test_a_perimeter_is_shown_from_the_end_of_its_image_s_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import ems
    monkeypatch.setattr(ems, "EMS_DIR", tmp_path)
    ems.perimeters.cache_clear()
    assert ems.perimeters() is None
    square = {"type": "MultiPolygon", "coordinates": [[[[15.3, 61.9], [15.4, 61.9], [15.4, 62.0], [15.3, 61.9]]]]}
    features = [{"type": "Feature", "geometry": square, "properties": {"product": name, "image_date": day, "image_source": "SPOT-6-7",
                                                                     "area_ha": ha, "parts": 1}}
                for name, day, ha in [("MONIT03", "2018-07-20", 8575), ("MAP", "2018-07-17", 828)]]
    (tmp_path / "perimeters.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    (tmp_path / "SOURCE.json").write_text(json.dumps({"attribution": "© European Union, Copernicus EMS (EMSR298)"}), encoding="utf-8")
    ems.perimeters.cache_clear()
    products = ems.perimeters()["products"]
    assert [(item["product"], item["visible_from_utc"]) for item in products] == [("MAP", "2018-07-18T00:00:00Z"), ("MONIT03", "2018-07-21T00:00:00Z")]
    ems.perimeters.cache_clear()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_show_the_newest_perimeter_by_the_clock() -> None:
    products = [{"product": "MAP", "visible_from_utc": "2018-07-18T00:00:00Z", "image_date": "2018-07-17", "image_source": "SPOT-6-7", "area_ha": 828},
                {"product": "MONIT03", "visible_from_utc": "2018-07-21T00:00:00Z", "image_date": "2018-07-20", "image_source": "SPOT-6-7", "area_ha": 8575}]
    code = (f"const m = require({json.dumps(str(EMS_JS))}); const p = {json.dumps(products)};"
            "console.log(JSON.stringify(['2018-07-17T23:00:00Z', '2018-07-19T12:00:00Z', '2018-07-25T00:00:00Z']"
            ".map((t) => (m.emsAt(p, Date.parse(t)) || {product: null}).product).concat([m.emsText(p[1], (d) => d)])));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert result[:3] == [None, "MAP", "MONIT03"] and result[3].startswith("SPOT-6/7-bild 2018-07-20, 8")
