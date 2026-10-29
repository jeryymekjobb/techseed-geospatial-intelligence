"""Tests for the scenario of rain and a storm from the sea at Sundsvall in December 2020 (sundsvall-dec2020)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools import fetch_scenario

ROOT = Path(__file__).resolve().parents[1]


def run_scenario(code: str, name: str) -> str:
    env = {**os.environ, "TECHSEED_SCENARIO": name}
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True, capture_output=True, text=True).stdout


def test_the_scenario_has_the_town_s_gauges_two_level_sensors_and_no_dam() -> None:
    out = run_scenario("from app.backend import scenario; print(sorted(scenario.RAIN_STATIONS.values()), scenario.OVERFLOW_SENSORS, "
                       "[site['site'] for site in scenario.LEVEL_SENSOR_SITES], scenario.DAM)", "sundsvall-dec2020")
    assert out.strip() == ("['Brämön A', 'Bällsta', 'Essvik', 'Fillan', 'Heffners'] True "
                           "['Himlabadet, Sidsjöbäcken', 'Selångersåns utlopp'] None")
    plan = {step.key: step for step in fetch_scenario.steps("sundsvall-dec2020")}
    assert "dam" not in plan and "level-sensors" in plan and "landsat" not in plan and "sentinel2" not in plan
    assert plan["sentinel1-wind"].optional and plan["sentinel1-wind"].account == "cdse"


def test_the_demo_check_expects_rain_without_a_reported_flood() -> None:
    code = "from app.backend import scenario; print(scenario.CHECK_SENSORS, scenario.CHECK_OUTCOME, scenario.CHECK_DETECTION_OUTCOME, sep='|')"
    assert run_scenario(code, "sundsvall-dec2020").strip() == "2/10|Possible flood|Okänd"
