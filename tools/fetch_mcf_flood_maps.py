#!/usr/bin/env python3
"""Fetch MCF's (formerly MSB's) overview flood maps over the scenario's map area as GeoJSON.

The 100-year flow and the highest calculated flow of the overview mapping of watercourses
(the service in the scenario's FLOOD_HAZARD_WMS; for Sundsvall Ljungan and Indalsälven)
are read with the ArcGIS REST query of the same map service, page by page, in WGS 84, and
written to the scenario's MCF_DIR with the source and the time of fetching. Each mapped
watercourse is one multipolygon along its whole length, too large for the service
unsimplified: it is simplified to SIMPLIFY_DEG (about 5-10 m) and clipped to the map area
when it is loaded into PostGIS. The INSPIRE record gives no limitations on public access
and no conditions; name MCF as the source. Only the Python standard library is used.
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
REST = "https://gis-tjanster.mcf.se/arcgis/rest/services/Oversvamningskarteringar/karteringar/MapServer"
# The REST interface's layer ids (the WMS numbers them otherwise: 13 and 9).
LAYERS = {"100ar": (2, "100-årsflöde"), "bhf": (5, "Beräknat högsta flöde")}
PAGE = 1000
SIMPLIFY_DEG = 0.0001


def query_url(layer: int, bbox: tuple[float, ...], offset: int) -> str:
    west, south, east, north = bbox
    return f"{REST}/{layer}/query?" + urlencode({
        "where": "1=1", "geometry": f"{west},{south},{east},{north}", "geometryType": "esriGeometryEnvelope",
        "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "outSR": 4326,
        "resultOffset": offset, "resultRecordCount": PAGE, "maxAllowableOffset": SIMPLIFY_DEG, "f": "geojson",
    })


def get_json(url: str) -> dict[str, Any]:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response:
        return json.loads(response.read())


def fetch(layer: int, bbox: tuple[float, ...]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    while True:
        page = get_json(query_url(layer, bbox, len(features)))
        features += page.get("features", [])
        if len(page.get("features", [])) < PAGE and not page.get("properties", {}).get("exceededTransferLimit"):
            return features


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.MCF_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not scenario.FLOOD_HAZARD_WMS or args.out is None:
        parser.exit(1, f"fetch_mcf_flood_maps: the scenario {scenario.NAME} has no MCF flood maps\n")
    args.out.mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, (layer, title) in LAYERS.items():
        features = fetch(layer, scenario.MAP_BBOX)
        (args.out / f"mcf-{name}.geojson").write_text(json.dumps({
            "type": "FeatureCollection", "title": title,
            "source": f"{scenario.FLOOD_HAZARD_WMS['attribution']}, {REST}/{layer}, förenklad {SIMPLIFY_DEG}°",
            "fetched_utc": fetched, "features": features,
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{name}: {len(features)} areas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
