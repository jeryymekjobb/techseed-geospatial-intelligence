"""Tests for ERA5 sea-source metadata and interpolation outputs."""

from __future__ import annotations

import json
from pathlib import Path

from tools import fetch_era5_sea as era5_sea


def test_main_writes_a_source_sidecar_for_the_interpolated_csv(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "era5-2026-08.nc"
    land = tmp_path / "era5-land.csv"
    land.write_text("latitude,longitude\n", encoding="utf-8")
    monkeypatch.setattr(era5_sea, "download", lambda area, start, end, raw_dir: [raw])
    monkeypatch.setattr(era5_sea, "land_points", lambda path: set(era5_sea.grid_points(1.0, 1.0, 0.0, 2.0)))
    monkeypatch.setattr(era5_sea, "rows_for", lambda path, points, start, end: [])
    output = tmp_path / "era5-sea-test.csv"

    assert era5_sea.main([
        "--area", "1,1,0,2", "--start", "2026-08-01", "--end", "2026-08-02",
        "--land", str(land), "--raw-dir", str(tmp_path / "raw"), "--out", str(output),
    ]) == 0

    source = json.loads(output.with_suffix(".SOURCE.json").read_text(encoding="utf-8"))
    assert source["dataset"] == "reanalysis-era5-single-levels"
    assert source["doi"] == "10.24381/cds.adbb2d47"
    assert source["licence"] == "CC BY 4.0"
    assert "Copernicus Climate Change Service" in source["attribution"]
    assert source["output_area_north_west_south_east"] == [1.0, 1.0, 0.0, 2.0]
    assert source["download_area_north_west_south_east"] == [1.25, 0.75, -0.25, 2.25]
    assert source["land_input"] == land.name and source["raw_files"] == [raw.name]
