"""Tests for the 2014 satellites: /api/satellites with and without fetched elements,
and a check of the whole chain against FIRMS - the satellite each detection names
must have passed within its instrument's swath of the detection, by the same orbit
code the globe uses (app/frontend/orbits.js with satellite.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from app.backend import lantmateriet, satellites, server

FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
SATELLITE_JS = FRONTEND / "vendor" / "satellite.js-7.1.0"
# Half the swath: MODIS 2330 km, VIIRS 3040 km across.
HALF_SWATH_KM = {"MODIS": 1165.0, "VIIRS": 1520.0}
NORAD = {"Aqua": "27424", "Terra": "25994", "SNPP": "37849"}
# FIRMS gives the start of the granule (MODIS 5 min, VIIRS about 1.5 min), to the minute.
WINDOW_S = (-60, 360)


@pytest.fixture()
def base_url():
    handler = type("TestHandler", (server.Handler,), {"settings": lantmateriet.Settings(None, None, None, None)})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_without_fetched_elements_there_are_no_satellites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(satellites, "TLE_FILE", tmp_path / "missing.json")
    satellites.satellites.cache_clear()
    try:
        result = satellites.satellites()
        assert result["available"] is False and result["satellites"] == [] and "fetch_tle_history" in result["note"]
    finally:
        satellites.satellites.cache_clear()


def test_the_endpoint_gives_the_elements_with_their_role_and_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    element = {"epoch_utc": "2014-07-31T00:00:00Z", "line1": "1" * 69, "line2": "2" * 69}
    (tmp_path / "tle-2014.json").write_text(json.dumps({"satellites": {
        "37849": {"name": "Suomi NPP", "elements": [element]},
        "39084": {"name": "Landsat 8", "elements": []},
    }}), encoding="utf-8")
    (tmp_path / "SOURCE.json").write_text(json.dumps({"fetched_utc": "2026-10-05T08:08:00Z"}), encoding="utf-8")
    monkeypatch.setattr(satellites, "TLE_FILE", tmp_path / "tle-2014.json")
    monkeypatch.setattr(satellites, "SOURCE_FILE", tmp_path / "SOURCE.json")
    satellites.satellites.cache_clear()
    try:
        with urlopen(f"{base_url}/api/satellites", timeout=10) as response:
            result = json.loads(response.read())
        with urlopen(f"{base_url}/api/config", timeout=10) as response:
            assert json.loads(response.read())["layers"]["satellites"] is True
    finally:
        satellites.satellites.cache_clear()
    assert result["available"] and result["label"] == satellites.LABEL
    assert result["source"] == "Space-Track.org (gp_history), hämtad 2026-10-05T08:08:00Z"
    assert result["satellites"] == [{  # Landsat 8 without elements is left out
        "norad": "37849", "name": "Suomi NPP", "firms": "SNPP", "instrument": "VIIRS",
        "role": "FIRMS-detektioner (VIIRS)", "elements": [element],
    }]


CHECK = """
import * as lib from "SATELLITE_JS/index.js";
import { createRequire } from "module";
import fs from "fs";
const require = createRequire(import.meta.url);
const orbits = require("ORBITS");
const { satellites, detections, norad, window, shiftMinutes } = JSON.parse(fs.readFileSync(0, "utf8"));
const result = {};
for (const item of detections) {
  const start = new Date(item.acq_datetime_utc).getTime() + shiftMinutes * 60000;
  let best = { km: Infinity, offset_s: null };
  for (let offset = window[0]; offset <= window[1]; offset += 10) {
    const point = orbits.subpoint(lib, satellites[norad[item.satellite]].elements, new Date(start + offset * 1000));
    const km = orbits.groundDistanceKm(point.latitude, point.longitude, item.latitude, item.longitude);
    if (km < best.km) best = { km, offset_s: offset };
  }
  (result[item.satellite] ||= []).push(best);
}
console.log(JSON.stringify(result));
"""


def closest_passes(tmp_path: Path, shift_minutes: int) -> dict[str, list[dict]]:
    # satellite.js ships ES modules without a package.json; a copy marked as a module runs in Node.
    copy = tmp_path / "satellite.js"
    if not copy.exists():
        shutil.copytree(SATELLITE_JS, copy)
        (copy / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    script = CHECK.replace("SATELLITE_JS", copy.as_posix()).replace("ORBITS", (FRONTEND / "orbits.js").as_posix())
    payload = {
        "satellites": json.loads(satellites.TLE_FILE.read_text(encoding="utf-8"))["satellites"],
        "detections": [{key: item[key] for key in ("satellite", "acq_datetime_utc", "latitude", "longitude")} for item in server.detections()],
        "norad": NORAD, "window": WINDOW_S, "shiftMinutes": shift_minutes,
    }
    run = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload),
                         capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


needs_orbits = pytest.mark.skipif(
    shutil.which("node") is None or not SATELLITE_JS.is_dir() or not satellites.TLE_FILE.is_file(),
    reason="needs Node.js, satellite.js (tools/fetch_web_vendor.py) and data/tle/ (tools/fetch_tle_history.py)",
)


@needs_orbits
def test_every_detection_lies_within_the_swath_of_the_satellite_that_made_it(tmp_path: Path) -> None:
    passes = closest_passes(tmp_path, 0)
    instruments = {"Aqua": "MODIS", "Terra": "MODIS", "SNPP": "VIIRS"}
    assert sorted(passes) == ["Aqua", "SNPP", "Terra"]
    assert sum(len(items) for items in passes.values()) == len(server.detections())
    for name, items in passes.items():
        farthest = max(item["km"] for item in items)
        assert farthest <= HALF_SWATH_KM[instruments[name]], (name, farthest)
        # The closest approach falls inside the granule, not at the edge of the search window.
        assert all(WINDOW_S[0] < item["offset_s"] < WINDOW_S[1] for item in items), name


@needs_orbits
def test_the_check_tells_a_wrong_time_apart(tmp_path: Path) -> None:
    # Three quarters of an hour later the satellites are on the other side of the Earth.
    passes = closest_passes(tmp_path, 45)
    assert all(item["km"] > 5000 for items in passes.values() for item in items)
