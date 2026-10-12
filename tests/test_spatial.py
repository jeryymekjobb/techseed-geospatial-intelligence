"""Tests for the prepared spatial questions (app/backend/spatial.py): only known
questions run, the psql pipe protocol and its errors (with a fake psql), the answers,
the HTTP interface, and the real queries against the local PostGIS when it runs."""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app.backend import lantmateriet, server, spatial
from app.backend.scenario_engine import ScenarioEngine

UTC = timezone.utc
CLOCK = datetime(2014, 8, 4, 12, tzinfo=UTC)
ROWS = [
    {"kind": "place", "type": "village", "name": "Seglingsberg", "distance_m": 2049, "geometry": {"type": "Point", "coordinates": [16.1, 59.8]}},
    {"kind": "road", "type": "primary", "name": None, "distance_m": 2500, "geometry": {"type": "LineString", "coordinates": [[16.1, 59.8], [16.2, 59.8]]}},
]
# A stand-in for psql: answers every query with REPLY (or exits), then echoes the marker.
FAKE_PSQL = r"""
import sys
reply = sys.argv[1]
for line in sys.stdin:
    if line.startswith("\\echo "):
        if reply == "EXIT":
            sys.exit(1)
        print(reply, flush=True)
        print(line.split(" ", 1)[1].strip(), flush=True)
"""


def fake_psql(reply: str) -> spatial.Psql:
    return spatial.Psql([sys.executable, "-c", FAKE_PSQL, reply])


def test_only_prepared_questions_have_sql_and_only_the_clock_goes_in() -> None:
    for question_id in ["infrastructure_5km", "forecast_places_6h", "nearest_village"]:
        sql = spatial.sql_for(question_id, CLOCK)
        assert "'2014-08-04T12:00:00Z'::timestamptz" in sql and "{" not in sql.replace("{clock}", "")
        assert "{clock}" not in sql
    for bad in ["why_fire", "DROP TABLE targets", "", "infrastructure_5km; --"]:
        with pytest.raises(spatial.UnknownQuestion):
            spatial.sql_for(bad, CLOCK)
    with pytest.raises(spatial.UnknownQuestion):
        spatial.ask("DROP TABLE targets", CLOCK, fake_psql("{}"), dict)


def test_the_pipe_returns_one_answer_per_query() -> None:
    psql = fake_psql(json.dumps({"pass_utc": "2014-08-04T11:13:00Z", "rows": ROWS}))
    first = spatial.ask("nearest_village", CLOCK, psql, dict)
    second = spatial.ask("infrastructure_5km", CLOCK, psql, dict)

    assert first["answer"] == "Närmaste by: Seglingsberg, 2,0 km från brandfronten (passage 2014-08-04T11:13:00Z)."
    assert first["sql"] == spatial.sql_for("nearest_village", CLOCK) and first["source"] == spatial.SOURCE
    assert second["answer"].startswith("Inom 5 km från brandfronten (passage 2014-08-04T11:13:00Z): 1 orter, 1 större vägsträckor")
    assert second["answer"].endswith("Elnät finns inte i kartdata.")
    assert [item["geometry"]["type"] for item in second["features"]["features"]] == ["Point", "LineString"]
    assert second["features"]["features"][0]["properties"] == {"kind": "place", "type": "village", "name": "Seglingsberg", "distance_m": 2049}
    assert psql.count == 2 and psql.process.poll() is None  # the same process answered both


def test_no_front_yet_and_empty_results_are_said_plainly() -> None:
    before = spatial.ask("infrastructure_5km", CLOCK, fake_psql(json.dumps({"pass_utc": None, "rows": []})), dict)
    assert before["answer"] == "Ingen brandfront ännu – ingen satellitpassage före scenariotiden."
    empty = spatial.ask("forecast_places_6h", CLOCK, fake_psql(json.dumps({"pass_utc": "2014-08-01T00:00:00Z", "rows": []})), dict)
    assert empty["answer"].startswith("Inga orter inom 6 h-prognosen")


@pytest.mark.parametrize("reply, message", [
    ("ERROR:  relation \"fronts\" does not exist", "ERROR:"),
    ("not json", "oväntat svar"),
    ("EXIT", "PostGIS svarar inte"),
])
def test_postgis_errors_become_unavailable(reply: str, message: str) -> None:
    with pytest.raises(spatial.Unavailable, match=message):
        spatial.ask("nearest_village", CLOCK, fake_psql(reply), dict)


def test_a_missing_psql_command_is_unavailable() -> None:
    with pytest.raises(spatial.Unavailable, match="kunde inte startas"):
        spatial.Psql(["/nonexistent/psql"]).query("SELECT 1")


def test_why_fire_answers_from_the_assessment_without_sql() -> None:
    result = {"outcome": "Wildfire probable", "score_pct": 79, "evidence": [
        {"key": "satellite", "status": "ok", "text": "Satellite anomaly", "ref": {"latitude": 59.9, "longitude": 16.2}},
        {"key": "camera", "status": "warn", "text": "Camera unavailable", "ref": None},
        {"key": "iot:s-1", "status": "ok", "text": "IoT S 1: rök", "ref": {"latitude": 59.91, "longitude": 16.1}},
    ]}
    answer = spatial.ask("why_fire", CLOCK, fake_psql("unused"), lambda: result)
    assert answer["sql"] is None
    assert answer["answer"] == "Wildfire probable (79 %, regelbaserad poäng): Satellite anomaly; IoT S 1: rök."
    assert [item["geometry"]["coordinates"] for item in answer["features"]["features"]] == [[16.2, 59.9], [16.1, 59.91]]


@pytest.fixture()
def base_url():
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None),
        "engine": ScenarioEngine(datetime(2014, 7, 31, tzinfo=UTC), datetime(2014, 8, 15, tzinfo=UTC)),
        "control_token": None,
        "psql": fake_psql(json.dumps({"pass_utc": "2014-08-04T11:13:00Z", "rows": ROWS[:1]})),
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url: str) -> tuple[int, dict]:
    try:
        with urlopen(url, timeout=30) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_http_questions_and_answers(base_url: str) -> None:
    status, questions = get(f"{base_url}/api/questions")
    assert status == 200 and [item["id"] for item in questions] == list(spatial.QUESTIONS)
    assert get(f"{base_url}/api/ask?q=DROP%20TABLE%20targets") == (400, {"error": "unknown_question"})

    request = Request(f"{base_url}/api/scenario/command", data=json.dumps({"command": "seek", "at": "2014-08-04T12:00:00Z"}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    urlopen(request, timeout=10).close()
    status, answer = get(f"{base_url}/api/ask?q=nearest_village")
    assert status == 200 and answer["clock_utc"] == "2014-08-04T12:00:00Z" and answer["answer"].startswith("Närmaste by: Seglingsberg")
    status, why = get(f"{base_url}/api/ask?q=why_fire")
    assert status == 200 and why["sql"] is None and why["answer"].startswith("Wildfire probable")


def postgis_running() -> bool:
    try:
        return spatial.Psql().query("SELECT count(*) FROM fronts").strip().isdigit()
    except spatial.Unavailable:
        return False


@pytest.mark.skipif(not postgis_running(), reason="needs the postgis service loaded with tools/load_postgis.py")
def test_the_real_queries_answer_within_a_second() -> None:
    psql = spatial.Psql()
    for question_id in ["infrastructure_5km", "forecast_places_6h", "nearest_village"]:
        spatial.ask(question_id, CLOCK, psql, dict)  # warm up
        answer = spatial.ask(question_id, CLOCK, psql, dict)
        assert answer["elapsed_ms"] < 1000
        assert "passage 2014-08-04T11:13:00Z" in answer["answer"]
        assert all(item["properties"]["distance_m"] >= 0 for item in answer["features"]["features"])
    infrastructure = spatial.ask("infrastructure_5km", CLOCK, psql, dict)["features"]["features"]
    assert infrastructure and max(item["properties"]["distance_m"] for item in infrastructure) <= spatial.DISTANCE_M


def test_the_buildings_near_each_point_are_counted_in_one_query() -> None:
    sql = spatial.buildings_near_sql([("dv-01", 62.39, 17.3), ("o'brien", 62.4, 17.31)])
    assert "json_object_agg(p.name" in sql and f"ST_DWithin(t.geom::geography, p.geom::geography, {spatial.NEAR_OVERFLOW_M})" in sql
    assert "t.kind = 'building'" in sql and "('o''brien', ST_SetSRID(ST_MakePoint(17.31, 62.4), 4326))" in sql
    assert spatial.buildings_near([("dv-01", 62.39, 17.3)], fake_psql('{"dv-01" : 33}')) == {"dv-01": 33}
    assert spatial.buildings_near([], fake_psql("never asked")) == {}
    with pytest.raises(spatial.Unavailable):
        spatial.buildings_near([("dv-01", 62.39, 17.3)], fake_psql("ERROR:  relation \"targets\" does not exist"))


def test_the_fire_s_threatened_places_are_listed_per_pass_once_each() -> None:
    result = server.threats(fake_psql("never asked"))
    assert result["buildings_near"] == {} and result["distance_m"] == spatial.NEAR_OVERFLOW_M
    passes = result["places"]
    assert passes and [item["clock_utc"] for item in passes] == sorted(item["clock_utc"] for item in passes)
    names = [place["name"] for item in passes for place in item["places"]]
    assert len(names) == len(set(names))  # a place is listed when it is first threatened
    first = passes[0]
    state = next(item for item in server.forecast.forecasts()["states"] if item["pass_utc"] == first["clock_utc"])
    assert first["places"] == [{"name": place["names"][0], "span": place["span"]} for place in state["places_within_24h"]]
