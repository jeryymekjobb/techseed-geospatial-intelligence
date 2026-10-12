"""Prepared spatial questions, answered with real PostGIS queries on the local database.

The questions are fixed: a client can only pick one by id, never send SQL or free
text. The only value that goes into the SQL is the scenario clock, formatted by the
backend itself. The front is the latest pass at or before the clock (table
`fronts`, loaded by tools/load_postgis.py). Every answer carries the SQL that ran,
its run time and the data sources, so the map result can be traced.

The queries run through one long-lived `psql` inside the `postgis` service of
docker-compose.yml, so no database driver is needed on the host and an answer
takes milliseconds instead of a new `docker exec` per question.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.backend import scenario

SOURCE = scenario.SPATIAL_SOURCE
DISTANCE_M = 5000
FORECAST_HORIZON_H = 6
MAX_ROWS = 1000
FRONT = """front AS (
  SELECT pass_time, geom FROM fronts WHERE pass_time <= {clock}::timestamptz ORDER BY pass_time DESC LIMIT 1
)"""
# Infrastructure from the OSM targets; the power grid is not in the data (decision B3 open).
INFRASTRUCTURE = """(t.kind IN ('place', 'railway')
    OR (t.kind = 'road' AND t.type IN ('trunk', 'primary', 'secondary'))
    OR (t.kind = 'building' AND t.type = 'industrial'))"""
ROWS = """SELECT json_build_object('pass_utc', (SELECT to_char(pass_time AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') FROM front),
  'rows', coalesce((SELECT json_agg(r) FROM ({query}) r), '[]'::json));"""

FIRE_QUESTIONS: dict[str, dict[str, str]] = {
    "why_fire": {"question": "Why do you believe there is a fire?"},
    "infrastructure_5km": {
        "question": "Show infrastructure within 5 km of the incident",
        "sql": f"""WITH {FRONT}
""" + ROWS.format(query=f"""SELECT t.kind, t.type, t.name,
    round(ST_Distance(t.geom::geography, f.geom::geography))::int AS distance_m,
    ST_AsGeoJSON(t.geom, 5)::json AS geometry
  FROM targets t, front f
  WHERE ST_DWithin(t.geom::geography, f.geom::geography, {DISTANCE_M}) AND {INFRASTRUCTURE}
  ORDER BY distance_m, t.kind, t.name LIMIT {MAX_ROWS}"""),
    },
    "forecast_places_6h": {
        "question": f"Which places are inside the {FORECAST_HORIZON_H} h forecast?",
        "sql": f"""WITH {FRONT}
""" + ROWS.format(query=f"""SELECT t.kind, t.type, t.name,
    round(ST_Distance(t.geom::geography, f.geom::geography))::int AS distance_m,
    ST_AsGeoJSON(t.geom, 5)::json AS geometry
  FROM targets t JOIN front f ON true
  JOIN forecasts p ON p.pass_time = f.pass_time AND p.horizon_h = {FORECAST_HORIZON_H} AND p.band = 'central'
  WHERE t.kind = 'place' AND ST_Intersects(t.geom, p.geom) AND NOT ST_Intersects(t.geom, f.geom)
  ORDER BY distance_m, t.name LIMIT {MAX_ROWS}"""),
    },
    "nearest_village": {
        "question": "How far is the nearest village from the front?",
        "sql": f"""WITH {FRONT}
""" + ROWS.format(query="""SELECT t.kind, t.type, t.name,
    round(ST_Distance(t.geom::geography, f.geom::geography))::int AS distance_m,
    ST_AsGeoJSON(t.geom, 5)::json AS geometry
  FROM targets t, front f
  WHERE t.kind = 'place' AND t.type IN ('village', 'town') AND NOT ST_Intersects(t.geom, f.geom)
  ORDER BY t.geom::geography <-> f.geom::geography LIMIT 3"""),
    },
}
KIND_NAMES = {"place": "orter", "road": "större vägsträckor", "railway": "järnvägssträckor", "building": "industribyggnader"}

# The flood: OSM targets against the 100-year flood areas (the municipality's and MCF's
# models) and round the synthetic overflow sensors of the assessment.
NEAR_OVERFLOW_M = 200
FLOOD_ROWS = """SELECT json_build_object('pass_utc', NULL, 'rows', coalesce((SELECT json_agg(r) FROM ({query}) r), '[]'::json));"""
AREA_SEPARATOR = " · "
IN_100Y = (f"SELECT string_agg(DISTINCT f.name, '{AREA_SEPARATOR}') FROM flood_areas f "
           "WHERE f.kind = '100ar' AND ST_Intersects(t.geom, f.geom)")
FLOOD_QUESTIONS: dict[str, dict[str, str]] = {
    "why_flood": {"question": "Why do you believe there is a flood?"},
    "buildings_100y": {
        "question": f"Vilka byggnader ligger inom {scenario.FLOOD_AREA_WORD}?",
        "sql": FLOOD_ROWS.format(query=f"""SELECT t.kind, t.type, t.name, 0 AS distance_m, ({IN_100Y}) AS area,
    count(*) OVER () AS total, ST_AsGeoJSON(t.geom, 5)::json AS geometry
  FROM targets t
  WHERE t.kind = 'building' AND EXISTS (SELECT 1 FROM flood_areas f WHERE f.kind = '100ar' AND ST_Intersects(t.geom, f.geom))
  ORDER BY area, t.type, t.name LIMIT {MAX_ROWS}"""),
    },
    "roads_100y": {
        "question": f"Vilka vägar och järnvägar korsar {scenario.FLOOD_AREA_WORD}?",
        "sql": FLOOD_ROWS.format(query=f"""SELECT t.kind, t.type, t.name, 0 AS distance_m, ({IN_100Y}) AS area,
    count(*) OVER () AS total, ST_AsGeoJSON(t.geom, 5)::json AS geometry
  FROM targets t
  WHERE t.kind IN ('road', 'railway') AND EXISTS (SELECT 1 FROM flood_areas f WHERE f.kind = '100ar' AND ST_Intersects(t.geom, f.geom))
  ORDER BY t.kind, area, t.name LIMIT {MAX_ROWS}"""),
    },
    "near_overflow": {
        "question": f"Vad finns inom {NEAR_OVERFLOW_M} m från de {scenario.SENSOR_WORDS['alarming']} punkterna?",
        # {points}: the overflowing synthetic sensors of the assessment at the clock, as VALUES rows.
        "sql": FLOOD_ROWS.format(query=f"""SELECT t.kind, t.type, t.name,
    round(min(ST_Distance(t.geom::geography, p.geom::geography)))::int AS distance_m, string_agg(DISTINCT p.name, ', ') AS area,
    count(*) OVER () AS total, ST_AsGeoJSON(t.geom, 5)::json AS geometry
  FROM targets t JOIN (VALUES {{points}}) AS p(name, geom)
    ON ST_DWithin(t.geom::geography, p.geom::geography, {NEAR_OVERFLOW_M})
  WHERE t.kind IN ('building', 'road', 'railway')
  GROUP BY t.id, t.kind, t.type, t.name, t.geom
  ORDER BY distance_m, t.kind, t.name LIMIT {MAX_ROWS}"""),
    },
}
QUESTIONS = FIRE_QUESTIONS if scenario.WILDFIRE else FLOOD_QUESTIONS
FLOOD_KINDS = {"building": "byggnader", "road": "vägsträckor", "railway": "järnvägssträckor"}


class Unavailable(RuntimeError):
    pass


class UnknownQuestion(ValueError):
    pass


def utc_literal(clock: datetime) -> str:
    return "'" + clock.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "'"


def overflow_points(assessment: dict[str, Any]) -> list[tuple[str, float, float]]:
    """The overflowing synthetic sensors of the flood's assessment: name, latitude, longitude."""
    return [(item["text"].removeprefix("IoT ").split(":")[0], item["ref"]["latitude"], item["ref"]["longitude"])
            for item in assessment["evidence"] if item["key"].startswith("iot:") and item["status"] == "ok" and item["ref"]]


def points_sql(points: list[tuple[str, float, float]]) -> str:
    return ", ".join(f"('{name.replace(chr(39), chr(39) * 2)}', ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326))" for name, lat, lon in points)


# The threatened buildings are named after the nearest named OSM place this close to their middle.
PLACE_NAME_M = 2000


def buildings_near_sql(points: list[tuple[str, float, float]]) -> str:
    """The buildings within NEAR_OVERFLOW_M of each point, as one JSON object by the points' names: how many,
    their middle and the nearest named OSM place within PLACE_NAME_M of it (of the point when there are none)."""
    centre = "coalesce(b.centre, p.geom)::geography"
    return (f"SELECT json_object_agg(p.name, json_build_object('count', b.count, "
            f"'latitude', round(ST_Y(b.centre)::numeric, 5), 'longitude', round(ST_X(b.centre)::numeric, 5), "
            f"'place', (SELECT t.name FROM targets t WHERE t.kind = 'place' AND t.name IS NOT NULL "
            f"AND ST_DWithin(t.geom::geography, {centre}, {PLACE_NAME_M}) "
            f"ORDER BY ST_Distance(t.geom::geography, {centre}) LIMIT 1))) "
            f"FROM (VALUES {points_sql(points)}) AS p(name, geom) "
            f"CROSS JOIN LATERAL (SELECT count(*) AS count, ST_Centroid(ST_Collect(ST_Centroid(t.geom))) AS centre "
            f"FROM targets t WHERE t.kind = 'building' "
            f"AND ST_DWithin(t.geom::geography, p.geom::geography, {NEAR_OVERFLOW_M})) AS b;")


def buildings_near(points: list[tuple[str, float, float]], psql: "Psql") -> dict[str, dict[str, Any]]:
    """The buildings within NEAR_OVERFLOW_M of each point (name, latitude, longitude), by name:
    { count, latitude, longitude, place }, the position and place None without buildings or a
    named place near; raises Unavailable."""
    if not points:
        return {}
    output = psql.query(buildings_near_sql(points)).strip()
    try:
        found = json.loads(output)
        result = {}
        for name, item in (found or {}).items():
            located = item.get("latitude") is not None and item.get("longitude") is not None
            result[str(name)] = {
                "count": int(item["count"]),
                "latitude": float(item["latitude"]) if located else None,
                "longitude": float(item["longitude"]) if located else None,
                "place": str(item["place"]) if item.get("place") else None,
            }
        return result
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError) as exc:
        raise Unavailable(f"oväntat svar från PostGIS: {output[:200]}") from exc


def sql_for(question_id: str, clock: datetime, points: list[tuple[str, float, float]] | None = None) -> str:
    if question_id not in QUESTIONS or "sql" not in QUESTIONS[question_id]:
        raise UnknownQuestion(question_id)
    sql = QUESTIONS[question_id]["sql"].replace("{clock}", utc_literal(clock))
    return sql.replace("{points}", points_sql(points)) if points else sql


class Psql:
    """One `psql` process kept open; a query is sent with a marker and read up to it."""

    def __init__(self, command: list[str] | None = None) -> None:
        self.command = command or [
            "docker", "compose", "exec", "-T", "postgis", "psql", "-U", "firemap", "-d", scenario.DATABASE,
            "-q", "-A", "-t", "-X", "-v", "ON_ERROR_STOP=0",
        ]
        self.process: subprocess.Popen[str] | None = None
        self.lock = threading.Lock()
        self.count = 0

    def _start(self) -> subprocess.Popen[str]:
        if self.process is None or self.process.poll() is not None:
            try:
                self.process = subprocess.Popen(
                    self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=scenario.REPO_ROOT, bufsize=1,
                )
            except OSError as exc:
                raise Unavailable(f"psql kunde inte startas: {exc}") from exc
        return self.process

    def query(self, sql: str) -> str:
        """The output lines of one query; raises Unavailable when PostGIS cannot answer."""
        # Without a terminator psql would wait for more SQL and answer after the marker.
        sql = sql.rstrip()
        if not sql.endswith(";"):
            sql += ";"
        with self.lock:
            process = self._start()
            self.count += 1
            marker = f"__techseed_end_{self.count}__"
            try:
                process.stdin.write(f"{sql}\n\\echo {marker}\n")
                process.stdin.flush()
                lines = []
                while True:
                    line = process.stdout.readline()
                    if not line:
                        raise Unavailable("PostGIS svarar inte (är `docker compose up -d postgis` igång?)")
                    if line.strip() == marker:
                        break
                    lines.append(line.rstrip("\n"))
            except (BrokenPipeError, OSError) as exc:
                self.process = None
                raise Unavailable("PostGIS svarar inte (är `docker compose up -d postgis` igång?)") from exc
            except Unavailable:
                self.process = None
                raise
        errors = [line for line in lines if line.startswith(("ERROR:", "psql:", "service \"postgis\""))]
        if errors:
            raise Unavailable(errors[0])
        return "\n".join(lines)


def features(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": row["geometry"],
         "properties": {key: value for key, value in row.items() if key != "geometry"}}
        for row in rows
    ]}


def name(row: dict[str, Any]) -> str:
    return row["name"] or f"{row['kind']} ({row['type']})"


def summary(question_id: str, rows: list[dict[str, Any]], pass_utc: str | None) -> str:
    if pass_utc is None:
        return "Ingen brandfront ännu – ingen satellitpassage före scenariotiden."
    if question_id == "infrastructure_5km":
        if not rows:
            return f"Ingen infrastruktur inom {DISTANCE_M // 1000} km från brandfronten (passage {pass_utc})."
        counts = {kind: sum(1 for row in rows if row["kind"] == kind) for kind in KIND_NAMES}
        parts = [f"{count} {KIND_NAMES[kind]}" for kind, count in counts.items() if count]
        limited = f" (de {MAX_ROWS} närmaste)" if len(rows) == MAX_ROWS else ""
        return (f"Inom {DISTANCE_M // 1000} km från brandfronten (passage {pass_utc}){limited}: " + ", ".join(parts)
                + ". Elnät finns inte i kartdata.")
    if question_id == "forecast_places_6h":
        if not rows:
            return f"Inga orter inom {FORECAST_HORIZON_H} h-prognosen (trolig spridning, passage {pass_utc})."
        first = ", ".join(name(row) for row in rows[:5])
        return (f"{len(rows)} orter inom {FORECAST_HORIZON_H} h-prognosen (trolig spridning, modell, passage {pass_utc}). "
                f"Närmast: {first}.")
    if not rows:
        return "Ingen by utanför brandfronten i kartdata."
    nearest = rows[0]
    kilometres = str(round(nearest["distance_m"] / 1000, 1)).replace(".", ",")
    return f"Närmaste by: {name(nearest)}, {kilometres} km från brandfronten (passage {pass_utc})."


def flood_summary(question_id: str, rows: list[dict[str, Any]], points: list[tuple[str, float, float]] | None) -> str:
    total = rows[0]["total"] if rows else 0
    limited = f" (de första {MAX_ROWS} visas)" if total > len(rows) else ""
    if question_id == "near_overflow":
        if not points:
            return f"Inga {scenario.SENSOR_WORDS['alarming']} punkter vid scenariotiden (syntetiska {scenario.SENSOR_WORDS['sensors']})."
        counts = ", ".join(f"{sum(1 for row in rows if row['kind'] == kind)} {text}" for kind, text in FLOOD_KINDS.items())
        return (f"Inom {NEAR_OVERFLOW_M} m från {len(points)} {scenario.SENSOR_WORDS['alarming']} punkter ({', '.join(name for name, _, _ in points)}; "
                f"syntetiskt underlag): {counts}{limited}.")
    areas: dict[str, int] = {}
    for row in rows:
        for area in (row["area"] or "").split(AREA_SEPARATOR):
            areas[area] = areas.get(area, 0) + 1
    by_area = ", ".join(f"{area}: {count}" for area, count in sorted(areas.items()))
    what = "byggnader" if question_id == "buildings_100y" else "väg- och järnvägssträckor"
    if not rows:
        return f"Inga {what} inom {scenario.FLOOD_AREA_WORD} i kartdata."
    return f"{total} {what} inom {scenario.FLOOD_AREA_WORD} ({by_area}){limited}. {scenario.FLOOD_MODELS}, inte observationer."


def why_fire(result: dict[str, Any]) -> dict[str, Any]:
    """Answered from the assessment, without SQL: the lines that hold, each on the map."""
    held = [item for item in result["evidence"] if item["status"] == "ok"]
    rows = [{"kind": "evidence", "type": item["key"], "name": item["text"], "distance_m": None,
             "geometry": {"type": "Point", "coordinates": [item["ref"]["longitude"], item["ref"]["latitude"]]}}
            for item in held if item["ref"]]
    if held:
        answer = (f"{result['outcome']} ({result['score_pct']} %, regelbaserad poäng): "
                  + "; ".join(item["text"] for item in held) + ".")
    else:
        answer = f"{result['outcome']}: ingen evidens håller ännu."
    return {"answer": answer, "features": features(rows), "sql": None, "source": "Bedömningen (assessment.py), se evidenslistan"}


def ask(question_id: str, clock: datetime, psql: Psql, assessment: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if question_id not in QUESTIONS:
        raise UnknownQuestion(question_id)
    started = time.perf_counter()
    points = None
    if question_id in {"why_fire", "why_flood"}:
        answer = why_fire(assessment())
    else:
        if question_id == "near_overflow":
            points = overflow_points(assessment())
            if not points:
                return {"id": question_id, "question": QUESTIONS[question_id]["question"], "answer": flood_summary(question_id, [], points),
                        "features": features([]), "sql": None, "source": SOURCE, "elapsed_ms": round((time.perf_counter() - started) * 1000, 1)}
        sql = sql_for(question_id, clock, points)
        output = psql.query(sql).strip()
        try:
            data = json.loads(output)
        except json.JSONDecodeError as exc:
            raise Unavailable(f"oväntat svar från PostGIS: {output[:200]}") from exc
        text = summary(question_id, data["rows"], data["pass_utc"]) if scenario.WILDFIRE else flood_summary(question_id, data["rows"], points)
        answer = {"answer": text, "features": features(data["rows"]), "sql": sql, "source": SOURCE}
    return {"id": question_id, "question": QUESTIONS[question_id]["question"], **answer,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1)}
