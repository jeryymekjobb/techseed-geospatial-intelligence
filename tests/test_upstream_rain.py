"""Tests for the rain upstream in the river, apart from the assessment (fetch_smhi_daily.py --upstream,
daily_rain.upstream_layer, rain.js, satlog.js). SYNTHETIC days at two of Ljungan's stations."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import fetch_scenario

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
STATIONS = [
    {"id": "124300", "name": "Klövsjöhöjden A", "latitude": 62.495, "longitude": 14.154, "days": [
        {"from_utc": "2023-08-06T06:00:00Z", "to_utc": "2023-08-07T06:00:00Z", "mm": 23.1, "quality": "G"},
        {"from_utc": "2023-08-07T06:00:00Z", "to_utc": "2023-08-08T06:00:00Z", "mm": 52.1, "quality": "G"}]},
    {"id": "124400", "name": "Åsarna D", "latitude": 62.659, "longitude": 14.353, "days": [
        {"from_utc": "2023-08-06T06:00:00Z", "to_utc": "2023-08-07T06:00:00Z", "mm": 4.0, "quality": "G"},
        {"from_utc": "2023-08-07T06:00:00Z", "to_utc": "2023-08-08T06:00:00Z", "mm": 41.9, "quality": "G"}]},
]


def test_the_log_s_days_name_the_stations_with_much_rain_wettest_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import daily_rain
    (tmp_path / "stations.json").write_text(json.dumps({"stations": STATIONS}), encoding="utf-8")
    monkeypatch.setattr(daily_rain.scenario, "UPSTREAM_RAIN_DIR", tmp_path)
    monkeypatch.setattr(daily_rain.scenario, "UPSTREAM_RAIN_NOTICE_MM", 20.0)
    layer = daily_rain.upstream_layer()
    assert layer["days"] == [
        {"to_utc": "2023-08-07T06:00:00Z", "stations": [{"name": "Klövsjöhöjden A", "mm": 23.1}]},
        {"to_utc": "2023-08-08T06:00:00Z", "stations": [{"name": "Klövsjöhöjden A", "mm": 52.1}, {"name": "Åsarna D", "mm": 41.9}]}]
    monkeypatch.setattr(daily_rain.scenario, "UPSTREAM_RAIN_DIR", None)
    assert daily_rain.upstream_layer() is None


def test_the_assessment_does_not_count_the_rain_upstream() -> None:
    from app.backend import flood_assessment
    assert "upstream" not in Path(flood_assessment.__file__).read_text(encoding="utf-8")


def test_the_rain_upstream_is_its_own_step_of_the_ljungan_scenario() -> None:
    plan = {step.key: step for step in fetch_scenario.steps("ljungan-aug2023")}
    assert "--upstream" in plan["smhi-daily-upstream"].command and not plan["smhi-daily-upstream"].optional
    assert "smhi-daily-upstream" not in [step.key for step in fetch_scenario.steps("flen2019")]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_panel_shows_each_station_s_day_and_the_log_reads_the_wettest() -> None:
    days = [{"to_utc": "2023-08-08T06:00:00Z", "stations": [{"name": "Klövsjöhöjden A", "mm": 52.1}, {"name": "Åsarna D", "mm": 41.9}]}]
    code = (f"const r = require({json.dumps(str(FRONTEND / 'rain.js'))}); const s = require({json.dumps(str(FRONTEND / 'satlog.js'))});"
            f"const rows = r.upstreamRainRows({json.dumps(STATIONS)}, Date.parse('2023-08-07T12:00:00Z'), Date.parse('2023-08-05T00:00:00Z'));"
            f"const lines = s.satelliteLog({{ upstreamRainDays: {json.dumps(days)} }}, Date.parse('2023-08-08T12:00:00Z'));"
            "console.log(JSON.stringify([rows.map((row) => [row.name, row.day, row.since]), lines.map((l) => [l.text, l.spoken, s.SATLOG_SOURCES[l.source]])]));")
    rows, lines = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    # Only the days that have ended by the clock.
    assert rows == [["Klövsjöhöjden A", 23.1, 23.1], ["Åsarna D", 4.0, 4.0]]
    assert lines == [["Regn uppströms senaste dygnet: Klövsjöhöjden 52,1 millimeter, Åsarna 41,9",
                      "Regn uppströms senaste dygnet: Klövsjöhöjden 52 millimeter, Åsarna 42", "SMHI, uppmätt"]]
