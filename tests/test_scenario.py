"""Tests for the scenario choice (app/backend/scenario.py, app/backend/scenarios/)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.backend import lantmateriet, scenario, server

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python(code: str, scenario_name: str | None) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "TECHSEED_SCENARIO"}
    if scenario_name is not None:
        env["TECHSEED_SCENARIO"] = scenario_name
    return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False)


def test_vastmanland_2014_is_the_default_scenario() -> None:
    result = run_python("from app.backend import scenario; print(scenario.NAME, scenario.DATABASE, scenario.TILES_FILE)", None)
    assert result.returncode == 0 and result.stdout.split() == ["vastmanland2014", "firemap", "vastmanland.mbtiles"]


def test_an_unknown_scenario_stops_with_the_available_ones() -> None:
    result = run_python("from app.backend import scenario", "atlantis")
    assert result.returncode != 0 and "vastmanland2014" in result.stderr


def test_the_scenario_keeps_the_values_of_the_fire_demo() -> None:
    assert scenario.VIEW_BBOX == (59.75, 60.08, 15.85, 16.45)
    assert scenario.MAP_BBOX == (15.5, 59.55, 16.8, 60.3)
    assert scenario.TARGETS_FILE == REPO_ROOT / "osm_data" / "targets-vastmanland.geojson"
    assert scenario.TLE_DIR / scenario.TLE_FILE_NAME == REPO_ROOT / "data" / "tle" / "tle-2014.json"


def test_config_gives_the_screens_the_scenario_texts_camera_and_map_area() -> None:
    config = server.config(lantmateriet.Settings(None, None, None, None, None))
    assert config["scenario"] == "vastmanland2014" and config["title"] == "Skogsbranden i Västmanland 2014"
    assert config["data_label"] == "Historiska data 2014 – uppspelning, inte live"
    assert config["control_label"].startswith("Scenario: WILDFIRE – Västmanland 2014")
    assert config["map_bounds"] == [[59.55, 15.5], [60.3, 16.8]]
    assert config["camera_route"][-1] == {"lon": 16.3, "lat": 59.6, "height": 160_000, "pitch": -60, "seconds": 2.2}
