"""Tests for Sentinel-1's wind over the sea (tools/netcdf3.py, tools/fetch_sentinel1_wind.py, sentinel1_wind.py,
wind_barbs.js, satlog.js). SYNTHETIC grids round the Sundsvall bay; the values are made up."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from tools import fetch_scenario
from tools import fetch_sentinel1_wind as fetch
from tools.netcdf3 import NetCDF3

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
BBOX = (16.9, 62.15, 17.8, 62.62)


def classic_netcdf(variables: dict[str, np.ndarray]) -> bytes:
    """A classic NetCDF file (format 1) with 2-D variables of one shape, each with a units attribute."""
    def name(text: str) -> bytes:
        raw = text.encode()
        return struct.pack(">I", len(raw)) + raw + b"\0" * (-len(raw) % 4)
    kinds = {np.dtype(">f4"): 5, np.dtype(">i1"): 1}
    rows, columns = next(iter(variables.values())).shape
    header = b"CDF\x01" + struct.pack(">I", 0)
    header += struct.pack(">II", 10, 2) + name("y") + struct.pack(">I", rows) + name("x") + struct.pack(">I", columns)
    header += struct.pack(">II", 0, 0)
    entries = []
    for key, values in variables.items():
        attribute = name("units") + struct.pack(">II", 2, 1) + b"m\0\0\0"
        entries.append((name(key) + struct.pack(">III", 2, 0, 1) + struct.pack(">II", 12, 1) + attribute
                        + struct.pack(">II", kinds[values.dtype], values.nbytes + (-values.nbytes % 4)), values))
    header += struct.pack(">II", 11, len(entries))
    size = len(header) + sum(len(entry) + 4 for entry, _ in entries)
    body = b""
    for entry, values in entries:
        header_entry = entry + struct.pack(">I", size + len(body))
        header += header_entry
        raw = values.tobytes()
        body += raw + b"\0" * (-len(raw) % 4)
    return header + body


def grid() -> NetCDF3:
    latitude = np.array([[62.3, 62.3, 62.3], [62.4, 62.4, 62.4], [62.9, 62.9, 62.9]], dtype=">f4")
    longitude = np.array([[17.4, 17.5, 17.6], [17.4, 17.5, 17.6], [17.4, 17.5, 17.6]], dtype=">f4")
    return NetCDF3(classic_netcdf({
        "owiLat": latitude, "owiLon": longitude,
        "owiWindSpeed": np.array([[12.6, 11.0, -999.0], [13.2, 12.0, 9.0], [5.0, 5.0, 5.0]], dtype=">f4"),
        "owiWindDirection": np.array([[155.0, 150.0, 0.0], [160.0, 140.0, 359.6], [10.0, 10.0, 10.0]], dtype=">f4"),
        "owiMask": np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=">i1"),
        "owiWindQuality": np.array([[0, 1, 0], [2, 0, 3], [0, 0, 0]], dtype=">i1"),
    }))


def test_the_reader_reads_a_classic_netcdf_file_s_arrays_and_attributes() -> None:
    read = grid()
    assert read.array("owiWindSpeed").shape == (3, 3) and float(read.array("owiWindSpeed")[1, 0]) == pytest.approx(13.2)
    assert int(read.array("owiMask")[1, 1]) == 1 and read.variables["owiLat"][3]["units"] == "m"
    with pytest.raises(ValueError):
        NetCDF3(b"\x89HDF\r\n")


def test_only_valid_sea_cells_in_the_map_area_of_usable_quality_are_kept() -> None:
    # Left out: no wind (-999), land (mask 1), poor quality (3) and the row outside the map area.
    assert fetch.wind_points(grid(), BBOX, step=1) == [[62.3, 17.4, 12.6, 155], [62.3, 17.5, 11.0, 150], [62.4, 17.4, 13.2, 160]]
    assert fetch.wind_points(grid(), BBOX, step=2) == [[62.3, 17.4, 12.6, 155]]


def test_a_pass_has_its_time_satellite_middle_and_strongest_wind_and_mean_direction() -> None:
    name = "S1A_IW_OCN__2SDV_20230809T050638_20230809T050703_049794_05FCF7_3483.SAFE"
    assert fetch.sensing_time(name) == datetime(2023, 8, 9, 5, 6, 38, tzinfo=timezone.utc)
    assert fetch.mean_direction([350, 10]) == 0 and fetch.mean_direction([150, 160]) == 155
    item = fetch.summary(name, fetch.wind_points(grid(), BBOX, step=1))
    assert (item["time_utc"], item["satellite"], item["median_ms"], item["max_ms"], item["from_deg"]) == (
        "2023-08-09T05:06:38Z", "Sentinel-1A", 12.6, 13.2, 155)


def test_the_catalogue_is_asked_for_ocn_products_over_the_map_area_in_the_playback() -> None:
    url = fetch.query(BBOX, datetime(2023, 8, 5, tzinfo=timezone.utc), datetime(2023, 8, 18, tzinfo=timezone.utc))
    assert "_OCN_" in url and "2023-08-05T00%3A00%3A00.000Z" in url and "POLYGON%28%2816.9+62.15" in url


def test_the_backend_names_where_the_wind_blew_from(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import sentinel1_wind
    (tmp_path / "wind.json").write_text(json.dumps({"source": fetch.ATTRIBUTION, "passes": [
        {"time_utc": "2023-08-09T05:06:38Z", "satellite": "Sentinel-1A", "median_ms": 12.6, "max_ms": 13.2, "from_deg": 155,
         "points": [[62.3, 17.4, 12.6, 155]]}]}), encoding="utf-8")
    monkeypatch.setattr(sentinel1_wind.scenario, "SENTINEL1_WIND_DIR", tmp_path)
    sentinel1_wind.data.cache_clear()
    layer = sentinel1_wind.layer()
    assert layer["label"] == "Havsvind (Sentinel-1)" and layer["passes"][0]["from_words"] == "sydost"
    monkeypatch.setattr(sentinel1_wind.scenario, "SENTINEL1_WIND_DIR", None)
    sentinel1_wind.data.cache_clear()
    assert sentinel1_wind.layer() is None


def test_the_wind_is_an_optional_step_with_a_copernicus_data_space_account() -> None:
    plan = {step.key: step for step in fetch_scenario.steps("ljungan-aug2023")}
    assert plan["sentinel1-wind"].optional and plan["sentinel1-wind"].account == "cdse"
    assert "sentinel1-wind" not in [step.key for step in fetch_scenario.steps("flen2019")]


def test_the_startup_check_reports_the_wind_as_optional(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from tools import startup_check
    settings = SimpleNamespace(TERRAIN_FILE=tmp_path / "terrain.json", TARGETS_FILE=tmp_path / "targets.json", WIND_FILE=None,
                               TLE_DIR=tmp_path / "tle", TLE_FILE_NAME="tle.json", TLE_SATELLITES={}, TILES_FILE="demo.mbtiles",
                               FIRMS_FILES=[], SENTINEL1_WIND_DIR=tmp_path / "wind")
    check = next(item for item in startup_check.data_checks(settings, tmp_path) if item.name.endswith("wind.json"))
    assert not check.passed and not check.required and "optional" in check.detail


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_maps_show_a_pass_for_some_hours_and_the_log_says_what_it_measured() -> None:
    passes = [{"time_utc": "2023-08-09T05:06:38Z", "satellite": "Sentinel-1A", "median_ms": 12.6, "max_ms": 13.2, "from_words": "sydost"},
              {"time_utc": "2023-08-09T16:22:38Z", "satellite": "Sentinel-1A", "median_ms": 7.5, "max_ms": 8.7, "from_words": "sydost"}]
    code = (f"const w = require({json.dumps(str(FRONTEND / 'wind_barbs.js'))}); const s = require({json.dumps(str(FRONTEND / 'satlog.js'))});"
            f"const p = {json.dumps(passes)}; const at = (t) => w.sentinel1WindPass(p, Date.parse(t), 12)?.time_utc ?? null;"
            "const lines = s.satelliteLog({ seaWindPasses: [p[0]] }, Date.parse('2023-08-09T06:00:00Z'));"
            "console.log(JSON.stringify([at('2023-08-09T05:00:00Z'), at('2023-08-09T12:00:00Z'), at('2023-08-09T17:00:00Z'),"
            " at('2023-08-10T05:00:00Z'), lines.map((l) => [l.text, l.spoken, s.SATLOG_SOURCES[l.source]])]));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    # Nothing before the first pass or more than 12 hours after the latest.
    assert result[:4] == [None, "2023-08-09T05:06:38Z", "2023-08-09T16:22:38Z", None]
    assert result[4] == [["Sentinel-1A mätte vinden över havet: omkring 12,6 meter per sekund från sydost, som mest 13,2",
                          "Sentinel-1A mätte vinden över havet: omkring 13 meter per sekund från sydost", "Sentinel-1, uppmätt"]]
