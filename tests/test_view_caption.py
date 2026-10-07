"""Tests for the main screen's caption (app/frontend/landsat.js) and the depth legend (flood_legend.js), in Node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
RADAR = {"satellite": "Sentinel-1C", "acquired_utc": "2026-08-16T05:21:32Z"}
MAP_DATA = {"source": "OpenStreetMap", "date_utc": "2026-10-02T09:40:23Z"}
FORMATS = "formatTime: (t) => 'T' + t.slice(0, 16), formatDate: (t) => 'D' + t.slice(0, 10)"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")


def node(script: str, expression: str) -> object:
    code = f"const m = require({json.dumps(str(FRONTEND / script))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def caption(scene: dict | None, image: str | None, reason: str, offline: bool = True) -> str:
    return node("landsat.js", f"viewCaption({{ scene: {json.dumps(scene)}, image: {json.dumps(image)}, reason: {json.dumps(reason)}, choice: 'radar', "
                f"mapData: {json.dumps(MAP_DATA)}, offlineTiles: {json.dumps(offline)}, {FORMATS} }})")


def test_the_caption_names_the_image_and_when_it_was_taken() -> None:
    assert caption(RADAR, "radar", "shown") == "Visas: Satellitbild – Sentinel-1C, radar, tagen T2026-08-16T05:21"
    assert caption(RADAR, "radar", "comparison").endswith("(jämförelse, tagen senare än scenariotiden)")


def test_without_an_image_the_caption_names_the_map_and_its_data_date() -> None:
    assert caption(None, None, "off") == "Visas: Karta – OpenStreetMap, data från D2026-10-02"
    assert caption(None, None, "none-yet") == "Visas: Karta – OpenStreetMap, data från D2026-10-02; ingen bild (radar) tagen ännu vid scenariotiden"
    assert caption(None, None, "off", offline=False) == "Visas: Karta – Natural Earth II (offline-kartan är inte igång)"


def test_during_the_fire_s_sequence_the_caption_names_the_detections_and_what_lies_under_them() -> None:
    def during(scene: dict | None, image: str | None, reason: str) -> str:
        return node("landsat.js", f"viewCaption({{ scene: {json.dumps(scene)}, image: {json.dumps(image)}, reason: {json.dumps(reason)}, choice: 'swir', "
                    f"mapData: {json.dumps(MAP_DATA)}, offlineTiles: true, {FORMATS}, "
                    "detection: { instrument: 'VIIRS', pass_utc: '2014-08-05T01:17:00Z' } })")

    landsat = {"satellite": "Landsat 8", "acquired_utc": "2014-08-04T10:06:44Z"}
    assert during(landsat, "ndmi", "shown") == ("Visas: VIIRS-detektioner T2014-08-05T01:17 · underlag: "
                                                "Satellitbild – Landsat 8, fukt i vegetationen (NDMI), tagen T2014-08-04T10:06")
    june = {"satellite": "Landsat 8", "acquired_utc": "2014-06-10T10:00:15Z"}
    assert during(june, "swir", "shown").endswith("tagen T2014-06-10T10:00")  # the date, no age
    assert during(None, None, "off") == "Visas: VIIRS-detektioner T2014-08-05T01:17 · underlag: Karta – OpenStreetMap, data från D2026-10-02"


def test_the_depth_legend_has_the_municipality_s_seven_classes_and_shows_with_a_depth_layer() -> None:
    classes = node("flood_legend.js", "DEPTH_CLASSES")
    assert [(item["color"], item["text"]) for item in classes] == [
        ("#17DB2E", "0,1–0,2 m"), ("#80FF01", "0,2–0,3 m"), ("#FBFF01", "0,3–0,4 m"), ("#FFC001", "0,4–0,5 m"),
        ("#FF7C01", "0,5–1 m"), ("#DE1E22", "1–2 m"), ("#680404", "mer än 2 m"),
    ]
    shown = node("flood_legend.js", "[depthLegendShown(['SundsvallsKommun:100-ar_maxvattendjup']), "
                 "depthLegendShown(['SundsvallsKommun:100-ar_maxvattenhastighet', '13']), depthLegendShown([])]")
    assert shown == [True, False, False]
