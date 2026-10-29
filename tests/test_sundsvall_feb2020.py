"""Tests for the scenario of high sea and rain on snow at Sundsvall in February 2020 (sundsvall-feb2020)."""

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


def test_without_the_municipality_s_rain_gauges_there_are_no_overflow_sensors() -> None:
    assert run_scenario("from app.backend import scenario; print(scenario.OVERFLOW_SENSORS, scenario.RAIN_STATIONS)", "sundsvall-feb2020").split(
        maxsplit=1) == ["False", "{'127130': 'Brämön A'}\n"]
    assert run_scenario("from app.backend import scenario; print(scenario.OVERFLOW_SENSORS)", "sundsvall2026").strip() == "True"


def test_the_scenario_fetches_its_own_data_and_shares_sundsvall_s_map() -> None:
    plan = {step.key: step for step in fetch_scenario.steps("sundsvall-feb2020")}
    assert {"smhi-sea-level", "smhi-daily", "model-flows", "sentinel1", "landsat", "sentinel2"} <= set(plan)
    assert "dam" not in plan and "level-sensors" in plan
    assert plan["sentinel1-wind"].optional and plan["sentinel1-wind"].account == "cdse"


def test_the_harbour_s_sensors_follow_spikarna_and_alarm_at_the_warning_s_lower_bound() -> None:
    out = run_scenario("from app.backend import scenario; print(scenario.LEVEL_ALARM_LEVEL, scenario.SEA_LEVEL_STORM_CM, "
                       "sorted({site['station'] for site in scenario.LEVEL_SENSOR_SITES}))", "sundsvall-feb2020")
    assert out.strip() == "81.0 81.0 ['sea-2061']"


def test_the_demo_check_expects_what_the_storm_without_a_documented_flood_gives() -> None:
    code = "from app.backend import scenario; print(scenario.CHECK_SENSORS, scenario.CHECK_OUTCOME, scenario.CHECK_DETECTION_OUTCOME, sep='|')"
    assert run_scenario(code, "sundsvall-feb2020").strip() == "3/3|Possible flood|Okänd"
    # Scenarios that do not set it keep the flood the sequence has always ended with.
    assert run_scenario(code, "sundsvall2026").strip().endswith("|Översvämning trolig")
