"""Tests for EFAS's flow forecasts as issued (tools/fetch_efas_forecasts.py, app/backend/efas.py, hydro.js, satlog.js).
SYNTHETIC grids and flows round Skallböle's 459 m³/s in EFAS's run of 9 August 2023."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tools import fetch_efas_forecasts as fetch
from tools import fetch_scenario

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
RUN = datetime(2023, 8, 9, tzinfo=timezone.utc)
# Three cells by Skallböle (62.4, 17.0): a side stream, the river and one 6 km off.
LATITUDES = [62.39, 62.383, 62.45]
LONGITUDES = [17.0, 16.97, 17.0]
FIELDS = [(RUN, RUN + timedelta(hours=6), [12.0, 459.3, 900.0]), (RUN, RUN + timedelta(hours=12), [11.0, 440.0, 900.0]),
          (RUN + timedelta(days=1), RUN + timedelta(days=1, hours=6), [10.0, 387.2, None])]
SKALLBOLE = {"id": "1650:2", "name": "Skallböle", "latitude": 62.4, "longitude": 17.0}


def test_the_river_s_cell_is_the_one_that_drains_the_most_near_the_station() -> None:
    # The cell 6 km off has more flow, but lies beyond CELL_KM.
    assert fetch.river_cell(LATITUDES, LONGITUDES, FIELDS, 62.4, 17.0) == 1
    assert fetch.river_cell(LATITUDES, LONGITUDES, FIELDS, 60.0, 15.0) is None


def test_each_issue_keeps_its_flows_in_time_order_and_when_it_was_available() -> None:
    [station] = fetch.forecasts(LATITUDES, LONGITUDES, FIELDS, [SKALLBOLE])
    assert station["cell"] == {"latitude": 62.383, "longitude": 16.97, "distance_km": 2.4}
    first, second = station["issues"]
    assert (first["issued_utc"], first["available_utc"]) == ("2023-08-09T00:00:00Z", "2023-08-09T12:00:00Z")
    assert first["values"] == [{"time_utc": "2023-08-09T06:00:00Z", "value": 459.3}, {"time_utc": "2023-08-09T12:00:00Z", "value": 440.0}]
    assert second["values"] == [{"time_utc": "2023-08-10T06:00:00Z", "value": 387.2}]


def test_one_request_asks_for_every_run_ten_days_ahead() -> None:
    payload = fetch.request(date(2023, 8, 5), date(2023, 8, 14), (62.8, 13.5, 62.1, 17.7))
    assert payload["day"] == [f"{day:02d}" for day in range(5, 15)] and payload["time"] == ["00:00"]
    assert payload["leadtime_hour"][0] == "6" and payload["leadtime_hour"][-1] == "240" and len(payload["leadtime_hour"]) == 40
    assert payload["product_type"] == ["high_resolution_forecast"] and payload["area"] == [62.8, 13.5, 62.1, 17.7]


def write_forecasts(directory: Path) -> None:
    [station] = fetch.forecasts(LATITUDES, LONGITUDES, FIELDS, [SKALLBOLE])
    (directory / "forecasts.json").write_text(json.dumps({"source": fetch.ATTRIBUTION, "available_after_hours": 12,
                                                          "stations": [station]}), encoding="utf-8")


def test_the_backend_gives_the_log_each_issue_s_peak_and_the_stations_their_forecasts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import efas, hydro
    write_forecasts(tmp_path)
    monkeypatch.setattr(efas.scenario, "EFAS_DIR", tmp_path)
    efas.data.cache_clear()
    assert efas.issues() == [
        {"issued_utc": "2023-08-09T00:00:00Z", "available_utc": "2023-08-09T12:00:00Z", "station": "Skallböle",
         "peak_value": 459.3, "peak_time_utc": "2023-08-09T06:00:00Z"},
        {"issued_utc": "2023-08-10T00:00:00Z", "available_utc": "2023-08-10T12:00:00Z", "station": "Skallböle",
         "peak_value": 387.2, "peak_time_utc": "2023-08-10T06:00:00Z"}]
    assert efas.layer()["label"] == "EFAS-prognos – information, inte en varning"
    # /api/hydro's station carries its forecasts.
    (tmp_path / "flow-1650.csv").write_text("time_utc,value,quality\n2023-08-09T00:00:00Z,245.9,O\n", encoding="utf-8")
    (tmp_path / "stations.json").write_text(json.dumps({"source": "SMHI", "stations": [{
        "id": "1650:2", "name": "Skallböle", "kind": "flow", "unit": "m³/s", "file": "flow-1650.csv", "latitude": 62.4, "longitude": 17.0,
        "measured_since": "1956-01-01", "earlier_max": {"value": 1050.0, "time_utc": "2000-07-22T00:00:00Z"}}]}), encoding="utf-8")
    monkeypatch.setattr(hydro, "HYDRO_DIR", tmp_path)
    monkeypatch.setattr(hydro, "MODEL_FLOW_DIR", None)
    monkeypatch.setattr(hydro, "SEA_LEVEL_DIR", None)
    hydro.stations.cache_clear()
    [station] = hydro.stations()["stations"]
    hydro.stations.cache_clear(), efas.data.cache_clear()
    assert [issue["issued_utc"] for issue in station["forecasts"]] == ["2023-08-09T00:00:00Z", "2023-08-10T00:00:00Z"]


def test_without_forecasts_nothing_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import efas
    monkeypatch.setattr(efas.scenario, "EFAS_DIR", None)
    efas.data.cache_clear()
    assert (efas.layer(), efas.issues(), efas.by_station()) == (None, [], {})
    efas.data.cache_clear()


def test_the_forecasts_are_an_optional_step_after_the_flows_with_an_ewds_account() -> None:
    plan = {step.key: step for step in fetch_scenario.steps("ljungan-aug2023")}
    order = list(plan)
    assert plan["efas"].optional and plan["efas"].account == "ewds" and order.index("smhi-hydro") < order.index("efas")
    assert order.index("model-flows") < order.index("efas")
    assert "efas" not in [step.key for step in fetch_scenario.steps("flen2019")]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_show_the_latest_forecast_available_by_the_clock_and_the_log_its_peak() -> None:
    [station] = fetch.forecasts(LATITUDES, LONGITUDES, FIELDS, [SKALLBOLE])
    issues = json.dumps(station["issues"])
    code = (f"const h = require({json.dumps(str(FRONTEND / 'hydro.js'))}); const s = require({json.dumps(str(FRONTEND / 'satlog.js'))});"
            f"const f = {issues}; const at = (t) => h.hydroForecast(f, Date.parse(t))?.issued_utc ?? null;"
            "const lines = s.satelliteLog({ flowForecasts: [{ issued_utc: '2023-08-09T00:00:00Z', available_utc: '2023-08-09T12:00:00Z',"
            " station: 'Skallböle', peak_value: 459.3, peak_time_utc: '2023-08-09T06:00:00Z' }] }, Date.parse('2023-08-10T00:00:00Z'));"
            "console.log(JSON.stringify([at('2023-08-09T11:00:00Z'), at('2023-08-09T12:00:00Z'), at('2023-08-11T00:00:00Z'),"
            " h.hydroForecastPeak(f[0]).value, h.hydroForecastPeak(null), lines.map((l) => [l.text, l.spoken, s.SATLOG_SOURCES[l.source]])]));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    # No forecast before it was available; then the newest one.
    assert result[:5] == [None, "2023-08-09T00:00:00Z", "2023-08-10T00:00:00Z", 459.3, None]
    assert result[5] == [["Ny flödesprognos från EFAS: Skallböle högst 459,3 kubikmeter per sekund den 9 augusti",
                          "Ny flödesprognos från EFAS: Skallböle högst 459 kubikmeter per sekund den 9 augusti", "EFAS, modell"]]


def test_the_startup_check_reports_the_forecasts_as_optional(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from tools import startup_check
    settings = SimpleNamespace(TERRAIN_FILE=tmp_path / "terrain.json", TARGETS_FILE=tmp_path / "targets.json", WIND_FILE=None,
                               TLE_DIR=tmp_path / "tle", TLE_FILE_NAME="tle.json", TLE_SATELLITES={}, TILES_FILE="demo.mbtiles",
                               FIRMS_FILES=[], EFAS_DIR=tmp_path / "efas")
    check = next(item for item in startup_check.data_checks(settings, tmp_path) if item.name.endswith("forecasts.json"))
    assert not check.passed and not check.required and "optional" in check.detail
