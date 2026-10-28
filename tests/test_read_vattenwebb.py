"""Tests for SMHI's modelled flows from Vattenwebb (tools/read_vattenwebb.py, hydro.model_flows, hydro.js).
SYNTHETIC rows in the layout of Vattenwebb's Excel sheets."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from app.backend import hydro
from tools import read_vattenwebb as read

HYDRO_JS = Path(__file__).resolve().parents[1] / "app" / "frontend" / "hydro.js"
# Excel's day numbers: 45139 is 2023-08-01, 43227 is 2018-05-07, 45658 is 2025-01-01.
SHEETS = {
    "Information": [["Vattenwebb version", "release_autumn_2025-2"], ["Hype modellversion", "s-hype2022_version_2022_1.1.1"]],
    "Områdesinformation": [
        ["SUBID", 12849.0, "Sjö och vattendrag", 0.02], ["Namn", "Selångersån", "Skog", 0.6],
        ["Utloppspunkt (SWEREF99)", "6920115, 619675", "Myrmark", 0.03],
        ["Total vattenföring [m³/s]", "Total stationskorrigerad vattenföring [m³/s]"],
        ["HQ2", 29.4, 29.4], ["HQ5", 43.6, 43.6], ["MHQ", 32.0, 32.0], ["MQ", 4.7, 4.7],
        ["Namn", "Hela avrinningsområdet"],
    ],
    "Dygnsvärden": [["", "Total vattenföring [m³/s]"], [43227.0, 64.27, 64.27], [45139.0, 2.2, 2.2], [45140.0, 6.0, 6.0],
                    ['Senare värden finns i fliken "Dygnsuppdaterade värden"', "", ""]],
    "Dygnsuppdaterade värden": [[45658.0, 1.5, 1.5]],
}


def test_sweref99tm_points_become_the_same_latitude_and_longitude_as_gdal() -> None:
    # gdaltransform -s_srs EPSG:3006 -t_srs EPSG:4326, run 2026-10-28.
    for (northing, easting), (longitude, latitude) in (((6920115, 619675), (17.3151019602, 62.3930903005)),
                                                       ((6580822, 674032), (18.0591897364, 59.3302312261))):
        lat, lon = read.sweref99tm_to_wgs84(northing, easting)
        assert abs(lat - latitude) < 1e-7 and abs(lon - longitude) < 1e-7


def test_a_station_keeps_the_period_s_days_the_earlier_highest_and_the_statistics() -> None:
    entry, days = read.station("12849", "Selångersån", SHEETS, date(2023, 8, 1), date(2023, 8, 21))
    assert days == [(date(2023, 8, 1), 2.2), (date(2023, 8, 2), 6.0)]
    assert entry["earlier_max"] == {"value": 64.27, "time_utc": "2018-05-07T00:00:00Z"} and entry["modelled_since"] == "2018-05-07"
    # The area's own name, not the whole catchment's further down the sheet.
    assert entry["area_name"] == "Selångersån" and entry["statistics"] == {"HQ2": 29.4, "HQ5": 43.6, "MHQ": 32.0, "MQ": 4.7}
    assert (round(entry["latitude"], 3), round(entry["longitude"], 3)) == (62.393, 17.315)
    assert entry["model"]["Hype modellversion"] == "s-hype2022_version_2022_1.1.1"
    # The daily-updated values follow the archive.
    assert read.daily_flows(SHEETS)[-1] == (date(2025, 1, 1), 1.5)


def test_the_backend_gives_the_modelled_flows_as_daily_modelled_stations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "model-flow-12849.csv").write_text("time_utc,value\n2023-08-01T00:00:00Z,2.2\n", encoding="utf-8")
    (tmp_path / "stations.json").write_text(json.dumps({"source": "SMHI Vattenwebb", "stations": [{
        "subid": "12849", "name": "Selångersån", "kind": "flow", "unit": "m³/s", "file": "model-flow-12849.csv",
        "latitude": 62.393, "longitude": 17.315, "modelled_since": "2010-01-01", "statistics": {"HQ2": 29.4},
        "earlier_max": {"value": 64.27, "time_utc": "2018-05-07T00:00:00Z"}}]}), encoding="utf-8")
    monkeypatch.setattr(hydro, "MODEL_FLOW_DIR", tmp_path)
    monkeypatch.setattr(hydro, "HYDRO_DIR", None)
    monkeypatch.setattr(hydro, "SEA_LEVEL_DIR", None)
    hydro.stations.cache_clear()
    result = hydro.stations()
    hydro.stations.cache_clear()
    station = result["stations"][0]
    assert result["source"] == "SMHI Vattenwebb"
    assert (station["id"], station["modelled"], station["daily"], station["measured_since"]) == ("model-12849", True, True, "2010-01-01")
    assert station["observations"] == [{"time_utc": "2023-08-01T00:00:00Z", "value": 2.2}] and station["statistics"] == {"HQ2": 29.4}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_name_the_return_period_and_a_daily_flow_s_date() -> None:
    statistics = {"HQ2": 29.4, "HQ5": 43.6, "HQ10": 53.0, "HQ25": 64.9, "HQ50": 73.7}
    code = (f"const m = require({json.dumps(str(HYDRO_JS))}); const s = {json.dumps(statistics)};"
            "console.log(JSON.stringify([m.hydroReturnPeriod(s, 25.4), m.hydroReturnPeriod(s, 43.6), m.hydroReturnPeriod(s, 64.3),"
            " m.hydroReturnPeriod(s, 80), m.hydroReturnPeriod(null, 80), m.hydroReturnPeriod(s, undefined),"
            " m.hydroWhen('flow', '2023-08-14T00:00:00Z', () => 'tid', true), m.hydroWhen('flow', '2023-08-14T00:00:00Z', () => 'tid')]));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert result == [None, 5, 10, 50, None, None, "14 aug 2023", "tid"]
