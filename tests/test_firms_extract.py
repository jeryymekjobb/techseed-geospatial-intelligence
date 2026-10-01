"""Tests for tools/firms_extract.py.

All detections here are SYNTHETIC test rows in the FIRMS archive column layout;
they are not observations.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import firms_extract  # noqa: E402

HEADER = "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight,type"
BBOX = (59.70, 60.10, 15.90, 16.50)


def write(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def synthetic_inputs(tmp_path: Path) -> list[Path]:
    modis = write(tmp_path / "modis.csv", [
        "59.8400,16.2000,330.0,1.0,1.0,2014-07-31,1150,Terra,MODIS,87,6.03,290.0,33.3,D,0",   # kept
        "59.8500,16.2100,310.0,1.0,1.0,2014-08-04,935,Terra,MODIS,20,6.03,290.0,5.0,D,0",     # low confidence
        "60.1370,16.1900,320.0,1.0,1.0,2014-08-04,935,Terra,MODIS,90,6.03,290.0,9.0,D,0",     # outside area
        "59.9000,16.1000,320.0,1.0,1.0,2014-08-04,1113,Aqua,MODIS,95,6.03,290.0,50.0,D,2",    # static source
        "59.9000,16.1000,320.0,1.0,1.0,2014-07-01,1113,Aqua,MODIS,95,6.03,290.0,50.0,D,0",    # outside period
    ])
    viirs = write(tmp_path / "viirs.csv", [
        "59.83685,16.20845,340.0,0.4,0.4,2014-07-31,1244,SNPP,SNPP,h,2,290.0,49.65,D,0",      # kept
        "59.84000,16.21000,300.0,0.4,0.4,2014-08-04,0136,SNPP,SNPP,n,2,280.0,10.5,N,0",       # kept
        "59.84500,16.21500,300.0,0.4,0.4,2014-08-04,0136,SNPP,SNPP,l,2,280.0,1.0,N,0",        # low confidence
    ])
    return [modis, viirs]


def test_filters_and_counts_every_exclusion(tmp_path: Path) -> None:
    metadata = firms_extract.extract(
        synthetic_inputs(tmp_path), tmp_path / "out",
        start=date(2014, 7, 29), end=date(2014, 8, 13), bbox=BBOX,
    )

    assert metadata["counts"] == {
        "input": 8,
        "kept": 3,
        "excluded": {"low_confidence": 2, "not_vegetation_fire_type": 1, "outside_area": 1, "outside_period": 1},
    }
    assert [item["file"] for item in metadata["inputs"]] == ["modis.csv", "viirs.csv"]
    assert all(len(item["sha256"]) == 64 for item in metadata["inputs"])


def test_outputs_use_utc_timestamps_and_wgs84_points(tmp_path: Path) -> None:
    out = tmp_path / "out"
    firms_extract.extract(synthetic_inputs(tmp_path), out, start=date(2014, 7, 29), end=date(2014, 8, 13), bbox=BBOX)

    rows = list(csv.DictReader((out / "hotspots.csv").open(encoding="utf-8")))
    assert [(row["instrument"], row["acq_datetime_utc"]) for row in rows] == [
        ("MODIS", "2014-07-31T11:50:00Z"),
        ("VIIRS", "2014-07-31T12:44:00Z"),
        ("VIIRS", "2014-08-04T01:36:00Z"),
    ]
    features = json.loads((out / "hotspots.geojson").read_text(encoding="utf-8"))["features"]
    assert features[0]["geometry"] == {"type": "Point", "coordinates": [16.2, 59.84]}
    assert features[0]["properties"]["frp"] == 33.3


def test_daily_summary_per_day_and_instrument(tmp_path: Path) -> None:
    out = tmp_path / "out"
    firms_extract.extract(synthetic_inputs(tmp_path), out, start=date(2014, 7, 29), end=date(2014, 8, 13), bbox=BBOX)

    summary = list(csv.DictReader((out / "daily_summary.csv").open(encoding="utf-8")))
    assert [(row["acq_date"], row["instrument"], row["detections"], row["frp_sum_mw"]) for row in summary] == [
        ("2014-07-31", "MODIS", "1", "33.3"),
        ("2014-07-31", "VIIRS", "1", "49.6"),
        ("2014-08-04", "VIIRS", "1", "10.5"),
    ]


def test_filters_can_be_relaxed_from_the_command_line(tmp_path: Path) -> None:
    out = tmp_path / "out"
    inputs = synthetic_inputs(tmp_path)

    assert firms_extract.main([
        *map(str, inputs), "--out", str(out), "--start", "2014-07-29", "--end", "2014-08-13",
        "--bbox", "59.70,60.10,15.90,16.50", "--modis-min-confidence", "0", "--viirs-confidence", "l,n,h",
    ]) == 0

    metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["counts"]["kept"] == 5
    assert metadata["filters"] == {"types": ["0"], "modis_min_confidence": 0, "viirs_confidence": ["h", "l", "n"]}


def test_missing_columns_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "broken.csv"
    path.write_text("latitude,longitude\n59.9,16.2\n", encoding="utf-8")

    try:
        firms_extract.read_detections(path)
    except ValueError as exc:
        assert "missing FIRMS columns" in str(exc)
    else:
        raise AssertionError("missing columns must be rejected")
