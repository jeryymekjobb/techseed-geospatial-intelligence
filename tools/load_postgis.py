#!/usr/bin/env python3
"""Load the fire-map data into the local PostGIS database of the scenario (scenario.DATABASE).

Writes one SQL script (tables, rows as GeoJSON geometries, spatial indexes) and
runs it with `psql` inside the `postgis` service of docker-compose.yml, so no
database driver is needed on the host. Tables, all in WGS 84 (EPSG:4326):

- targets: OSM places, building centres, roads and railways (the scenario's TARGETS_FILE);
- terrain: OSM land cover (its TERRAIN_FILE);
- for the fire: detections (FIRMS), and fronts and forecasts, the estimated front and the
  forecast bands per pass;
- for the flood: flood_areas, the municipality's 100-year flow of the Selånger river and
  MCF's 100-year and highest calculated flows clipped to the map area (the scenario's
  MCF_LAYERS), and stormwater_points, the municipality's critical stormwater points with the
  depth its cloudburst model gives there; empty where the scenario has no municipal data.

A scenario's database is created, with PostGIS, if it does not exist yet. Re-running
replaces the tables. Only the Python standard library is used.
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
DROP TABLE IF EXISTS targets, terrain, detections, fronts, forecasts, flood_areas, stormwater_points;
CREATE TABLE targets (id serial PRIMARY KEY, kind text NOT NULL, type text, name text, osm_id text, geom geometry(Geometry, 4326) NOT NULL);
CREATE TABLE terrain (id serial PRIMARY KEY, terrain text NOT NULL, osm_tag text, name text, osm_id text, geom geometry(Geometry, 4326) NOT NULL);
"""
FIRE_SCHEMA = """
CREATE TABLE detections (id serial PRIMARY KEY, instrument text, satellite text, acq_time timestamptz NOT NULL, confidence text, frp real, geom geometry(Point, 4326) NOT NULL);
CREATE TABLE fronts (pass_time timestamptz PRIMARY KEY, geom geometry(Polygon, 4326) NOT NULL);
CREATE TABLE forecasts (pass_time timestamptz NOT NULL, horizon_h int NOT NULL, band text NOT NULL, geom geometry(Polygon, 4326) NOT NULL, PRIMARY KEY (pass_time, horizon_h, band));
"""
FLOOD_SCHEMA = """
CREATE TABLE flood_areas (id serial PRIMARY KEY, kind text NOT NULL, name text, source text NOT NULL, geom geometry(Geometry, 4326) NOT NULL);
CREATE TABLE stormwater_points (fid int PRIMARY KEY, area text, location text, object text, problem text, model_depth_m real, geom geometry(Point, 4326) NOT NULL);
"""
INDEXES = """
CREATE INDEX targets_geom ON targets USING gist (geom);
CREATE INDEX targets_geog ON targets USING gist ((geom::geography));
CREATE INDEX terrain_geom ON terrain USING gist (geom);
"""
FIRE_INDEXES = """
CREATE INDEX detections_geom ON detections USING gist (geom);
CREATE INDEX detections_time ON detections (acq_time);
CREATE INDEX fronts_geom ON fronts USING gist (geom);
CREATE INDEX forecasts_geom ON forecasts USING gist (geom);
"""
FLOOD_INDEXES = """
CREATE INDEX flood_areas_geom ON flood_areas USING gist (geom);
CREATE INDEX stormwater_points_geom ON stormwater_points USING gist (geom);
CREATE INDEX stormwater_points_geog ON stormwater_points USING gist ((geom::geography));
"""
# The flood areas: the municipality's (whole) and MCF's (clipped to the map area) by file, kind and title.
FLOOD_FILES = (
    ("municipal", "selangersan-100ar.geojson", "100ar", "Selångersån (kommunen, 2009)"),
    ("mcf", "mcf-100ar.geojson", "100ar", None),
    ("mcf", "mcf-bhf.geojson", "bhf", None),
)


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

    parts = ["BEGIN;", SCHEMA, FIRE_SCHEMA if scenario.WILDFIRE else FLOOD_SCHEMA]
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
    if not scenario.WILDFIRE:
        parts += flood_rows()
        parts += [INDEXES, FLOOD_INDEXES, "ANALYZE;", "COMMIT;"]
        return "\n".join(parts) + "\n"
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
    parts += [INDEXES, FIRE_INDEXES, "ANALYZE;", "COMMIT;"]
    return "\n".join(parts) + "\n"


def flood_rows() -> list[str]:
    """The flood's areas and stormwater points (tools/fetch_municipal_features.py, tools/fetch_mcf_flood_maps.py)."""
    west, south, east, north = scenario.MAP_BBOX
    envelope = f"ST_MakeEnvelope({west}, {south}, {east}, {north}, 4326)"
    directories = {"municipal": scenario.MUNICIPAL_DIR, "mcf": scenario.MCF_DIR}
    parts: list[str] = []
    for directory, file_name, kind, title in FLOOD_FILES:
        if directories[directory] is None:
            continue
        collection = json.loads((directories[directory] / file_name).read_text(encoding="utf-8"))
        source = collection["source"]
        # MCF's areas by watercourse and the label of their layer (files fetched before labels say MCF).
        label = collection.get("label", "MCF")
        parts += inserts("flood_areas", ["kind", "name", "source", "geom"], (
            [literal(kind), literal(title or f"{f['properties'].get('Kartering')} ({label})"), literal(source),
             f"ST_Intersection(ST_MakeValid({geometry(f['geometry'])}), {envelope})"]
            for f in collection["features"]
        ), batch=50)
    # Small parts, so the spatial index finds the area near each building quickly (MCF's areas are large).
    parts.append("CREATE TEMP TABLE flood_parts AS SELECT kind, name, source, ST_Subdivide(geom, 256) AS geom "
                 "FROM flood_areas WHERE NOT ST_IsEmpty(geom);")
    parts.append("TRUNCATE flood_areas; INSERT INTO flood_areas (kind, name, source, geom) SELECT * FROM flood_parts; DROP TABLE flood_parts;")
    if scenario.MUNICIPAL_DIR is None:
        return parts
    points = json.loads((scenario.MUNICIPAL_DIR / "critical-stormwater.geojson").read_text(encoding="utf-8"))["features"]
    parts += inserts("stormwater_points", ["fid", "area", "location", "object", "problem", "model_depth_m", "geom"], (
        [literal(f["properties"]["fid"]), literal(f["properties"].get("omrade")), literal(f["properties"].get("lokalisering")),
         literal(f["properties"].get("objekttyp")), literal(f["properties"].get("problem")),
         literal(f["properties"].get("model_depth_100y_m")), geometry({"type": "Point", "coordinates": f["geometry"]["coordinates"][:2]})]
        for f in points
    ))
    return parts


def ensure_database(*, compose_dir: Path = scenario.REPO_ROOT) -> None:
    """Create the scenario's database with PostGIS if the server does not have it yet."""
    exists = run_psql(f"SELECT 1 FROM pg_database WHERE datname = {literal(scenario.DATABASE)};", database="postgres", compose_dir=compose_dir)
    if not exists.strip():
        run_psql(f'CREATE DATABASE "{scenario.DATABASE}";', database="postgres", compose_dir=compose_dir)
    run_psql("CREATE EXTENSION IF NOT EXISTS postgis;", compose_dir=compose_dir)


def run_psql(sql: str, *, compose_dir: Path = scenario.REPO_ROOT, quiet: bool = True, database: str | None = None) -> str:
    command = ["docker", "compose", "exec", "-T", "postgis", "psql", "-v", "ON_ERROR_STOP=1", "-U", "firemap",
               "-d", database or scenario.DATABASE]
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
    ensure_database()
    run_psql(sql)
    tables = ["targets", "terrain", *(("detections", "fronts", "forecasts") if scenario.WILDFIRE else ("flood_areas", "stormwater_points"))]
    counts = run_psql("SELECT string_agg(t || '=' || n, ' ') FROM ("
                      + " UNION ALL ".join(f"SELECT '{table}' t, count(*) n FROM {table}" for table in tables) + ") c;")
    print(f"Loaded into {scenario.DATABASE}: {counts.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
