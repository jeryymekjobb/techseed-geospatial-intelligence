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
    assert "dam" not in plan and "level-sensors" not in plan
