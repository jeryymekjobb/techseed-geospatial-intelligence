"""Tests for the screens' MET Norway forecast (app/frontend/met_forecast.js and its log lines in
satlog.js), run with Node.js when it is installed."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.backend import met_forecast as mf
from tests.test_met_forecast import run

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"


def node(expression: str) -> object:
    code = f"const m = require({json.dumps(str(FRONTEND / 'met_forecast.js'))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_panel_draws_the_wind_gust_and_rain_with_the_clock() -> None:
    hours = mf.hourly(run(gust=[6.0] * 10 + [12.0] + [6.0] * 14, rain_acc=[0.0] * 5 + [2.0] * 20))
    svg = node(f"metForecastChart({json.dumps(hours)}, Date.parse('2018-07-17T12:00:00Z'), (ms) => new Date(ms).getUTCHours() === 22 ? 'dag' : null)")
    assert svg.count('class="met-rain"') == 1 and 'class="met-wind"' in svg and 'class="met-gust"' in svg
    assert 'class="rain-now" x1="75"' in svg and ">dag</text>" in svg and "upp till 12 m/s, regn upp till 2 mm/h" in svg
    rows = node("metSummaryRows([{ hours: 6, wind_from: 'SO', wind_ms: 4.25, gust_max_ms: 8, precipitation_mm: 0, humidity_min_pct: 31 }])")
    assert rows == [["6 h", "SO 4,3 m/s, byar 8, regn 0 mm, fukt ned till 31 %"]]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_a_new_forecast_with_news_is_a_log_line_read_aloud() -> None:
    issues = [{"available_utc": "2018-07-17T09:00:00Z", "news": ["Risk för åska om 7 timmar, nya bränder kan tändas"],
               "wind": {"from": "sydost", "ms": 5}},
              {"available_utc": "2018-07-17T15:00:00Z", "news": []},
              {"available_utc": "2018-07-17T21:00:00Z", "news": ["Låg luftfuktighet, ned till 26 procent"], "wind": {"from": "nordost", "ms": 0}}]
    code = (f"const m = require({json.dumps(str(FRONTEND / 'satlog.js'))});"
            f"console.log(JSON.stringify(m.satelliteLog({{ forecastIssues: {json.dumps(issues)} }}, Date.parse('2018-07-17T22:00:00Z'))))")
    lines = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert lines[0]["text"] == "Ny väderprognos: Nästan vindstilla. Låg luftfuktighet, ned till 26 procent"
    lines = lines[1:]
    assert lines == [{"atMs": 1531818000000, "text": "Ny väderprognos: Vind från sydost, 5 meter per sekund. Risk för åska om 7 timmar, nya bränder kan tändas",
                      "source": "metno", "kind": "met_forecast"}]
    assert (FRONTEND / "satlog.js").read_text(encoding="utf-8").count('metno: "MET Norway"') == 1
