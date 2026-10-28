#!/usr/bin/env python3
"""Count the buildings by a stream below a dam, for the scenario's marked "if the dam failed".

There is no open dam-break mapping for the scenario's dam, and one may be classified, so the demo
does not model a flood wave. As the user chose on 2026-10-28 it shows the dam as a marked "if":
the buildings within DAM["distance_m"] of the stream that runs from it (OpenStreetMap's waterway
lines named DAM["stream"], kept north of the dam, downstream for Sidsjöbäcken, which runs north to
the Selånger river), counted once in the scenario's PostGIS, and the places DAM["places"] names with
their distance from the stream. The stream comes from DAM["osm_extract"] with GDAL's OSM driver,
in Docker or natively (--tools); the result goes to DAM_FILE.

    TECHSEED_SCENARIO=ljungan-aug2023 .venv/bin/python -m tools.derive_dam_exposure

OpenStreetMap data © OpenStreetMap contributors (ODbL).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.backend import postgres, scenario
from tools import geo_tools
from tools.fetch_landsat_scene import GDAL_IMAGE

NOTE = "Illustrativt: byggnader nära bäcken nedströms dammen, ingen dammbrottsmodell"


def extract_steps(extract: str, stream: str, bbox: tuple[float, float, float, float]) -> list[list[str]]:
    """GDAL's steps for the stream's lines inside the bbox (west, south, east, north) as GeoJSON."""
    west, south, east, north = bbox
    return [["ogr2ogr", "-f", "GeoJSON", "stream-osm.geojson", extract, "lines",
             "-spat", str(west), str(south), str(east), str(north), "-where", f"name = '{stream}'"]]


def user() -> str:
    return f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "0:0"


def downstream(collection: dict[str, Any], latitude: float) -> dict[str, Any]:
    """The stream's lines as one MultiLineString, each cut to its points north of the dam (at least two)."""
    lines = []
    for feature in collection["features"]:
        geometry = feature["geometry"]
        parts = geometry["coordinates"] if geometry["type"] == "MultiLineString" else [geometry["coordinates"]]
        for part in parts:
            kept = [point for point in part if point[1] >= latitude]
            if len(kept) >= 2:
                lines.append(kept)
    return {"type": "MultiLineString", "coordinates": lines}


def exposure_sql(stream: dict[str, Any], distance_m: float, places: list[dict[str, Any]]) -> str:
    """One JSON object: the buildings within the distance (how many, their middle) and each place's distance."""
    line = f"ST_SetSRID(ST_GeomFromGeoJSON('{json.dumps(stream)}'), 4326)::geography"
    place_rows = ", ".join(f"('{item['name'].replace(chr(39), chr(39) * 2)}', ST_SetSRID(ST_MakePoint({item['longitude']}, {item['latitude']}), 4326))"
                           for item in places) or "(NULL, NULL)"
    return (f"SELECT json_build_object('count', b.count, 'latitude', round(ST_Y(b.centre)::numeric, 5), "
            f"'longitude', round(ST_X(b.centre)::numeric, 5), 'places', (SELECT json_object_agg(p.name, round(ST_Distance(p.geom::geography, {line})::numeric)) "
            f"FROM (VALUES {place_rows}) AS p(name, geom) WHERE p.name IS NOT NULL)) "
            f"FROM (SELECT count(*) AS count, ST_Centroid(ST_Collect(ST_Centroid(t.geom))) AS centre FROM targets t "
            f"WHERE t.kind = 'building' AND ST_DWithin(t.geom::geography, {line}, {distance_m})) AS b;")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    geo_tools.add_argument(parser)
    args = parser.parse_args(argv)
    dam, out = scenario.DAM, scenario.DAM_FILE
    if not dam or out is None:
        parser.exit(1, f"derive_dam_exposure: the scenario {scenario.NAME} has no DAM\n")
    extract = Path(dam["osm_extract"])
    out.parent.mkdir(parents=True, exist_ok=True)
    steps = extract_steps(f"/osm/{extract.name}", dam["stream"], scenario.MAP_BBOX)
    if geo_tools.choice(args.tools) == "native":
        result = geo_tools.run_native(extract_steps(str(extract), dam["stream"], scenario.MAP_BBOX), out.parent)
    else:
        result = subprocess.run(["docker", "run", "--rm", "-u", user(), "-v", f"{out.parent}:/data", "-v", f"{extract.parent}:/osm:ro",
                                 GDAL_IMAGE, "sh", "-c", geo_tools.shell_script(steps)], capture_output=True, text=True)
    if result.returncode != 0:
        parser.exit(1, f"derive_dam_exposure: GDAL failed:\n{result.stderr[-1500:]}\n")
    raw = out.parent / "stream-osm.geojson"
    stream = downstream(json.loads(raw.read_text(encoding="utf-8")), dam["latitude"])
    raw.unlink()
    if not stream["coordinates"]:
        parser.exit(1, f"derive_dam_exposure: no '{dam['stream']}' below the dam in {extract}\n")
    query = subprocess.run(postgres.command(scenario.DATABASE, quiet=True) + ["-A", "-t", "-c", exposure_sql(stream, dam["distance_m"], dam["places"])],
                           capture_output=True, text=True)
    if query.returncode != 0:
        parser.exit(1, f"derive_dam_exposure: PostGIS failed: {query.stderr[-500:]}\n")
    found = json.loads(query.stdout.strip())
    distances = found.get("places") or {}
    result_file = {
        "name": dam["name"], "latitude": dam["latitude"], "longitude": dam["longitude"], "stream": dam["stream"],
        "distance_m": dam["distance_m"], "buildings": int(found["count"]),
        "buildings_latitude": found["latitude"], "buildings_longitude": found["longitude"],
        "places": [{**item, "from_stream_m": distances.get(item["name"])} for item in dam["places"]],
        "trigger_sensor": dam["trigger_sensor"], "stream_geometry": stream, "note": NOTE,
        "source": "© OpenStreetMap contributors (ODbL); byggnader räknade i PostGIS",
        "derived_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out.write_text(json.dumps(result_file, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{dam['name']}: {result_file['buildings']} buildings within {dam['distance_m']} m of {dam['stream']}; places {distances}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
