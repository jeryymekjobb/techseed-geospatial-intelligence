"""Tests for SMHI's radar as rain (tools/fetch_smhi_radar.py, app/backend/radar.py, rain.js). SYNTHETIC values."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tools import fetch_smhi_radar as radar

RAIN_JS = Path(__file__).resolve().parents[1] / "app" / "frontend" / "rain.js"


def test_sweref99_tm_matches_gdal_for_sundsvall() -> None:
    north, east = radar.sweref99tm(np.array([62.3908, 62.15]), np.array([17.3069, 16.9]))
    # gdaltransform -s_srs EPSG:4326 -t_srs EPSG:3006
    assert np.allclose(east, [619260.25, 599017.01], atol=0.05) and np.allclose(north, [6919844.80, 6892342.28], atol=0.05)


def test_pixel_values_become_rain_in_smhi_s_classes() -> None:
    values = np.array([0, 255, 80, 139, 175, 220], dtype=np.uint8)  # no echo, no data, 2 dBZ, 25.6, 40, 58 dBZ
    rate = radar.rain_rate(values)
    assert math.isnan(rate[0]) and math.isnan(rate[1]) and math.isnan(rate[2])  # under 5 dBZ is no rain
    assert rate[3] == pytest.approx(1.45, abs=0.05) and rate[4] == pytest.approx(11.5, abs=0.2) and rate[5] > 50
    rgba = radar.colours(rate)
    assert rgba[0][3] == 0 and rgba[2][3] == 0  # transparent without rain
    assert [tuple(rgba[i][:3]) for i in (3, 4, 5)] == [(61, 143, 217), (18, 63, 140), (122, 31, 162)]  # moderate, heavy, cloudburst


def test_a_radar_file_s_name_gives_its_time() -> None:
    assert radar.moment_of("radar_2608160600.tif").isoformat() == "2026-08-16T06:00:00+00:00"
    assert radar.moment_of("readme.txt") is None


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_frame_shown_is_the_latest_up_to_the_clock_and_not_too_old() -> None:
    frames = [{"time_utc": f"2026-08-16T06:{minute:02d}:00Z", "url": str(minute)} for minute in (0, 10, 20)]
    code = (f"const m = require({json.dumps(str(RAIN_JS))}); const f = {json.dumps(frames)};"
            "console.log(JSON.stringify(['2026-08-16T05:59:00Z', '2026-08-16T06:15:00Z', '2026-08-16T06:40:00Z', '2026-08-16T06:41:00Z']"
            ".map((t) => (m.radarFrameAt(f, Date.parse(t), 10) || {url: null}).url)));")
    result = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert result == [None, "10", "20", None]


def test_the_radar_frames_are_listed_and_served_and_nothing_else(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import radar as layer
    monkeypatch.setattr(layer, "RADAR_DIR", tmp_path)
    assert layer.layer() is None
    (tmp_path / "radar-20260816T0600.png").write_bytes(b"\x89PNG")
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    (tmp_path / "SOURCE.json").write_text(json.dumps({
        "bounds_west_south_east_north": [16.9, 62.15, 17.8, 62.62], "step_minutes": 10, "attribution": "SMHI",
        "frames": [{"time_utc": "2026-08-16T06:00:00Z", "file": "radar-20260816T0600.png"}]}), encoding="utf-8")
    info = layer.layer()
    assert info["bounds"] == [[62.15, 16.9], [62.62, 17.8]] and info["frames"] == [{"time_utc": "2026-08-16T06:00:00Z", "url": "/radar/radar-20260816T0600.png"}]
    assert layer.image("radar-20260816T0600.png") == b"\x89PNG"
    assert layer.image("secret.txt") is None and layer.image("../SOURCE.json") is None
