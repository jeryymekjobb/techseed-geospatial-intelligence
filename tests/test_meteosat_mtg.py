"""Tests for MTG's Lightning Imager and instability indices (tools/fetch_meteosat_li.py, fetch_meteosat_gii.py,
app/backend/meteosat_li.py, meteosat_gii.py)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.backend import meteosat_gii, meteosat_li, scenario
from tools import fetch_meteosat_gii as gii_tool
from tools import fetch_meteosat_li as li_tool

NAME = "W_XX-EUMETSAT-Darmstadt,IMG+SAT,MTI1+LI-2-LFL--FD--x-x--ARC-x_C_EUMT_20260815161025_L2PF_OPE_20260815160006_20260815161006_N__O_0098_0000"


def test_the_fetch_sources_use_the_display_attributions() -> None:
    assert li_tool.PRODUCT_ATTRIBUTION == meteosat_li.ATTRIBUTION
    assert gii_tool.PRODUCT_ATTRIBUTION == meteosat_gii.ATTRIBUTION


def test_the_lightning_tool_keeps_the_flashes_round_the_area_with_their_time() -> None:
    assert li_tool.sensing_start(NAME) == "2026-08-15T16:00:06Z"
    columns = {"latitude": [62.91, 40.0, None], "longitude": [17.5, 17.5, 17.5], "flash_time": [840124806.4, 840124807.0, 840124808.0]}
    # Seconds since 2000-01-01 as epoch seconds; the one in the south and the one without a position are out.
    assert li_tool.flashes_in(columns, (17.2, 62.6, 18.3, 63.2)) == [[1786809606, 62.91, 17.5]]


def test_a_thunderstorm_is_a_line_when_it_begins_and_when_it_ends() -> None:
    series = [{"time_utc": f"t{index}", "count": count} for index, count in enumerate([0, 4, 12, 30, 8, 5, 2, 0, 11])]
    assert [(item["time_utc"], item["kind"]) for item in meteosat_li.events(series)] == [("t2", "up"), ("t6", "down"), ("t8", "up")]


def test_the_maps_get_the_flashes_of_the_hour_before_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scenario, "MAP_BBOX", (17.2, 62.6, 18.3, 63.2))
    clock = datetime(2026, 8, 15, 17, tzinfo=timezone.utc)
    now = int(clock.timestamp())
    items = ((now - 4000, 62.9, 17.5), (now - 1800, 62.9, 17.5), (now - 60, 63.5, 16.4), (now + 60, 62.9, 17.5))
    shown = meteosat_li.at(clock, items)
    assert [flash["age_min"] for flash in shown["flashes"]] == [30, 1] and shown["in_area"] == 1


def test_the_instability_is_read_every_third_hour_and_classed_by_rule_of_thumb() -> None:
    names = [f"x_OPE_2026081{d}{h:02d}{m:02d}06_2026081{d}{h:02d}{m:02d}06_" for d, h, m in ((5, 0, 0), (5, 0, 10), (5, 1, 0), (5, 3, 0), (5, 3, 10))]
    assert [li_tool.sensing_start(name)[11:16] for name in gii_tool.every_step(names)] == ["00:00", "03:00"]
    assert gii_tool.summary([[63.0, 17.5, 32.5, 1.0], [63.1, 17.6, 28.0, None]]) == {"fields": 2, "k_max": 32.5, "lifted_min": 1.0}
    assert [meteosat_gii.k_class(k) for k in (15, 25, 32.5, 36)] == ["låg", "måttlig", "hög", "mycket hög"]
    times = [{"time_utc": "2026-08-15T06:00:06Z", "k_max": 32.5}, {"time_utc": "2026-08-15T09:00:06Z", "k_max": 34.0},
             {"time_utc": "2026-08-15T12:00:06Z", "k_max": None}, {"time_utc": "2026-08-16T03:00:06Z", "k_max": 31.0}]
    assert [(event["time_utc"][:13], event["class"]) for event in meteosat_gii.events(times)] == [("2026-08-15T06", "hög"), ("2026-08-16T03", "hög")]
