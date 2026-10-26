"""Tests for each image's satellite at the time of its image (tools/fetch_scene_elements.py,
app/backend/scene_satellites.py, landsat.js imageSatellite). SYNTHETIC records; the element set is
a published ISS example, not one of the scenario's."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.backend import passes, scene_satellites
from tools import fetch_scene_elements as fetch

ISS = {"line1": "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
       "line2": "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"}
LANDSAT_JS = Path(__file__).resolve().parents[1] / "app" / "frontend" / "landsat.js"


def test_the_element_set_nearest_the_image_is_kept() -> None:
    records = [{"EPOCH": "2019-06-29 01:00:00", "TLE_LINE1": "1" * 69, "TLE_LINE2": "2" * 69},
               {"EPOCH": "2019-06-29 11:41:37", "TLE_LINE1": "a" * 69, "TLE_LINE2": "b" * 69},
               {"EPOCH": "2019-06-29 10:40:00", "TLE_LINE1": "short", "TLE_LINE2": "2" * 69}]
    moment = datetime(2019, 6, 29, 10, 30, tzinfo=timezone.utc)
    assert fetch.nearest(records, moment) == {"epoch_utc": "2019-06-29T11:41:37Z", "line1": "a" * 69, "line2": "b" * 69}
    assert fetch.nearest([], moment) is None
    assert fetch.query_path("40697", moment).endswith("/NORAD_CAT_ID/40697/EPOCH/2019-06-26--2019-07-02/orderby/EPOCH/format/json")


def test_the_scenes_are_read_from_the_image_sources(tmp_path: Path) -> None:
    (tmp_path / "SOURCE.json").write_text(json.dumps({"scenes": [
        {"scene": "S2A_MSIL2A_20190629T103031_R108", "acquired_utc": "2019-06-29T10:30:31Z"},
        {"scene": "LC08_L2SP_195021_20130707_02_T1", "acquired_utc": "2013-07-07T10:16:00Z"},
        {"scene": "S1A_IW_GRDH_X", "acquired_utc": "2020-01-01T05:00:00Z"}]}), encoding="utf-8")
    assert fetch.scenes([tmp_path, None]) == [
        {"scene": "LC08_L2SP_195021_20130707_02_T1", "satellite": "Landsat 8", "acquired_utc": "2013-07-07T10:16:00Z"},
        {"scene": "S2A_MSIL2A_20190629T103031_R108", "satellite": "Sentinel-2A", "acquired_utc": "2019-06-29T10:30:31Z"}]


@pytest.mark.skipif(not passes.available(), reason="needs sgp4")
def test_the_satellite_is_taken_where_it_came_nearest_the_place() -> None:
    centre = (55.39, 12.91)

    def distance(at: datetime) -> float:
        point = scene_satellites.position(ISS, at)
        return passes.ground_distance_km(*centre, point["latitude"], point["longitude"])

    # The ISS's nearest pass over the day, found every 30 s, stands in for an image; the window starts
    # five minutes before it, as a catalogue time may lie before the satellite reaches the place.
    start = datetime(2019, 12, 9, tzinfo=timezone.utc)
    nearest_pass = min((start + timedelta(seconds=30 * step) for step in range(2880)), key=distance)
    moment, point = scene_satellites.overpass(ISS, nearest_pass - timedelta(minutes=5), centre)
    assert abs((moment - nearest_pass).total_seconds()) <= 30 and distance(moment) < 1000
    assert distance(moment) <= min(distance(moment - timedelta(seconds=1)), distance(moment + timedelta(seconds=1)))
    assert 380 < point["height_km"] < 440 and 7.0 < point["speed_km_s"] < 8.0  # the ISS's height and speed
    assert scene_satellites.direction(55.39, 12.91, 55.69, 11.35) == "väster"
    assert scene_satellites.direction(55.39, 12.91, 55.27, 13.64) == "öster"


def test_the_image_layer_gets_each_scene_s_satellite(monkeypatch: pytest.MonkeyPatch) -> None:
    at = {"latitude": 55.69, "longitude": 11.35, "height_km": 797.6, "norad": "40697", "distance_km": 104, "direction": "väster"}
    monkeypatch.setattr(scene_satellites, "positions", lambda: {"S2A_X": at})
    layer = scene_satellites.with_positions({"scenes": [{"scene": "S2A_X"}, {"scene": "LC08_Y"}]})
    assert layer["scenes"] == [{"scene": "S2A_X", "satellite_at": at}, {"scene": "LC08_Y"}] and "inte en observation" in layer["satellite_label"]
    monkeypatch.setattr(scene_satellites, "positions", lambda: {})
    assert scene_satellites.with_positions({"scenes": []}) == {"scenes": []} and scene_satellites.with_positions(None) is None


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_screens_take_the_latest_image_s_satellite_and_say_where_it_was() -> None:
    at = {"latitude": 55.69, "longitude": 11.35, "height_km": 797.6, "speed_km_s": 7.45, "norad": "40697",
          "time_utc": "2019-06-29T10:35:29Z", "distance_km": 104, "direction": "väster"}
    scenes = [{"satellite": "Landsat 8", "acquired_utc": "2014-07-19T10:07:00Z", "satellite_at": {**at, "norad": "39084", "time_utc": "2014-07-19T10:07:58Z"}},
              {"satellite": "Sentinel-2A", "acquired_utc": "2019-06-29T10:30:31Z", "satellite_at": at},
              {"satellite": "Sentinel-2B", "acquired_utc": "2020-06-15T10:15:59Z"}]
    code = (f"const m = require({json.dumps(str(LANDSAT_JS))}); const s = {json.dumps(scenes)};"
            "console.log(JSON.stringify([m.imageSatellite(s, Date.parse('2013-01-01T00:00:00Z')),"
            " m.imageSatellite(s, Date.parse('2020-07-01T00:00:00Z')), m.satelliteAtText(s[1].satellite_at, 'Falsterbonäset'),"
            " m.satelliteAtText(undefined, 'Falsterbonäset')]));")
    before, later, text, none = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    # Before the first image no satellite; in July 2020 the 2019 image's, since the 2020 image has no position.
    assert before is None
    assert (later["name"], later["instrument"], later["norad"], later["track"], later["passes"]) == ("Sentinel-2A", "MSI", "40697", [], None)
    assert later["point"] == {"latitude": 55.69, "longitude": 11.35, "height_km": 797.6, "speed_km_s": 7.45}
    assert text == " – satelliten 798 km upp, 104 km väster om Falsterbonäset (beräknat)" and none == ""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_log_s_image_line_comes_when_the_satellite_was_over_the_place() -> None:
    satlog = Path(__file__).resolve().parents[1] / "app" / "frontend" / "satlog.js"
    scenes = [{"satellite": "Sentinel-2A", "acquired_utc": "2019-06-29T10:30:31Z", "satellite_at": {"time_utc": "2019-06-29T10:35:29Z"}},
              {"satellite": "Landsat 8", "acquired_utc": "2014-07-19T10:07:00Z"}]
    code = (f"const m = require({json.dumps(str(satlog))});"
            f"console.log(JSON.stringify(m.satelliteLog({{ scenes: {json.dumps(scenes)} }}, Date.parse('2020-01-01T00:00:00Z'), Infinity, Infinity, 'näset')"
            ".map((line) => new Date(line.atMs).toISOString())));")
    times = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert times == ["2019-06-29T10:35:29.000Z", "2014-07-19T10:07:00.000Z"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_caption_gives_the_time_the_satellite_was_over_the_place() -> None:
    scene = {"satellite": "Sentinel-2A", "acquired_utc": "2019-06-29T10:30:31Z", "images": {"natural": "x"},
             "satellite_at": {"height_km": 797.6, "time_utc": "2019-06-29T10:35:29Z", "distance_km": 104, "direction": "väster"}}
    code = (f"const m = require({json.dumps(str(LANDSAT_JS))});"
            f"console.log(JSON.stringify(m.viewCaption({{ scene: {json.dumps(scene)}, image: 'natural', formatTime: (t) => t, place: 'Falsterbonäset' }})));")
    caption = json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)
    assert caption == ("Visas: Satellitbild – Sentinel-2A, naturliga färger, tagen 2019-06-29T10:35:29Z"
                       " – satelliten 798 km upp, 104 km väster om Falsterbonäset (beräknat)")
