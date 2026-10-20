"""Tests for LSA SAF's fire risk (tools/fetch_meteosat_frm.py, app/backend/meteosat_frm.py, app/frontend/meteosat_frm.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.backend import meteosat_frm
from tools import fetch_meteosat_frm as fetch

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "meteosat_frm.js"


def test_the_tool_asks_for_the_map_valid_at_the_start_and_every_later_day() -> None:
    days = fetch.days(datetime(2014, 7, 31, tzinfo=timezone.utc), datetime(2014, 8, 15, tzinfo=timezone.utc))
    # The map valid at the start of the playback is the day before's, until noon.
    assert days[0] == date(2014, 7, 30) and days[-1] == date(2014, 8, 14) and len(days) == 16
    assert fetch.days(datetime(2014, 7, 31, 13, tzinfo=timezone.utc), datetime(2014, 8, 1, 12, 30, tzinfo=timezone.utc)) == [
        date(2014, 7, 31), date(2014, 8, 1)]
    assert fetch.url(date(2014, 8, 4)).endswith("/FRMv3/NETCDF/2014/08/04/NETCDF4_LSASAF_MSG_FRMv3-ERA5_MSG-Disk_201408040000.nc")


def test_the_tool_keeps_the_cells_inside_the_area_with_their_values() -> None:
    assert fetch.window([60.1, 60.05, 60.0, 59.95, 59.9], 59.92, 60.06) == slice(1, 4)
    assert fetch.window([15.9, 16.0, 16.1], 16.5, 16.8) == slice(0, 0)
    assert fetch.scaled([[2510, -8000], [0, 4410]], 0.01, -8000, 1) == [[25.1, None], [0.0, 44.1]]
    assert fetch.scaled([[3, -8000]], 1.0, -8000, 0) == [[3, None]]


def grid_file(tmp_path: Path) -> Path:
    def day(when: str, risks: list[list[int]], fwi: float) -> dict:
        return {"date": when, "valid_utc": f"{when}T12:00:00Z", "risk": risks, "fwi": [[fwi, fwi], [fwi, fwi]],
                "ffmc": [[90.0, 90.0], [90.0, 90.0]], "dc": [[380, 380], [380, 380]]}
    path = tmp_path / "frm.json"
    path.write_text(json.dumps({"cell_deg": 0.05, "latitudes": [59.9, 59.85], "longitudes": [16.15, 16.2], "days": [
        day("2014-08-02", [[2, 2], [2, 2]], 17.5), day("2014-08-03", [[1, 3], [1, 1]], 3.2),
        day("2014-08-04", [[3, 3], [3, 3]], 25.1), day("2014-08-05", [[3, 3], [3, 3]], 20.0)]}), encoding="utf-8")
    return path


def test_the_log_gets_the_first_class_at_the_fire_and_each_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(meteosat_frm, "FILE", grid_file(tmp_path))
    meteosat_frm.grid.cache_clear()
    try:
        series = meteosat_frm.at_fire(meteosat_frm.grid(), 59.89, 16.16)
        assert [day["risk"] for day in series] == [2, 1, 3, 3]
        assert [(change["date"], change["name"], change["direction"]) for change in meteosat_frm.changes(series)] == [
            ("2014-08-02", "måttlig", "start"), ("2014-08-03", "låg", "down"), ("2014-08-04", "hög", "up")]
        layer = meteosat_frm.layer()
        assert layer["label"] == meteosat_frm.LABEL and layer["attribution"].startswith("Contains modified EUMETSAT Meteosat product ")
        assert len(layer["days"]) == len(layer["at_fire"]) == 4
        monkeypatch.setattr(meteosat_frm, "FILE", tmp_path / "missing.json")
        meteosat_frm.grid.cache_clear()
        assert meteosat_frm.layer() is None
    finally:
        meteosat_frm.grid.cache_clear()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_show_the_latest_map_valid_at_the_clock() -> None:
    code = (f"const m = require({json.dumps(str(SCRIPT))});"
            " const days = [{valid_utc: '2014-08-03T12:00:00Z', risk: [[1, null]], fwi: [[3.2, null]]},"
            " {valid_utc: '2014-08-04T12:00:00Z', risk: [[3, 4]], fwi: [[25.1, 30]]}];"
            " const info = {cell_deg: 0.05, latitudes: [59.9], longitudes: [16.15, 16.2], days};"
            " const names = {1: 'låg', 3: 'hög'};"
            " console.log(JSON.stringify([m.frmDayAt(days, Date.parse('2014-08-04T11:59:00Z')), m.frmDayAt(days, Date.parse('2014-08-04T12:00:00Z')),"
            " m.frmDayAt(days, Date.parse('2014-08-01T00:00:00Z')), m.frmCells(info, 0).length, m.frmCells(info, 1)[1],"
            " m.frmText({risk: 3, fwi: 25.1}, names, '4 aug. 14:00'), m.frmText(undefined, names, '')]));")
    before, at, none, cells, cell, text, empty = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert (before, at, none, cells) == (0, 1, -1, 1)
    assert cell == {"south": pytest.approx(59.875), "north": pytest.approx(59.925), "west": pytest.approx(16.175), "east": pytest.approx(16.225), "risk": 4, "fwi": 30}
    assert text == "hög, FWI 25 (gäller 4 aug. 14:00; Meteosat och ERA5)" and empty == "ingen karta ännu"
