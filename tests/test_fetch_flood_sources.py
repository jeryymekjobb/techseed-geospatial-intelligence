"""Tests for the flood scenarios' map-service fetchers, MCF's flood maps over ArcGIS REST
(tools/fetch_mcf_flood_maps.py) and the municipality's objects over WFS
(tools/fetch_municipal_features.py), with stand-ins for the services (no network needed)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from tools import fetch_mcf_flood_maps as mcf
from tools import fetch_municipal_features as municipal

BBOX = (17.2, 62.3, 17.5, 62.5)


def query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def test_mcf_s_areas_are_asked_with_arcgis_rest_page_by_page_and_written_with_their_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mcf.scenario, "FLOOD_HAZARD_WMS", {"attribution": "MCF, översiktlig översvämningskartering"})
    monkeypatch.setattr(mcf.scenario, "MAP_BBOX", BBOX)
    monkeypatch.setattr(mcf, "LAYERS", {"100ar": (2, "100-årsflöde", "MCF")})
    monkeypatch.setattr(mcf, "PAGE", 2)
    asked = []

    def answer(url: str) -> dict:
        asked.append(url)
        offset = int(query(url)["resultOffset"])
        features = [{"type": "Feature", "properties": {"n": n}, "geometry": None} for n in range(offset, min(offset + 2, 3))]
        return {"type": "FeatureCollection", "features": features}
    monkeypatch.setattr(mcf, "get_json", answer)

    assert mcf.main(["--out", str(tmp_path)]) == 0
    first = query(asked[0])
    assert urlsplit(asked[0]).path.endswith("/MapServer/2/query")
    assert (first["geometry"], first["inSR"], first["outSR"], first["f"]) == ("17.2,62.3,17.5,62.5", "4326", "4326", "geojson")
    assert [query(url)["resultOffset"] for url in asked] == ["0", "2"]  # a short page is the last
    written = json.loads((tmp_path / "mcf-100ar.geojson").read_text(encoding="utf-8"))
    assert [feature["properties"]["n"] for feature in written["features"]] == [0, 1, 2]
    assert written["source"].startswith("MCF, översiktlig översvämningskartering, https://gis-tjanster.mcf.se/")
    assert written["fetched_utc"].endswith("Z") and written["title"] == "100-årsflöde"


def test_a_page_cut_by_the_service_s_own_limit_is_followed_by_the_next() -> None:
    pages = iter([{"features": [{}], "properties": {"exceededTransferLimit": True}}, {"features": []}])
    original = mcf.get_json
    try:
        mcf.get_json = lambda url: next(pages)
        assert len(mcf.fetch(2, BBOX)) == 1
    finally:
        mcf.get_json = original


def test_a_scenario_without_mcf_maps_stops_with_a_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mcf.scenario, "FLOOD_HAZARD_WMS", None)
    with pytest.raises(SystemExit) as stopped:
        mcf.main(["--out", str(tmp_path)])
    assert stopped.value.code == 1 and not list(tmp_path.iterdir())


def test_the_municipality_s_objects_come_by_wfs_and_the_stormwater_points_get_the_model_s_depth(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(municipal.scenario, "MUNICIPAL_WMS", {"url": "https://kommun.test/geoserver/wms", "attribution": "Sundsvalls kommun"})
    point = {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [17.3, 62.4]}}
    outside = {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [17.4, 62.45]}}

    def answer(url: str) -> dict:
        asked = query(url)
        if asked.get("request") == "GetFeature":
            features = [point, outside] if asked["typeNames"] == municipal.WFS_LAYERS["critical-stormwater"] else []
            return {"type": "FeatureCollection", "features": json.loads(json.dumps(features))}
        assert asked["REQUEST"] == "GetFeatureInfo" and asked["QUERY_LAYERS"] == municipal.DEPTH_LAYER
        depth = 0.4567 if float(asked["BBOX"].split(",")[0]) < 17.35 else -1.7976931348623157e308  # no-data outside the model, as the tool expects it
        return {"features": [{"properties": {"GRAY_INDEX": depth}}]}
    monkeypatch.setattr(municipal, "get_json", answer)

    assert municipal.wfs_url("L").startswith("https://kommun.test/geoserver/wfs?")
    assert query(municipal.wfs_url("L"))["srsName"] == "EPSG:4326"
    assert municipal.main(["--out", str(tmp_path)]) == 0
    written = json.loads((tmp_path / "critical-stormwater.geojson").read_text(encoding="utf-8"))
    assert [feature["properties"]["model_depth_100y_m"] for feature in written["features"]] == [0.457, None]
    assert written["source"] == "Sundsvalls kommun, SundsvallsKommun:GATA_KritiskDagvatten_punkt (WFS)"
    assert written["depth_source"].startswith(municipal.DEPTH_LAYER)
    assert municipal.depth_from({"features": []}) is None
