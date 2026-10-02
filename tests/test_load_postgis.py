"""Tests for tools/load_postgis.py. The database tests run only when the local
`postgis` service of docker-compose.yml is up (`docker compose up -d postgis`)."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from app.backend import forecast, scenario
from tools import fire_spread as fs
from tools import load_postgis


def postgis_running() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "compose", "ps", "--status", "running", "-q", "postgis"],
                            capture_output=True, text=True, cwd=scenario.REPO_ROOT, check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def test_sql_literals_and_polygons() -> None:
    assert load_postgis.literal("Öjesjön's") == "'Öjesjön''s'"
    assert load_postgis.literal(None) == "NULL" and load_postgis.literal(2.5) == "2.5"
    assert load_postgis.polygon([[60.0, 16.0], [60.0, 16.1], [59.9, 16.1]]) == {
        "type": "Polygon", "coordinates": [[[16.0, 60.0], [16.1, 60.0], [16.1, 59.9], [16.0, 60.0]]],
    }
    statements = list(load_postgis.inserts("t", ["a"], (["1"] for _ in range(3)), batch=2))
    assert len(statements) == 2 and statements[0].count("(1)") == 2


@pytest.mark.skipif(not postgis_running(), reason="needs the postgis service of docker-compose.yml")
def test_loaded_tables_and_a_spatial_query_match_python() -> None:
    load_postgis.main([])
    counts = load_postgis.run_psql(
        "SELECT (SELECT count(*) FROM detections) || ' ' || (SELECT count(*) FROM fronts) || ' ' || (SELECT count(*) FROM forecasts);"
    ).split()
    assert counts == ["1727", "38", "456"]

    database = int(load_postgis.run_psql(
        "SELECT count(*) FROM targets t JOIN fronts f ON f.pass_time = '2014-08-04T13:09:00Z' "
        "WHERE t.kind = 'place' AND ST_DWithin(t.geom::geography, f.geom::geography, 5000);"
    ))
    state = next(s for s in forecast.forecasts()["states"] if s["pass_utc"] == "2014-08-04T13:09:00Z")
    projector = fs.Projector(*scenario.FIRE_CENTRE)
    hull = [projector.xy(lat, lon) for lat, lon in state["front"]]
    places = [f for f in json.loads(load_postgis.TARGETS_FILE.read_text(encoding="utf-8"))["features"] if f["properties"]["kind"] == "place"]
    python = sum(1 for f in places if fs.distance_to_hull(projector.xy(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]), hull) <= 5000)
    # Python uses a local flat projection, PostGIS the ellipsoid: allow a boundary case or two.
    assert abs(database - python) <= 2 and database > 100
