"""Installation checks must not start services or need an installed demo."""

import subprocess
import sys
from types import SimpleNamespace

from tools import check_demo, start_demo, startup_check


def test_child_processes_use_the_current_python():
    assert str(start_demo.PYTHON) == sys.executable
    assert str(check_demo.PYTHON) == sys.executable


def test_chrome_on_path(monkeypatch):
    monkeypatch.setattr(startup_check.shutil, "which", lambda name: "/chrome" if name == "chromium" else None)
    assert startup_check.find_chrome() == "/chrome"


def test_windows_chrome_outside_path(tmp_path, monkeypatch):
    monkeypatch.setattr(startup_check.shutil, "which", lambda name: None)
    chrome = tmp_path / "Google/Chrome/Application/chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.touch()
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    assert startup_check.find_chrome() == str(chrome)


def test_probe_handles_absence_timeout_and_failure(monkeypatch):
    for error in (FileNotFoundError(), subprocess.TimeoutExpired("docker", 15)):
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr(startup_check.subprocess, "run", fail)
        assert not startup_check.probe("Docker", ["docker", "info"]).passed
    monkeypatch.setattr(startup_check.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    assert not startup_check.probe("Docker", ["docker", "info"]).passed


def test_data_presence_checks_are_read_only(tmp_path):
    settings = SimpleNamespace(TERRAIN_FILE=tmp_path / "terrain.json", TARGETS_FILE=tmp_path / "targets.json",
                               WIND_FILE=tmp_path / "wind.csv", TLE_DIR=tmp_path / "tle", TLE_FILE_NAME="tle.json",
                               TILES_FILE="demo.mbtiles", FIRMS_FILES=[], WEATHER_DIR=tmp_path / "weather")
    before = list(tmp_path.rglob("*"))
    assert not all(check.passed for check in startup_check.data_checks(settings, tmp_path))
    assert list(tmp_path.rglob("*")) == before
    for check in startup_check.data_checks(settings, tmp_path):
        path = tmp_path / check.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic test placeholder", encoding="utf-8")
    assert all(check.passed for check in startup_check.data_checks(settings, tmp_path))
    settings.WIND_FILE.write_text("")
    assert not all(check.passed for check in startup_check.data_checks(settings, tmp_path))


def test_cli_reports_failure_without_installing(monkeypatch, capsys):
    monkeypatch.setattr(startup_check, "installation_checks", lambda name: [startup_check.Check(name, False, "missing")])
    assert startup_check.main(["kramfors2026"]) == 1
    assert "MISSING/FAILED kramfors2026" in capsys.readouterr().out


def test_landsat_metadata_is_only_required_for_configured_scenes(tmp_path):
    from app.backend.scenarios import ljusdal2018, vastmanland2014

    assert not ljusdal2018.LANDSAT_SCENES
    checks = startup_check.data_checks(ljusdal2018, tmp_path)
    assert str(ljusdal2018.LANDSAT_DIR / "SOURCE.json") not in {check.name for check in checks}
    assert vastmanland2014.LANDSAT_SCENES
    checks = startup_check.data_checks(vastmanland2014, tmp_path)
    assert str(vastmanland2014.LANDSAT_DIR / "SOURCE.json") in {check.name for check in checks}


def test_forecast_weather_inputs_are_checked_and_deduplicated(tmp_path):
    settings = SimpleNamespace(TERRAIN_FILE=tmp_path / "terrain.json", TARGETS_FILE=tmp_path / "targets.json",
                               WIND_FILE=tmp_path / "wind.csv", TLE_DIR=tmp_path / "tle", TLE_FILE_NAME="tle.json",
                               TILES_FILE="demo.mbtiles", FIRMS_FILES=[],
                               FORECAST_WEATHER_FILES=[tmp_path / "spinup.csv", tmp_path / "weather.csv",
                                                       tmp_path / "weather.csv"])
    def weather_checks():
        return [check for check in startup_check.data_checks(settings, tmp_path)
                if check.name in {str(path) for path in settings.FORECAST_WEATHER_FILES}]

    assert len(weather_checks()) == 2
    assert not any(check.passed for check in weather_checks())
    for path in settings.FORECAST_WEATHER_FILES:
        path.write_text("synthetic weather fixture", encoding="utf-8")
    assert all(check.passed for check in weather_checks())
    settings.FORECAST_WEATHER_FILES[0].write_text("")
    assert not all(check.passed for check in weather_checks())


def test_karbole_forecast_weather_files_are_included(tmp_path):
    from app.backend.scenarios import ljusdal2018

    names = {check.name for check in startup_check.data_checks(ljusdal2018, tmp_path)}
    assert ljusdal2018.FORECAST_WEATHER_FILES
    assert all(str(path) in names for path in ljusdal2018.FORECAST_WEATHER_FILES)


def test_met_norway_forecasts_are_reported_but_optional(tmp_path, monkeypatch, capsys):
    # The Windows test of 2026-10-22: flen2019 runs without forecasts, which were never fetched for it.
    settings = SimpleNamespace(TERRAIN_FILE=tmp_path / "terrain.json", TARGETS_FILE=tmp_path / "targets.json",
                               WIND_FILE=tmp_path / "wind.csv", TLE_DIR=tmp_path / "tle", TLE_FILE_NAME="tle.json",
                               TILES_FILE="demo.mbtiles", FIRMS_FILES=[], MET_FORECAST_DIR=tmp_path / "met-forecast")
    for check in startup_check.data_checks(settings, tmp_path):
        if "met-forecast" not in check.name:
            path = tmp_path / check.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic test placeholder", encoding="utf-8")
    checks = startup_check.data_checks(settings, tmp_path)
    forecast = next(check for check in checks if "met-forecast" in check.name)
    assert not forecast.passed and not forecast.required and "optional" in forecast.detail
    assert all(check.passed for check in checks if check.required)
    monkeypatch.setattr(startup_check, "installation_checks", lambda name: checks)
    assert startup_check.main(["flen2019"]) == 0
    assert "OPTIONAL/MISSING" in capsys.readouterr().out


def test_a_scenario_without_wind_or_satellites_needs_neither_file(tmp_path):
    # Falsterbo's erosion over 2012-2026: no ERA5-Land wind and no satellite orbits.
    settings = SimpleNamespace(TERRAIN_FILE=tmp_path / "terrain.json", TARGETS_FILE=tmp_path / "targets.json",
                               WIND_FILE=None, TLE_DIR=tmp_path / "tle", TLE_FILE_NAME="tle.json", TLE_SATELLITES={},
                               TILES_FILE="demo.mbtiles", FIRMS_FILES=[])
    names = [check.name for check in startup_check.data_checks(settings, tmp_path)]
    assert str(tmp_path / "wind.csv") not in names and str(tmp_path / "tle" / "tle.json") not in names
    with_both = SimpleNamespace(**{**vars(settings), "WIND_FILE": tmp_path / "wind.csv", "TLE_SATELLITES": {"40697": "Sentinel-2A"}})
    names = [check.name for check in startup_check.data_checks(with_both, tmp_path)]
    assert str(tmp_path / "wind.csv") in names and str(tmp_path / "tle" / "tle.json") in names


def test_a_scenario_without_sentinel_2_scenes_needs_no_sentinel_2_file(tmp_path):
    # Sundsvall in November 2023: every Sentinel-2 scene was cloudy.
    settings = SimpleNamespace(TERRAIN_FILE=tmp_path / "terrain.json", TARGETS_FILE=tmp_path / "targets.json", WIND_FILE=None,
                               TLE_DIR=tmp_path / "tle", TLE_FILE_NAME="tle.json", TLE_SATELLITES={}, TILES_FILE="demo.mbtiles",
                               FIRMS_FILES=[], SENTINEL2_DIR=tmp_path / "sentinel2", SENTINEL2_SCENES={})
    assert str(tmp_path / "sentinel2" / "SOURCE.json") not in [check.name for check in startup_check.data_checks(settings, tmp_path)]
    settings.SENTINEL2_SCENES = {"after": "S2A_MSIL2A_20231105T103221_R108"}
    assert str(tmp_path / "sentinel2" / "SOURCE.json") in [check.name for check in startup_check.data_checks(settings, tmp_path)]
