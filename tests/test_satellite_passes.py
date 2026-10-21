"""Tests for the 2014 satellites: /api/satellites with and without fetched elements,
and a check of the whole chain against FIRMS - the satellite each detection names
must have passed within its instrument's swath of the detection, by the same orbit
code the globe uses (app/frontend/orbits.js with satellite.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from datetime import timedelta
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


def test_only_the_satellites_that_send_the_scenario_data_are_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    element = {"epoch_utc": "2014-07-31T00:00:00Z", "line1": "1" * 69, "line2": "2" * 69}
    (tmp_path / "tle-2014.json").write_text(json.dumps({"satellites": {
        "37849": {"name": "Suomi NPP", "elements": [element]},  # FIRMS
        "39084": {"name": "Landsat 8", "elements": [element]},  # one of the images
        "25544": {"name": "ISS", "elements": [element]},  # sends nothing
    }}), encoding="utf-8")
    monkeypatch.setattr(satellites, "TLE_FILE", tmp_path / "tle-2014.json")
    monkeypatch.setattr(satellites, "SOURCE_FILE", tmp_path / "SOURCE.json")
    monkeypatch.setattr(satellites.landsat, "layer", lambda: {"scenes": [{"satellite": "Landsat 8"}]})
    satellites.satellites.cache_clear()
    try:
        assert [item["name"] for item in satellites.satellites()["satellites"]] == ["Suomi NPP", "Landsat 8"]
        monkeypatch.setattr(satellites.landsat, "layer", lambda: None)
        satellites.satellites.cache_clear()
        assert [item["name"] for item in satellites.satellites()["satellites"]] == ["Suomi NPP"]
    finally:
        satellites.satellites.cache_clear()
    # Known acquisitions count as data too (Sentinel-1).
    assert satellites.contributes({"name": "Sentinel-1C", "acquisitions": ["2026-08-17T05:14:00Z"]}, set())
    assert not satellites.contributes({"name": "ISS", "firms": None}, {"Landsat 8"})
    # Meteosat counts only where the scenario shows its fire pixels or cloud tops.
    meteosat = {"name": "Meteosat-10", "firms": None, "geostationary": True}
    assert satellites.contributes(meteosat, set(), geostationary_data=True)
    assert not satellites.contributes(meteosat, set(), geostationary_data=False)


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
        "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0, "elements": [element],
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


PASS_CHECK = """
import * as lib from "SATELLITE_JS/index.js";
import { createRequire } from "module";
import fs from "fs";
const require = createRequire(import.meta.url);
const orbits = require("ORBITS");
const { satellites, cases, centre } = JSON.parse(fs.readFileSync(0, "utf8"));
const result = cases.map(({ norad, from, halfSwath }) => {
  const next = orbits.nextPass(lib, satellites[norad].elements, new Date(from), centre[0], centre[1], halfSwath);
  return next && next.toISOString();
});
const track = orbits.orbitTrack(lib, satellites["37849"].elements, new Date(cases[0].from));
console.log(JSON.stringify({ result, track: track.length, heights: [Math.min(...track.map((p) => p.height_km)), Math.max(...track.map((p) => p.height_km))] }));
"""


@needs_orbits
def test_the_next_pass_is_the_pass_that_made_the_detections(tmp_path: Path) -> None:
    closest_passes(tmp_path, 0)  # makes the satellite.js copy
    centre = list(server.scenario.FIRE_CENTRE)
    cases, expected = [], []
    for name, norad in NORAD.items():
        times = sorted({item["acq_datetime_utc"] for item in server.detections() if item["satellite"] == name})
        for acquired in times[:: max(1, len(times) // 4)][:4]:
            moment = server.parse_utc(acquired)
            half = HALF_SWATH_KM["VIIRS" if name == "SNPP" else "MODIS"]
            cases.append({"norad": norad, "from": (moment - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"), "halfSwath": half})
            expected.append(moment)
    script = PASS_CHECK.replace("SATELLITE_JS", (tmp_path / "satellite.js").as_posix()).replace("ORBITS", (FRONTEND / "orbits.js").as_posix())
    payload = {"satellites": json.loads(satellites.TLE_FILE.read_text(encoding="utf-8"))["satellites"], "cases": cases, "centre": centre}
    output = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload),
                                       capture_output=True, text=True, check=True).stdout)
    assert len(cases) >= 9
    for found, moment in zip(output["result"], expected):
        # The pass begins when the fire enters the swath, at most a few minutes before the granule.
        offset = (server.parse_utc(found.replace(".000Z", "Z")) - moment).total_seconds()
        assert -600 <= offset <= 360, (found, moment)
    assert output["track"] == 101 and 800 < output["heights"][0] < output["heights"][1] < 860  # Suomi NPP near 830 km


@needs_orbits
def test_landsat_8_passed_over_the_fire_when_the_scene_was_taken(tmp_path: Path) -> None:
    closest_passes(tmp_path, 0)  # makes the satellite.js copy
    acquired = server.parse_utc("2014-08-04T10:06:44Z")
    script = PASS_CHECK.replace("SATELLITE_JS", (tmp_path / "satellite.js").as_posix()).replace("ORBITS", (FRONTEND / "orbits.js").as_posix())
    payload = {
        "satellites": json.loads(satellites.TLE_FILE.read_text(encoding="utf-8"))["satellites"],
        "cases": [{"norad": "39084", "from": "2014-08-04T09:30:00Z", "halfSwath": 92.5},
                  {"norad": "37849", "from": "2014-08-04T09:30:00Z", "halfSwath": 1520.0}],
        "centre": list(server.scenario.FIRE_CENTRE),
    }
    output = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload),
                                       capture_output=True, text=True, check=True).stdout)
    landsat_pass = server.parse_utc(output["result"][0].replace(".000Z", "Z"))
    # The scene time is the centre of a 185 km scene; the fire is in it, so within a few tens of seconds.
    assert abs((landsat_pass - acquired).total_seconds()) <= 60


DAY_CHECK = """
import * as lib from "SATELLITE_JS/index.js";
import { createRequire } from "module";
import fs from "fs";
const require = createRequire(import.meta.url);
const orbits = require("ORBITS");
const { satellites, days, centre } = JSON.parse(fs.readFileSync(0, "utf8"));
const result = {};
for (const [norad, half] of [["27424", 1165], ["25994", 1165], ["37849", 1520]]) {
  result[norad] = days.flatMap((day) => {
    const start = Date.parse(day);
    return orbits.passesBetween(lib, satellites[norad].elements, start, start + 86400000, centre[0], centre[1], half);
  });
}
console.log(JSON.stringify(result));
"""


@needs_orbits
def test_the_passes_of_a_day_contain_every_detection(tmp_path: Path) -> None:
    closest_passes(tmp_path, 0)  # makes the satellite.js copy
    days = ["2014-08-03T00:00:00Z", "2014-08-04T00:00:00Z"]
    script = DAY_CHECK.replace("SATELLITE_JS", (tmp_path / "satellite.js").as_posix()).replace("ORBITS", (FRONTEND / "orbits.js").as_posix())
    payload = {"satellites": json.loads(satellites.TLE_FILE.read_text(encoding="utf-8"))["satellites"], "days": days,
               "centre": list(server.scenario.FIRE_CENTRE)}
    passes = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload),
                                       capture_output=True, text=True, check=True).stdout)
    by_name = {name: passes[norad] for name, norad in NORAD.items()}
    checked = 0
    for item in server.detections():
        if not item["acq_datetime_utc"].startswith(("2014-08-03", "2014-08-04")):
            continue
        acquired = server.parse_utc(item["acq_datetime_utc"]).timestamp() * 1000
        # The granule (acquisition time to five minutes later) overlaps a computed pass.
        assert any(entry["start"] <= acquired + 360000 and entry["end"] >= acquired - 60000 for entry in by_name[item["satellite"]]), item
        checked += 1
    assert checked > 300
    assert all(0 < entry["end"] - entry["start"] < 30 * 60000 for entries in passes.values() for entry in entries)
