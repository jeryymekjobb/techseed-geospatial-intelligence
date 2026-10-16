from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "app" / "frontend"


def node(script: str, expression: str) -> object:
    code = f"const m = require({json.dumps(str(FRONTEND / script))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def run_scenario(code: str, name: str = "vasternorrland2025") -> str:
    env = {**os.environ, "TECHSEED_SCENARIO": name}
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True, capture_output=True, text=True).stdout


def test_the_documented_damage_is_sourced_sorted_and_only_in_vasternorrland() -> None:
    out = json.loads(run_scenario("import json; from app.backend import routes; print(json.dumps(routes.impacts()))"))
    assert [item["time_utc"] for item in out] == sorted(item["time_utc"] for item in out)
    assert all(item["source"].startswith("Länsstyrelsen Västernorrland") for item in out)
    assert all(item["kind"] in ("road", "rail", "alert") for item in out)
    # Every road or railway has an approximate place; the alerts have none.
    assert all(("latitude" in item) == (item["kind"] != "alert") for item in out)
    rails = [item["text"] for item in out if item["kind"] == "rail"]
    assert any("Stugusjön" in text for text in rails) and any("Prästmon" in text for text in rails)
    assert run_scenario("from app.backend import routes; print(routes.impacts(), routes.layer())", "sundsvall2026").split() == ["[]", "None"]


def test_a_piece_is_coloured_once_its_rain_passes_a_threshold() -> None:
    from app.backend import routes
    mm = [10.0, 55.0, 90.0]
    assert routes.exposure_class(mm, 0.5) == 0  # nothing has fallen before the first hour is over
    assert routes.exposure_class(mm, 1.0) == 0
    assert routes.exposure_class(mm, 2.2) == 1
    assert routes.exposure_class(mm, 3.0) == 2
    assert routes.exposure_class(mm, 9.0) == 2  # after the last hour the last sum holds


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_maps_show_what_the_clock_has_reached() -> None:
    impacts = [{"time_utc": "2025-09-07T05:00:00Z", "kind": "road", "latitude": 62.8, "longitude": 17.86, "text": "Väg 738"},
               {"time_utc": "2025-09-07T09:38:00Z", "kind": "alert", "text": "Varning"}]
    at = "Date.parse('2025-09-07T06:00:00Z')"
    assert node("routes.js", f"routeImpactsAt({json.dumps(impacts)}, {at}).map((item) => item.text)") == ["Väg 738"]
    assert node("routes.js", f"routeImpactsAt({json.dumps(impacts)}, Date.parse('2025-09-07T04:59:00Z'))") == []
    exposure = {"start_utc": "2025-09-06T12:00:00Z", "hours": 3, "thresholds_mm": [50, 80],
                "pieces": [{"kind": "road", "ref": "90", "coords": [[63, 17.6], [63.01, 17.61]], "mm": [10, 55, 90]},
                           {"kind": "rail", "ref": None, "coords": [[63.1, 17.7], [63.11, 17.71]], "mm": [1, 2, 3]}]}
    shown = node("routes.js", f"routeExposureAt({json.dumps(exposure)}, Date.parse('2025-09-06T14:30:00Z'))")
    assert [(piece["ref"], piece["level"], piece["rain"]) for piece in shown] == [("90", 1, 55)]
    assert node("routes.js", f"routeExposureClass([10, 55, 90], 3, [50, 80])") == 2


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_log_reads_the_damage_and_marks_an_approximate_time_on_screen_only() -> None:
    impacts = [{"time_utc": "2025-09-07T05:50:00Z", "kind": "rail", "approximate_time": True, "text": "Godståg spårar ur vid Stugusjön"}]
    lines = node("satlog.js", f"satelliteLog({{ routeImpacts: {json.dumps(impacts)} }}, Date.parse('2025-09-07T06:00:00Z'))")
    assert lines == [{"atMs": 1757224200000, "text": "Godståg spårar ur vid Stugusjön (tid ungefärlig)",
                      "spoken": "Godståg spårar ur vid Stugusjön", "source": "report", "kind": "route_impact"}]
    assert node("satlog.js", "SATLOG_SOURCES.report") == "Länsstyrelsen, utredning"
    assert node("satlog.js", f"spokenLines({json.dumps(lines)}, new Set())") == [{"text": "Godståg spårar ur vid Stugusjön"}]


def test_a_line_is_cut_into_pieces_that_join_and_the_rain_adds_up_by_the_hour() -> None:
    import numpy as np

    from tools import derive_route_exposure as tool
    # About 3.3 km east at 63 N in steps of about 0.5 km: three or four pieces of about 1 km.
    line = [[17.0 + 0.01 * i, 63.0] for i in range(7)]
    pieces = tool.pieces(line)
    assert pieces[0][0] == line[0] and pieces[-1][-1] == line[-1]
    assert all(a[-1] == b[0] for a, b in zip(pieces, pieces[1:]))
    assert all(tool.km_between(piece[0], piece[-1]) >= tool.PIECE_KM for piece in pieces[:-1])
    start = datetime(2025, 9, 6, 12, tzinfo=timezone.utc)
    # 12 mm/h for the first hour's twelve steps, nothing after: 12 mm, then still 12 mm.
    frames = [(start + timedelta(minutes=5 * i), np.array([12.0, 0.0])) for i in range(12)]
    assert tool.hourly_sums(frames, start, 2).tolist() == [[12.0, 0.0], [12.0, 0.0]]
    assert tool.wanted({"kind": "road", "type": "tertiary"}) == "road"
    assert tool.wanted({"kind": "road", "type": "unclassified"}) is None
    assert tool.wanted({"kind": "road", "type": "unclassified", "ref": "Y 738"}) == "road"
    assert tool.wanted({"kind": "railway", "type": "rail", "name": "Gådeåtunneln"}) is None


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_a_damage_names_its_own_source_on_the_screens() -> None:
    out = json.loads(run_scenario("import json; from app.backend import routes; print(json.dumps(routes.impacts()))", "kramfors2026"))
    assert {item["source_label"] for item in out} >= {"Tidningen Ångermanland", "Sveriges Radio P4"}
    assert all(item["source"].startswith("Lokala medier") for item in out)
    impacts = [{"time_utc": "2026-08-16T06:00:00Z", "kind": "road", "text": "Väg 855 avstängd", "source_label": "Tidningen Ångermanland"}]
    lines = node("satlog.js", f"satelliteLog({{ routeImpacts: {json.dumps(impacts)} }}, Date.parse('2026-08-16T07:00:00Z'))")
    assert lines[0]["sourceText"] == "Tidningen Ångermanland"
