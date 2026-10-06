#!/usr/bin/env python3
"""Load the fire-map data into the local PostGIS database of the scenario (scenario.DATABASE).

Writes one SQL script (tables, rows as GeoJSON geometries, spatial indexes) and
runs it with `psql` inside the `postgis` service of docker-compose.yml, so no
database driver is needed on the host. Tables, all in WGS 84 (EPSG:4326):

- targets: OSM places, building centres, roads and railways (osm_data/);
- terrain: OSM land cover (app/layers/);
- detections: the FIRMS detections of the fire;
- fronts and forecasts: the estimated front and the forecast bands per pass.

Re-running replaces the tables. Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

from app.backend import scenario

TARGETS_FILE = scenario.TARGETS_FILE
SCHEMA = """
DROP TABLE IF EXISTS targets, terrain, detections, fronts, forecasts;
CREATE TABLE targets (id serial PRIMARY KEY, kind text NOT NULL, type text, name text, osm_id text, geom geometry(Geometry, 4326) NOT NULL);
CREATE TABLE terrain (id serial PRIMARY KEY, terrain text NOT NULL, osm_tag text, name text, osm_id text, geom geometry(Geometry, 4326) NOT NULL);
CREATE TABLE detections (id serial PRIMARY KEY, instrument text, satellite text, acq_time timestamptz NOT NULL, confidence text, frp real, geom geometry(Point, 4326) NOT NULL);
CREATE TABLE fronts (pass_time timestamptz PRIMARY KEY, geom geometry(Polygon, 4326) NOT NULL);
CREATE TABLE forecasts (pass_time timestamptz NOT NULL, horizon_h int NOT NULL, band text NOT NULL, geom geometry(Polygon, 4326) NOT NULL, PRIMARY KEY (pass_time, horizon_h, band));
"""
INDEXES = """
CREATE INDEX targets_geom ON targets USING gist (geom);
CREATE INDEX targets_geog ON targets USING gist ((geom::geography));
CREATE INDEX terrain_geom ON terrain USING gist (geom);
CREATE INDEX detections_geom ON detections USING gist (geom);
CREATE INDEX detections_time ON detections (acq_time);
CREATE INDEX fronts_geom ON fronts USING gist (geom);
CREATE INDEX forecasts_geom ON forecasts USING gist (geom);
ANALYZE;
"""


def literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def geometry(geojson: dict[str, Any]) -> str:
    return f"ST_SetSRID(ST_GeomFromGeoJSON({literal(json.dumps(geojson, separators=(',', ':')))}), 4326)"


def polygon(ring_latlon: list[list[float]]) -> dict[str, Any]:
    ring = [[lon, lat] for lat, lon in ring_latlon]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def inserts(table: str, columns: list[str], rows: Iterable[list[str]], batch: int = 500) -> Iterable[str]:
    chunk: list[str] = []
    for row in rows:
        chunk.append("(" + ", ".join(row) + ")")
        if len(chunk) >= batch:
            yield f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n" + ",\n".join(chunk) + ";"
            chunk = []
    if chunk:
        yield f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n" + ",\n".join(chunk) + ";"


def build_sql() -> str:
    from app.backend import forecast, server

    parts = ["BEGIN;", SCHEMA]
    targets = json.loads(TARGETS_FILE.read_text(encoding="utf-8"))["features"]
    parts += inserts("targets", ["kind", "type", "name", "osm_id", "geom"], (
        [literal(f["properties"]["kind"]), literal(f["properties"].get("type")), literal(f["properties"].get("name")),
         literal(f["properties"].get("osm_id")), geometry(f["geometry"])] for f in targets
    ))
    terrain = json.loads(scenario.TERRAIN_FILE.read_text(encoding="utf-8"))["features"]
    parts += inserts("terrain", ["terrain", "osm_tag", "name", "osm_id", "geom"], (
        [literal(f["properties"]["terrain"]), literal(f["properties"].get("osm_tag")), literal(f["properties"].get("name")),
         literal(f["properties"].get("osm_id")), f"ST_MakeValid({geometry(f['geometry'])})"] for f in terrain
    ))
    parts += inserts("detections", ["instrument", "satellite", "acq_time", "confidence", "frp", "geom"], (
        [literal(item["instrument"]), literal(item["satellite"]), literal(item["acq_datetime_utc"]), literal(item["confidence"]),
         literal(item["frp"]), f"ST_SetSRID(ST_MakePoint({item['longitude']}, {item['latitude']}), 4326)"]
        for item in server.detections()
    ))
    states = forecast.forecasts()["states"]
    parts += inserts("fronts", ["pass_time", "geom"], ([literal(state["pass_utc"]), geometry(polygon(state["front"]))] for state in states))
    parts += inserts("forecasts", ["pass_time", "horizon_h", "band", "geom"], (
        [literal(state["pass_utc"]), str(int(horizon)), literal(band), geometry(polygon(ring))]
        for state in states for horizon, bands in state["forecast"].items() for band, ring in bands.items()
    ))
    parts += [INDEXES, "COMMIT;"]
    return "\n".join(parts) + "\n"


def run_psql(sql: str, *, compose_dir: Path = scenario.REPO_ROOT, quiet: bool = True) -> str:
    command = ["docker", "compose", "exec", "-T", "postgis", "psql", "-v", "ON_ERROR_STOP=1", "-U", "firemap", "-d", scenario.DATABASE]
    if quiet:
        command += ["-q", "-A", "-t"]
    result = subprocess.run(command, input=sql, text=True, capture_output=True, cwd=compose_dir, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"psql exited with {result.returncode}")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--sql-only", type=Path, help="write the SQL script here instead of loading it")
    args = parser.parse_args(argv)
    sql = build_sql()
    if args.sql_only:
        args.sql_only.write_text(sql, encoding="utf-8")
        print(f"SQL: {args.sql_only} ({len(sql) // 1024} KB)")
        return 0
    run_psql(sql)
    counts = run_psql("SELECT string_agg(t || '=' || n, ' ') FROM (SELECT 'targets' t, count(*) n FROM targets UNION ALL "
                      "SELECT 'terrain', count(*) FROM terrain UNION ALL SELECT 'detections', count(*) FROM detections UNION ALL "
                      "SELECT 'fronts', count(*) FROM fronts UNION ALL SELECT 'forecasts', count(*) FROM forecasts) c;")
    print(f"Loaded: {counts.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
