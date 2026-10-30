"""Tests for the scenario choice (app/backend/scenario.py, app/backend/scenarios/)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.backend import lantmateriet, scenario, server

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python(code: str, scenario_name: str | None) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "TECHSEED_SCENARIO"}
    if scenario_name is not None:
        env["TECHSEED_SCENARIO"] = scenario_name
    return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False)


def test_vastmanland_2014_is_the_default_scenario() -> None:
    result = run_python("from app.backend import scenario; print(scenario.NAME, scenario.DATABASE, scenario.TILES_FILE)", None)
    assert result.returncode == 0 and result.stdout.split() == ["vastmanland2014", "firemap", "vastmanland.mbtiles"]


def test_an_unknown_scenario_stops_with_the_available_ones() -> None:
    result = run_python("from app.backend import scenario", "atlantis")
    assert result.returncode != 0 and "vastmanland2014" in result.stderr


def test_the_scenario_keeps_the_values_of_the_fire_demo() -> None:
    assert scenario.VIEW_BBOX == (59.75, 60.08, 15.85, 16.45)
    assert scenario.MAP_BBOX == (15.5, 59.55, 16.8, 60.3)
    assert scenario.TARGETS_FILE == REPO_ROOT / "osm_data" / "targets-vastmanland.geojson"
    assert scenario.TLE_DIR / scenario.TLE_FILE_NAME == REPO_ROOT / "data" / "tle" / "tle-2014.json"


def test_config_gives_the_screens_the_scenario_texts_camera_and_map_area() -> None:
    config = server.config(lantmateriet.Settings(None, None, None, None, None))
    assert config["scenario"] == "vastmanland2014" and config["title"] == "Skogsbranden i Västmanland 2014"
    assert config["data_label"] == "Historiska data 2014 – uppspelning, inte live"
    assert config["control_label"].startswith("Scenario: WILDFIRE – Västmanland 2014")
    assert config["map_bounds"] == [[59.55, 15.5], [60.3, 16.8]]
    assert config["camera_route"][-1] == {"lon": 16.3, "lat": 59.6, "height": 160_000, "pitch": -60, "seconds": 2.2}


def test_sundsvall_2026_is_a_flood_with_its_own_data_and_the_municipality_s_layers() -> None:
    result = run_python("from app.backend import scenario; print(scenario.NAME, scenario.INCIDENT, scenario.DATABASE, "
                        "len(scenario.TLE_SATELLITES), scenario.TERRAIN_DIR.relative_to(scenario.REPO_ROOT))", "sundsvall2026")
    assert result.stdout.split() == ["sundsvall2026", "flood", "sundsvall2026", "10", "data/sundsvall2026/terrain"]  # with Meteosat-10 and -12
    layers = run_python("from app.backend import scenario; print(*scenario.MUNICIPAL_WMS['layers'])", "sundsvall2026").stdout.split()
    assert len(layers) == 12 and all(layer.startswith("SundsvallsKommun:") for layer in layers)  # only the municipality's own
    config = run_python("from app.backend import server, lantmateriet; import json; "
                        "c = server.config(lantmateriet.Settings(None, None, None, None, None)); "
                        "print(json.dumps([c['incident'], c['incident_place'], [w['id'] for w in c['layers']['wms']]]))", "sundsvall2026")
    assert config.stdout.strip() == '["flood", "Sundsvall", ["municipal", "mcf"]]'
    assert run_python("from app.backend import scenario; print(scenario.INCIDENT)", None).stdout.strip() == "wildfire"


def test_skane_2024_is_a_flood_with_smhi_s_flows_and_levels_and_mcf_s_maps() -> None:
    result = run_python("from app.backend import scenario; print(scenario.NAME, scenario.INCIDENT, scenario.DATABASE, scenario.TILES_FILE, "
                        "len(scenario.HYDRO_STATIONS), scenario.MUNICIPAL_DIR, scenario.HYDRO_DIR.relative_to(scenario.REPO_ROOT))", "skane2024")
    assert result.stdout.split() == ["skane2024", "flood", "skane2024", "skane.mbtiles", "6", "None", "data/skane2024/hydro"]
    config = run_python("from app.backend import server, lantmateriet; import json; "
                        "c = server.config(lantmateriet.Settings(None, None, None, None, None)); "
                        "print(json.dumps([c['title'], c['incident_place'], [w['id'] for w in c['layers']['wms']], c['playback']['start_utc']], ensure_ascii=False))", "skane2024")
    assert config.stdout.strip() == '["Översvämningarna i Skåne 2024", "Ringsjöarna", ["mcf"], "2024-01-20T00:00:00Z"]'
    # Without the municipality's stormwater points the flood has level sensors instead of overflow sensors;
    # their points are in data/, which is not in the repository (tools/derive_level_sensor_points.py).
    sensors = run_python("from app.backend import scenario, server; "
                         "print(type(server.synthetic_sensors()).__name__, len(server.synthetic_sensors().nodes), "
                         "scenario.LEVEL_SENSOR_FILE.is_file())", "skane2024")
    kind, count, fetched = sensors.stdout.split()
    assert sensors.returncode == 0 and kind == "LevelSensors" and count == ("8" if fetched == "True" else "0")


def test_the_wms_proxy_forwards_only_get_map_for_the_scenario_s_layers() -> None:
    code = """
from app.backend import wms
for query in [{'REQUEST': 'GetCapabilities', 'SERVICE': 'WMS'},
              {'REQUEST': 'GetMap', 'LAYERS': 'SundsvallsKommun:Elsewhere'},
              {'REQUEST': 'GetMap', 'LAYERS': 'SundsvallsKommun:100-ar_maxvattendjup', 'CQL_FILTER': 'x'}]:
    try:
        wms.get_map('municipal', query)
        print('forwarded')
    except ValueError:
        print('refused')
try:
    wms.get_map('elsewhere', {})
except KeyError:
    print('unknown')
"""
    assert run_python(code, "sundsvall2026").stdout.split() == ["refused", "refused", "refused", "unknown"]


def test_the_wms_proxy_always_forwards_styles() -> None:
    code = """
from urllib.parse import parse_qs, urlsplit
from app.backend import wms
urls = []
class Answer:
    headers = {'Content-Type': 'image/png'}
    def read(self): return b'png'
    def __enter__(self): return self
    def __exit__(self, *exc): return False
def answer(request, timeout):
    urls.append(request.full_url)
    return Answer()
wms.urlopen = answer
wms.get_map('mcf', {'service': 'WMS', 'request': 'GetMap', 'layers': '12', 'format': 'image/png'})
wms.get_map('mcf', {'service': 'WMS', 'request': 'GetMap', 'layers': '12', 'styles': 'default'})
for url in urls:
    print(parse_qs(urlsplit(url).query, keep_blank_values=True)['STYLES'])
"""
    # The screens' empty styles= is dropped by the query parsing; MCF refuses a GetMap without STYLES.
    assert run_python(code, "flenkommun2024").stdout.split("\n")[:2] == ["['']", "['default']"]


def test_a_silent_map_service_is_refused_at_once_and_reported_unavailable() -> None:
    code = """
from app.backend import wms
calls = []
def silent(request, timeout):
    calls.append(timeout)
    raise TimeoutError("The read operation timed out")
wms.urlopen = silent
query = {'SERVICE': 'WMS', 'REQUEST': 'GetMap', 'LAYERS': 'SundsvallsKommun:100-ar_maxvattendjup'}
for _ in range(3):
    try:
        wms.get_map('municipal', query)
    except wms.UpstreamError as exc:
        print(exc.status)
print(calls, wms.available('municipal'), [source['available'] for source in wms.sources()])
"""
    lines = run_python(code, "sundsvall2026").stdout.splitlines()
    # One wait of 5 s, then refused at once; the probe does not ask the silent service again, MCF is asked once.
    assert lines[:3] == ["504", "503", "503"]
    assert lines[3] == "[5, 5] False [False, False]"


def test_ljusdal_2018_is_a_fire_from_four_firms_satellites_with_its_own_forecast_station() -> None:
    result = run_python("from app.backend import scenario; print(scenario.NAME, scenario.INCIDENT, scenario.DATABASE, scenario.TILES_FILE, "
                        "scenario.FORECAST_STATION.replace(' ', '_'), all(path.is_file() for path in scenario.FIRMS_FILES), "
                        "sorted(role['firms'] for role in scenario.SATELLITE_ROLES.values() if role['firms']))", "ljusdal2018")
    assert result.stdout.strip().split(maxsplit=6) == ["ljusdal2018", "wildfire", "ljusdal2018", "ljusdal.mbtiles", "SMHI_Hamra_A", "True",
                                               "['Aqua', 'N20', 'SNPP', 'Terra']"]
    assert run_python("from app.backend import scenario; print(scenario.FORECAST_STATION)", None).stdout.strip() == "SMHI Sala A"


def test_every_scenario_has_a_summary_that_says_what_is_real() -> None:
    code = "from app.backend import scenario; import json; print(json.dumps(scenario.SUMMARY))"
    for name in ["vastmanland2014", "ljusdal2018", "sundsvall2026", "skane2024", "ljungan-aug2023"]:
        result = run_python(code, name)
        assert result.returncode == 0, result.stderr
        lines = __import__("json").loads(result.stdout)
        assert 4 <= len(lines) <= 7 and all(isinstance(line, str) and line for line in lines)
        assert any("simulerade" in line for line in lines), name  # the simulated parts are named as such
        assert not any(word in " ".join(lines) for word in [" mm ", " h ", " MW", " m "]), name  # whole words, as read aloud
        # Swedish, not Swenglish: the words the user asked to replace.
        assert not any(word in " ".join(lines) for word in ["live", "IoT", "IR ", "syntetisk", "vegetation", "detektioner", "-bilder", "klimatanpassad"]), name
        if name == "ljusdal2018":
            assert "Landsats bilder från de veckorna är för molniga över branden och är inte med." in lines
        if name == "ljungan-aug2023":
            # Skallböle's daily mean was 445-449 m³/s on 12-14 August, not first on the 14th.
            assert any("som högst den 12 till 14 augusti" in line for line in lines)
    assert server.config(lantmateriet.Settings(None, None, None, None, None))["summary"] == scenario.SUMMARY


def test_falsterbo_has_a_clear_image_a_year_and_one_on_each_side_of_babet() -> None:
    import importlib
    import re

    falsterbo = importlib.import_module("app.backend.scenarios.falsterbo")
    scenes = {**falsterbo.LANDSAT_SCENES, **falsterbo.SENTINEL2_SCENES}
    dates = {role: re.search(r"_(\d{8})", scene).group(1) for role, scene in scenes.items()}
    # Every year of the playback but 2012 (only Landsat 7, with gaps), 2023 through the pair round Babet.
    assert {date[:4] for date in dates.values()} == {str(year) for year in range(2013, 2027)}
    assert dates["before-babet"] < "20231020" < dates["after-babet"]
    assert all(dates[role].startswith(role) for role in scenes if role.isdigit())
    assert all(role in falsterbo.LANDSAT_ROLES for role in scenes)
    assert falsterbo.LANDSAT_ROLES["2019"] == "Årsbild 2019" and falsterbo.LANDSAT_ROLES["after-babet"] == "Efter Babet"
    assert all(falsterbo.PLAYBACK_START.strftime("%Y%m%d") <= date <= falsterbo.PLAYBACK_END.strftime("%Y%m%d") for date in dates.values())


def test_the_demo_check_expects_ljungan_s_flood_in_the_river_not_the_town() -> None:
    code = "from app.backend import scenario; print(scenario.CHECK_SENSORS, scenario.CHECK_OUTCOME, scenario.CHECK_DETECTION_OUTCOME, sep='|')"
    assert run_python(code, "ljungan-aug2023").stdout.strip() == "2/11|Possible flood|Okänd"
    # Scenarios that do not set it keep the flood the sequence has always ended with.
    assert run_python(code, "sundsvall2026").stdout.strip().endswith("|Översvämning trolig")


def test_the_demo_check_expects_no_detected_flood_in_sundsvall_in_november_2023() -> None:
    code = "from app.backend import scenario; print(scenario.CHECK_SENSORS, scenario.CHECK_OUTCOME, scenario.CHECK_DETECTION_OUTCOME, sep='|')"
    assert run_python(code, "sundsvall-nov2023").stdout.strip() == "4/9|Flood probable|Okänd"


def test_every_scenario_with_sundsvall_s_map_keeps_its_white_outside_transparent() -> None:
    code = "from app.backend import scenario; print(scenario.MUNICIPAL_BASEMAP.get('white_outside', False))"
    for name in ("sundsvall2026", "ljungan-aug2023", "sundsvall-nov2023", "sundsvall-feb2020", "sundsvall-dec2020"):
        assert run_python(code, name).stdout.strip() == "True", name
