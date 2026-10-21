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
