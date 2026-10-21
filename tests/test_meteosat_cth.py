"""Tests for Meteosat's cloud top height (tools/fetch_meteosat_cth.py, app/backend/meteosat_cth.py, app/frontend/meteosat_cth.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.backend import meteosat_cth
from tools import fetch_meteosat_cth as fetch

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "meteosat_cth.js"


def test_only_the_positions_are_turned_by_180_degrees() -> None:
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert fetch.rows(values, 3) == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    assert fetch.rotated(values, 3) == [[9, 8, 7], [6, 5, 4], [3, 2, 1]]


def test_the_cells_in_and_round_the_area_get_their_corners() -> None:
    lats = [[63.0 - 0.2 * row for _ in range(5)] for row in range(5)]
    lons = [[17.0 + 0.4 * column for column in range(5)] for _ in range(5)]
    cells = fetch.cells_in(lats, lons, (17.3, 62.5, 17.9, 62.7), margin=(0.1, 0.5))
    # The border rows and columns have no corners on their outer side and are left out; the margin
    # takes the other nine, of which two lie in the area.
    assert len(cells) == 9 and [(cell["latitude"], cell["longitude"]) for cell in cells if cell["in_area"]] == [(62.6, 17.4), (62.6, 17.8)]
    assert cells[3]["corners"] == [[62.7, 17.2], [62.7, 17.6], [62.5, 17.6], [62.5, 17.2]]


def test_a_quarter_has_the_cloudy_share_and_mean_height_over_the_map_area() -> None:
    assert fetch.quarter([9000.0, None, 7000.0, 12000.0], [True, True, True, False]) == {"cloud_pct": 67, "mean_km": 8.0}
    assert fetch.quarter([None, None], [True, True]) == {"cloud_pct": 0, "mean_km": None}
    assert fetch.time_of("MSG3-SEVI-MSGCLTH-0100-0100-20260815160000.000000000Z-NA") == "2026-08-15T16:00:00Z"


def test_the_log_hears_when_the_tops_pass_8_and_10_km_and_fall_back() -> None:
    def q(time: str, km: float | None) -> dict:
        return {"time_utc": time, "mean_km": km}
    quarters = [q("15:00", 6.3), q("15:30", 8.1), q("15:45", None), q("16:00", 7.5), q("16:15", 10.2), q("17:00", 9.5),
                q("17:15", 10.0), q("18:00", 8.8), q("18:15", 10.1), q("01:00", 7.5), q("01:15", 6.9)]
    # A quarter without a product is skipped; dips of less than a kilometre below a threshold do not
    # count (7.5 after 8.1, 9.5 after 10.2); passing both at once is one line, at the higher; 8.8 leaves 10.
    assert [(e["time_utc"], e["kind"], e["km"]) for e in meteosat_cth.events(quarters)] == [
        ("15:30", "up", 8.0), ("16:15", "up", 10.0), ("18:15", "up", 10.0), ("01:15", "down", 7.0)]


def test_the_layer_gives_heights_in_km(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cth.json"
    path.write_text(json.dumps({"cells": [{"latitude": 62.9, "longitude": 17.7, "in_area": True, "corners": [[0, 0]] * 4}],
                                "quarters": [{"time_utc": "2026-08-15T16:00:00Z", "cloud_pct": 100, "mean_km": 9.0, "heights_m": [9040]}]}),
                    encoding="utf-8")
    monkeypatch.setattr(meteosat_cth, "FILE", path)
    meteosat_cth.data.cache_clear()
    try:
        layer = meteosat_cth.layer()
        assert layer["quarters"][0]["heights_km"] == [9.0] and layer["thresholds_km"] == [8.0, 10.0]
        assert layer["attribution"].startswith("Contains modified EUMETSAT Meteosat product ")
    finally:
        meteosat_cth.data.cache_clear()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_show_the_latest_quarter_in_its_height_s_colour() -> None:
    code = (f"const m = require({json.dumps(str(SCRIPT))});"
            " const q = [{time_utc: '2026-08-15T15:45:00Z'}, {time_utc: '2026-08-15T16:00:00Z'}];"
            " console.log(JSON.stringify([m.cthQuarterAt(q, Date.parse('2026-08-15T15:59:00Z')), m.cthQuarterAt(q, Date.parse('2026-08-15T12:00:00Z')),"
            " m.cthColour(2), m.cthColour(9), m.cthColour(10.9)]));")
    at, before, low, high, top = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert (at, before) == (0, -1) and low == "#d7e3f4" and high == "#5b3fb0" and top == "#3b0f70"
