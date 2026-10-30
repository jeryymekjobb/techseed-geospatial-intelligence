"""Tests for dragging the clock's line in the panel's time charts (app/frontend/chart_clock.js,
panel.js setupClockDrag)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
START = "Date.parse('2026-08-15T22:00:00Z')"
END = "Date.parse('2026-08-18T00:00:00Z')"


def time_at(x: float) -> str:
    code = (f"const m = require({json.dumps(str(FRONTEND / 'chart_clock.js'))});"
            f"console.log(JSON.stringify(m.chartTimeAt({x}, 300, {START}, {END})));")
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_a_point_in_a_chart_is_a_time_within_the_playback() -> None:
    assert time_at(0) == "2026-08-15T22:00:00.000Z"
    assert time_at(150) == "2026-08-16T23:00:00.000Z"
    assert time_at(300) == "2026-08-18T00:00:00.000Z"
    # Dragged past the chart's ends, the clock stops at the playback's start and end.
    assert time_at(-40) == "2026-08-15T22:00:00.000Z" and time_at(340) == "2026-08-18T00:00:00.000Z"


def test_the_charts_that_drag_the_clock_draw_its_line_and_load_the_helper() -> None:
    panel = (FRONTEND / "panel.js").read_text(encoding="utf-8")
    for chart in ("rain-chart", "cth-chart", "clm-chart", "hydro-chart", "timeline"):
        assert f'"{chart}"' in panel
    assert "if (!state.clockDrag) setClock(" in panel
    for page in ("index.html", "3d.html"):
        html = (FRONTEND / page).read_text(encoding="utf-8")
        assert html.index('src="/chart_clock.js"') < html.index('src="/panel.js"')
