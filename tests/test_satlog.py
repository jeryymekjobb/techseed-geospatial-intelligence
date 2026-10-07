"""Tests for the satellite log under the satellite monitor (app/frontend/satlog.js), in Node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "satlog.js"
MINUTE = 60000
HOUR = 60 * MINUTE
CLOCK = 1_407_150_000_000  # 2014-08-04T11:00:00Z

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")


def node(expression: str) -> object:
    code = f"const m = require({json.dumps(str(SCRIPT))}); with (m) {{ console.log(JSON.stringify({expression})); }}"
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


def hotspot(moment: str, satellite: str = "SNPP", instrument: str = "VIIRS", frp: float = 1.0) -> dict:
    return {"properties": {"acq_datetime_utc": moment, "satellite": satellite, "instrument": instrument, "frp": frp}}


def test_firms_detections_are_grouped_into_passes_per_satellite() -> None:
    features = [
        hotspot("2014-08-04T01:36:00Z", frp=2.5), hotspot("2014-08-04T01:38:00Z", frp=6.96),
        hotspot("2014-08-04T01:37:00Z", "Aqua", "MODIS", 30.0),
        hotspot("2014-08-04T03:18:00Z", frp=1.0),  # the next orbit, more than 15 minutes later
    ]
    passes = node(f"firmsPasses({json.dumps(features)})")
    assert [(item["satellite"], item["detections"], item["maxFrp"]) for item in passes] == [
        ("SNPP", 2, 6.96), ("Aqua", 1, 30.0), ("SNPP", 1, 1.0)]


def test_the_log_lists_what_happened_up_to_the_clock_newest_first() -> None:
    data = {
        "satellites": [{"name": "Suomi NPP", "instrument": "VIIRS", "passes": [
            {"start": CLOCK - 2 * HOUR, "end": CLOCK - 2 * HOUR + 5 * MINUTE},
            {"start": CLOCK - 2 * MINUTE, "end": CLOCK + 3 * MINUTE},  # going on now: only its entry
            {"start": CLOCK + HOUR, "end": CLOCK + HOUR + 5 * MINUTE},  # ahead of the clock
        ]}],
        "firms": [{"atMs": CLOCK - 2 * HOUR + MINUTE, "satellite": "SNPP", "instrument": "VIIRS", "detections": 154, "maxFrp": 6.96}],
        "scenes": [{"acquired_utc": "2014-08-04T10:06:00Z"}, {"acquired_utc": "2014-09-14T10:00:00Z"}],
        "events": [{"kind": "satcom_failure", "clock_utc": "2014-08-04T10:30:00Z"}, {"kind": "iot", "clock_utc": "2014-08-04T10:40:00Z"}],
    }
    lines = node(f"satelliteLog({json.dumps(data)}, {CLOCK})")
    assert [(line["text"], line["source"]) for line in lines] == [
        ("Suomi NPP (VIIRS) över branden", "computed"),
        ("SATCOM nere – satellitdata köas", "simulated"),
        ("Landsat 8 tar bild över branden", "landsat"),
        ("Suomi NPP (VIIRS) lämnar branden", "computed"),
        ("154 detektioner från Suomi NPP (VIIRS), starkast 7 MW", "firms"),
        ("Suomi NPP (VIIRS) över branden", "computed"),
    ]


def test_the_log_keeps_the_last_day_and_a_few_lines() -> None:
    passes = [{"start": CLOCK - hours * HOUR, "end": CLOCK - hours * HOUR + MINUTE} for hours in (1, 2, 3, 4, 30)]
    lines = node(f"satelliteLog({{satellites: [{{name: 'Aqua', instrument: 'MODIS', passes: {json.dumps(passes)}}}]}}, {CLOCK}, 86400000, 6)")
    assert len(lines) == 6 and lines[0]["atMs"] == CLOCK - HOUR + MINUTE
    assert len(node(f"satelliteLog({{satellites: [{{name: 'Aqua', passes: {json.dumps(passes)}}}]}}, {CLOCK})")) == 8  # the 30 h old pass is out
    assert all(line["atMs"] > CLOCK - 24 * HOUR for line in node(f"satelliteLog({{satellites: [{{name: 'Aqua', passes: {json.dumps(passes)}}}]}}, {CLOCK}, 86400000, 99)"))
    assert node(f"satelliteLog({{}}, {CLOCK})") == []


def test_firms_lines_name_their_year_and_noaa_20() -> None:
    lines = node(f"satelliteLog({{ firms: firmsPasses([{json.dumps(hotspot('2018-07-17T11:20:00Z', 'N20'))}]) }}, "
                 "Date.parse('2018-07-17T12:00:00Z'))")
    assert [(line["text"], line["sourceText"]) for line in lines] == [("1 detektion från NOAA-20 (VIIRS), starkast 1 MW", "FIRMS 2018")]
