#!/usr/bin/env python3
"""Fetch the municipality's flood objects from its geoserver into the scenario's data.

For the Sundsvall scenario (MUNICIPAL_WMS in app/backend/scenarios/sundsvall2026.py):

- the critical stormwater points (GATA_KritiskDagvatten_punkt) by WFS, each with the
  depth the municipality's cloudburst model gives for a 100-year rain at the point
  (Skyfallsmodell100_tiff, metres according to its legend), read by WMS GetFeatureInfo;
  None where the point lies outside the model;
- the Selånger river's 100-year flow (Selangersan100ArsFlode2009_yta) by WFS.

Both are written as GeoJSON in WGS 84 to the scenario's MUNICIPAL_DIR with the source and
the time of fetching. The user confirmed on 2026-10-06 that the demo may use the
municipality's layers. Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.backend import scenario

USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
WFS_LAYERS = {
    "critical-stormwater": "SundsvallsKommun:GATA_KritiskDagvatten_punkt",
    "selangersan-100ar": "SundsvallsKommun:Selangersan100ArsFlode2009_yta",
}
DEPTH_LAYER = "SundsvallsKommun:Skyfallsmodell100_tiff"
# The raster's no-data value, returned outside the modelled area.
NO_DATA_BELOW = -1e300


def service_url(kind: str) -> str:
    return scenario.MUNICIPAL_WMS["url"].replace("/wms", f"/{kind}")


def get_json(url: str) -> Any:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response:
        return json.loads(response.read())


def wfs_url(layer: str) -> str:
    return f"{service_url('wfs')}?" + urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": layer,
        "outputFormat": "application/json", "srsName": "EPSG:4326",
    })


def depth_url(latitude: float, longitude: float, half: float = 0.0003) -> str:
    """GetFeatureInfo for the raster cell at the point (the centre of a 7 x 7 pixel image)."""
    return f"{service_url('wms')}?" + urlencode({
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetFeatureInfo", "LAYERS": DEPTH_LAYER,
        "QUERY_LAYERS": DEPTH_LAYER, "STYLES": "", "SRS": "EPSG:4326",
        "BBOX": f"{longitude - half},{latitude - half},{longitude + half},{latitude + half}",
        "WIDTH": 7, "HEIGHT": 7, "X": 3, "Y": 3, "INFO_FORMAT": "application/json", "FEATURE_COUNT": 1,
    })


def depth_from(answer: dict[str, Any]) -> float | None:
    """The model's depth in metres from a GetFeatureInfo answer; None outside the model."""
    for feature in answer.get("features", []):
        value = feature.get("properties", {}).get("GRAY_INDEX")
        if value is not None and value > NO_DATA_BELOW:
            return round(float(value), 3)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.MUNICIPAL_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not scenario.MUNICIPAL_WMS or args.out is None:
        parser.exit(1, f"fetch_municipal_features: the scenario {scenario.NAME} has no municipal map service\n")
    args.out.mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, layer in WFS_LAYERS.items():
        collection = get_json(wfs_url(layer))
        if name == "critical-stormwater":
            for feature in collection["features"]:
                longitude, latitude = feature["geometry"]["coordinates"][:2]
                feature["properties"]["model_depth_100y_m"] = depth_from(get_json(depth_url(latitude, longitude)))
        modelled = sum(1 for feature in collection["features"] if feature["properties"].get("model_depth_100y_m") is not None)
        (args.out / f"{name}.geojson").write_text(json.dumps({
            "type": "FeatureCollection",
            "source": f"{scenario.MUNICIPAL_WMS['attribution']}, {layer} (WFS)",
            "depth_source": f"{DEPTH_LAYER} (WMS GetFeatureInfo), metres" if name == "critical-stormwater" else None,
            "fetched_utc": fetched,
            "features": collection["features"],
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{name}: {len(collection['features'])} objects" + (f", {modelled} inside the model" if name == "critical-stormwater" else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
