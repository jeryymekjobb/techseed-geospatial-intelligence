"""Tests for the Landsat 8 scenes: the GDAL commands and the NDMI of
tools/fetch_landsat_scene.py (no network or Docker), the layer description, the
/landsat/ endpoint and which image the maps show (app/frontend/landsat.js)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app.backend import landsat, lantmateriet, server
from app.backend.scenario_engine import ScenarioEngine
from tools import fetch_landsat_scene as fetch

PNG = b"\x89PNG\r\n\x1a\nfake"
FRONTEND = Path(__file__).resolve().parents[1] / "app" / "frontend"
HAS_NUMPY = importlib.util.find_spec("numpy") is not None and importlib.util.find_spec("PIL") is not None


def test_reflectance_is_turned_into_level2_numbers() -> None:
    assert fetch.dn_for(0.0) == 7273 and fetch.dn_for(0.25) == 16364 and fetch.dn_for(0.45) == 23636


def test_the_script_cuts_the_map_area_writes_the_composites_and_the_raw_bands() -> None:
    bands = ["red", "green", "blue", "nir08", "swir16", "swir22", "qa_pixel"]
    script = fetch.warp_script({band: f"https://example.org/{band}.TIF?token=abc" for band in bands}, "SCENE")
    assert script.count("gdalwarp ") == 7
    assert "--config GDAL_DISABLE_READDIR_ON_OPEN EMPTY_DIR" in script
    assert "-t_srs EPSG:4326 -te 15.5 59.55 16.8 60.3 -ts 2410 2780" in script
    assert "-r near '/vsicurl/https://example.org/qa_pixel.TIF?token=abc' qa_pixel.tif" in script  # bit flags: never interpolated
    assert "-r bilinear '/vsicurl/https://example.org/swir22.TIF?token=abc' swir22.tif" in script
    for band in ["nir08", "swir16", "qa_pixel"]:
        assert f"gdal_translate -q -of EHdr {band}.tif SCENE-{band}.bil" in script
    assert "-scale 7273 16364 1 255 -a_nodata 0 -of PNG natural.vrt SCENE-natural.png" in script
    assert "-scale 7273 23636 1 255 -a_nodata 0 -of PNG swir.vrt SCENE-swir.png" in script


def test_docker_verifies_tls_with_the_host_certificates(tmp_path: Path) -> None:
    command = fetch.docker_command("true", Path("relative/dir"))
    assert f"{Path('relative/dir').resolve()}:/data" in command  # docker needs an absolute path
    assert f"{fetch.HOST_CA_BUNDLE}:/etc/ssl/host-ca.crt:ro" in command and "CURL_CA_BUNDLE=/etc/ssl/host-ca.crt" in command
    assert not any("READDIR" in part or "SSL_VERIFY" in part or "UNSAFESSL" in part for part in command)
    assert fetch.without_token("open /vsicurl/x.TIF?st=1&sig=abc failed", "st=1&sig=abc") == "open /vsicurl/x.TIF?<token> failed"


def test_the_fire_area_rows_and_columns() -> None:
    rows, cols = fetch.fire_area_rows_cols((600, 330), (15.85, 59.75, 16.45, 60.08))  # 0.001 degrees per pixel
    assert (cols.start, cols.stop) == (160, 450) and (rows.start, rows.stop) == (70, 250)


@pytest.mark.skipif(not HAS_NUMPY, reason="needs numpy and Pillow (the .venv)")
def test_ndmi_masks_clouds_and_water_and_counts_coverage(tmp_path: Path) -> None:
    import numpy as np
    from PIL import Image

    size = (60, 33)
    nir = np.full((33, 60), fetch.dn_for(0.30), dtype="<u2")
    swir = np.full((33, 60), fetch.dn_for(0.10), dtype="<u2")  # NDMI 0.5: moist
    qa = np.zeros((33, 60), dtype="<u2")
    qa[:, :30] = fetch.QA_FILL  # the western half has no data, cutting the fire area (columns 24-36)
    qa[15, 33] = 1 << 3          # one cloud pixel inside the fire area (rows 13-20)
    qa[17, 34] = fetch.QA_WATER  # one water pixel
    for band, data in {"nir08": nir, "swir16": swir, "qa_pixel": qa}.items():
        data.tofile(tmp_path / f"S-{band}.bil")
    coverage, cloud = fetch.ndmi_image(tmp_path, "S", size)
    image = np.asarray(Image.open(tmp_path / "S-ndmi.png"))
    assert image[5, 40, 3] == 230 and image[15, 33, 3] == 0 and image[17, 34, 3] == 0 and image[5, 5, 3] == 0
    assert tuple(image[5, 40, :3]) == (60, 154, 146)  # NDMI 0.5: a third of the way from the 0.45 to the 0.6 colour
    rows, cols = fetch.fire_area_rows_cols(size)
    area = (rows.stop - rows.start) * (cols.stop - cols.start)
    assert coverage == pytest.approx(100 * (rows.stop - rows.start) * (cols.stop - 30) / area, abs=0.1)
    assert cloud == pytest.approx(100 / area, abs=0.1)


def write_scenes(directory: Path, roles: dict[str, str], images: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    scenes = []
    for role, acquired in roles.items():
        scene = f"LC08_{role}"
        scenes.append({"role": role, "scene": scene, "acquired_utc": acquired, "fire_area_cloud_pct": 0.0,
                       "fire_area_coverage_pct": 100.0, "images": {name: {"file": f"{scene}-{name}.png"} for name in ["swir", "natural", "ndmi"]}})
        for name in images:
            (directory / f"{scene}-{name}.png").write_bytes(PNG)
    (directory / "SOURCE.json").write_text(json.dumps({
        "scenes": scenes, "bounds_west_south_east_north": [15.85, 59.75, 16.45, 60.08],
        "ndmi_colours": [[-0.2, [140, 81, 10]], [0.6, [1, 102, 94]]], "citation": "courtesy of the U.S. Geological Survey",
    }), encoding="utf-8")


ROLES = {"before": "2014-06-10T10:00:15Z", "during": "2014-08-04T10:06:44Z", "after": "2014-09-14T10:00:42Z"}


def test_the_layer_lists_the_scenes_in_time_order_with_their_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(landsat, "LANDSAT_DIR", tmp_path / "landsat")
    assert landsat.layer() is None
    write_scenes(tmp_path / "landsat", {"after": ROLES["after"], "before": ROLES["before"]}, ["swir", "ndmi"])
    layer = landsat.layer()
    assert [scene["role"] for scene in layer["scenes"]] == ["before", "after"]
    assert layer["scenes"][0]["images"] == {"swir": "/landsat/LC08_before-swir.png", "ndmi": "/landsat/LC08_before-ndmi.png"}
    assert layer["scenes"][1]["label"] == "Efter branden – jämförelse: Landsat 8, 2014-09-14 10:00 UTC"
    assert layer["bounds"] == [[59.75, 15.85], [60.08, 16.45]] and layer["ndmi_colours"][0][0] == -0.2


@pytest.fixture()
def base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(landsat, "LANDSAT_DIR", tmp_path / "landsat")
    write_scenes(tmp_path / "landsat", ROLES, ["swir", "natural", "ndmi"])
    (tmp_path / "secret.png").write_bytes(PNG)
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None), "control_token": None,
        "engine": ScenarioEngine(datetime(2014, 7, 31, tzinfo=timezone.utc), datetime(2014, 8, 15, tzinfo=timezone.utc)),
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def status(url: str) -> int:
    try:
        with urlopen(url, timeout=10) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


def test_the_images_are_served_and_nothing_else(base_url: str) -> None:
    with urlopen(f"{base_url}/landsat/LC08_during-ndmi.png", timeout=10) as response:
        assert response.read() == PNG and response.headers["Content-Type"] == "image/png"
    with urlopen(f"{base_url}/api/config", timeout=10) as response:
        assert len(json.loads(response.read())["layers"]["landsat"]["scenes"]) == 3
    for path in ["/landsat/SOURCE.json", "/landsat/%2e%2e/secret.png", "/landsat/missing.png"]:
        assert status(base_url + path) == 404, path


def scenes_js() -> list[dict]:
    return [{"role": role, "scene": f"LC08_{role}", "satellite": "Landsat 8", "acquired_utc": acquired, "images": {"swir": "x", "ndmi": "y"}}
            for role, acquired in ROLES.items()]


def select(clock: str, pick: str, latest: str = "swir") -> dict:
    code = (f"const m = require({json.dumps(str(FRONTEND / 'landsat.js'))});"
            f"const r = m.landsatSelection({json.dumps(scenes_js())}, Date.parse({json.dumps(clock)}), {json.dumps(pick)}, {json.dumps(latest)});"
            "console.log(JSON.stringify({key: r.key, reason: r.reason}));")
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_maps_show_the_chosen_image_or_the_latest_up_to_the_clock_and_the_after_image_only_as_a_comparison() -> None:
    assert select("2014-08-04T10:00:00Z", "auto") == {"key": "LC08_before|swir", "reason": "shown"}
    assert select("2014-08-04T10:07:00Z", "auto", "ndmi") == {"key": "LC08_during|ndmi", "reason": "shown"}
    assert select("2014-08-14T00:00:00Z", "auto") == {"key": "LC08_during|swir", "reason": "shown"}  # never the after image by itself
    assert select("2014-08-05T00:00:00Z", "LC08_before|ndmi") == {"key": "LC08_before|ndmi", "reason": "shown"}
    assert select("2014-07-31T00:00:00Z", "LC08_after|swir") == {"key": "LC08_after|swir", "reason": "comparison"}
    assert select("2014-08-05T00:00:00Z", "off") == {"key": None, "reason": "off"}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_a_chosen_image_not_taken_yet_gives_way_to_the_latest() -> None:
    assert select("2014-08-01T00:00:00Z", "LC08_during|swir") == {"key": "LC08_before|swir", "reason": "shown"}
    assert select("2014-08-01T00:00:00Z", "LC08_missing|swir") == {"key": "LC08_before|swir", "reason": "shown"}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_an_image_kind_not_taken_yet_is_none_yet() -> None:
    assert select("2014-08-04T10:00:00Z", "auto", "natural") == {"key": None, "reason": "none-yet"}  # the scenes have no natural colour


def options(clock: str) -> list[list[str]]:
    code = (f"const m = require({json.dumps(str(FRONTEND / 'landsat.js'))});"
            f"const r = m.imageOptions({json.dumps(scenes_js())}, {{swir: 'a', natural: 'b', ndmi: 'c'}}, Date.parse({json.dumps(clock)}), (t) => t.slice(0, 10));"
            "console.log(JSON.stringify(r.map((item) => [item.value, item.text])));")
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_mission_control_s_list_grows_with_the_clock_latest_first_with_the_comparison_last() -> None:
    assert options("2014-08-01T00:00:00Z") == [
        ["LC08_before|swir", "2014-06-10 – Landsat 8 – falska färger, kortvågig IR"],
        ["LC08_before|ndmi", "2014-06-10 – Landsat 8 – fukt i vegetationen (NDMI)"],
        ["LC08_after|swir", "2014-09-14 – Landsat 8 – falska färger, kortvågig IR (jämförelse – tagen senare)"],
        ["LC08_after|ndmi", "2014-09-14 – Landsat 8 – fukt i vegetationen (NDMI) (jämförelse – tagen senare)"],
    ]
    assert [value for value, _ in options("2014-08-05T00:00:00Z")] == [
        "LC08_during|swir", "LC08_during|ndmi", "LC08_before|swir", "LC08_before|ndmi", "LC08_after|swir", "LC08_after|ndmi"]
    assert [value for value, _ in options("2014-09-15T00:00:00Z")][:2] == ["LC08_after|swir", "LC08_after|ndmi"]  # taken by then: no comparison


def test_mission_control_may_choose_only_the_scenario_s_images(base_url: str) -> None:
    def post(target: str) -> int:
        request = Request(f"{base_url}/api/scenario/command", data=json.dumps({"command": "image", "target": target}).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=10) as response:
                assert json.loads(response.read())["status"]["image"] == target
                return response.status
        except HTTPError as exc:
            return exc.code

    assert [post(target) for target in ["LC08_during|ndmi", "off", "auto"]] == [200, 200, 200]
    assert [post(target) for target in ["LC08_during|water", "LC08_other|swir", "../x|swir", ""]] == [400, 400, 400, 400]


def test_mission_control_may_tick_only_the_scenario_s_image_types(base_url: str) -> None:
    def post(target: str) -> int:
        request = Request(f"{base_url}/api/scenario/command", data=json.dumps({"command": "image_types", "target": target}).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=10) as response:
                assert json.loads(response.read())["status"]["image_types"] == [kind for kind in target.split(",") if kind]
                return response.status
        except HTTPError as exc:
            return exc.code

    assert [post(target) for target in ["ndmi,swir", "", "swir"]] == [200, 200, 200]
    assert [post(target) for target in ["water", "swir,radar"]] == [400, 400]


def landsat_js(expression: str) -> object:
    code = (f"const m = require({json.dumps(str(FRONTEND / 'landsat.js'))}); const scenes = {json.dumps(scenes_js())};"
            f"console.log(JSON.stringify({expression}));")
    return json.loads(subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_auto_follows_the_latest_image_of_the_ticked_types_and_the_list_holds_only_them() -> None:
    # Radar on 1 August and an optical image on 3 August (SYNTHETIC scenes): the latest ticked one is shown.
    scenes = [{"role": "radar", "scene": "S1A_1", "satellite": "Sentinel-1A", "acquired_utc": "2024-08-01T05:00:00Z", "images": {"radar": "r"}},
              {"role": "during", "scene": "S2A_3", "satellite": "Sentinel-2A", "acquired_utc": "2024-08-03T10:00:00Z", "images": {"natural": "n", "water": "w"}}]
    def pick(clock: str, types: list[str]) -> dict:
        return landsat_js(f"(() => {{ const r = m.landsatSelection({json.dumps(scenes)}, Date.parse('{clock}'), 'auto', {json.dumps(types)});"
                          " return {key: r.key, reason: r.reason}; })()")
    assert pick("2024-08-04T00:00:00Z", ["radar", "natural"]) == {"key": "S2A_3|natural", "reason": "shown"}
    assert pick("2024-08-02T00:00:00Z", ["radar", "natural"]) == {"key": "S1A_1|radar", "reason": "shown"}  # the optical one not taken yet
    assert pick("2024-08-04T00:00:00Z", ["radar"]) == {"key": "S1A_1|radar", "reason": "shown"}
    assert pick("2024-08-04T00:00:00Z", ["water", "natural"]) == {"key": "S2A_3|water", "reason": "shown"}  # in the order given (the screens give the scenario's)
    assert pick("2024-08-04T00:00:00Z", []) == {"key": None, "reason": "no-types"}
    names = {"natural": "a", "water": "b", "radar": "c"}
    assert landsat_js(f"m.imageTypeCounts({json.dumps(scenes)}, {json.dumps(names)}, Date.parse('2024-08-02T00:00:00Z'))") == {
        "natural": {"taken": 0, "total": 1}, "water": {"taken": 0, "total": 1}, "radar": {"taken": 1, "total": 1}}
    listed = landsat_js(f"m.imageOptions({json.dumps(scenes)}, {json.dumps(names)}, Date.parse('2024-08-04T00:00:00Z'), (t) => t, ['radar']).map((i) => i.value)")
    assert listed == ["S1A_1|radar"]
    assert landsat_js(f"[m.defaultImageTypes('wildfire', {{natural: 1, swir: 1}}), m.defaultImageTypes('flood', {json.dumps(names)}),"
                      " m.defaultImageTypes('flood', {natural: 1}), m.defaultImageTypes('flood', {})]") == [["swir"], ["radar"], ["natural"], []]
    # The status's ticks in the scenario's order, or the default when none are set.
    assert landsat_js(f"[m.imageTypesShown(['radar', 'natural'], 'flood', {json.dumps(names)}), m.imageTypesShown(null, 'flood', {json.dumps(names)})]") == [
        ["natural", "radar"], ["radar"]]
    assert landsat_js("m.typeNames(['radar', 'natural'])") == "radar eller naturliga färger"


def test_mission_control_may_tick_only_the_base_maps_that_can_be_shown(base_url: str) -> None:
    def post(target: str) -> int:
        request = Request(f"{base_url}/api/scenario/command", data=json.dumps({"command": "base_maps", "target": target}).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=10) as response:
                return response.status
        except HTTPError as exc:
            return exc.code

    assert [post(target) for target in ["online", ""]] == [200, 200]
    assert [post(target) for target in ["topowebb", "satellite"]] == [400, 400]  # topowebb is not enabled in the test
