"""Explicit Edge support without changing Chrome defaults or opening browsers."""

from contextlib import contextmanager
from types import SimpleNamespace
import sys

import pytest

from tools import browsers, check_demo, native_services, open_screens, start_demo, startup_check, windows_screens


def test_explicit_selection_overrides_environment_and_default_stays_chrome(monkeypatch):
    monkeypatch.delenv("TECHSEED_BROWSER", raising=False)
    assert browsers.choice() == "chrome"
    monkeypatch.setenv("TECHSEED_BROWSER", "edge")
    assert browsers.choice() == "edge"
    assert browsers.choice("chrome") == "chrome"
    assert browsers.channel("edge") == "msedge"
    assert browsers.channel("chrome") == "chrome"
    monkeypatch.setenv("TECHSEED_BROWSER", "invalid")
    with pytest.raises(ValueError):
        browsers.choice()


def test_windows_edge_discovery_outside_path(tmp_path, monkeypatch):
    monkeypatch.setattr(browsers.shutil, "which", lambda name: None)
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path))
    executable = tmp_path / "Microsoft/Edge/Application/msedge.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert browsers.find_edge() == str(executable)


def test_edge_profile_is_separate_and_closing_is_profile_scoped(monkeypatch):
    window = open_screens.Window("main", "/3d.html", 0, 0, 800, 600)
    command = open_screens.chrome_command("msedge.exe", "http://127.0.0.1:8765", window, "edge")
    assert f"--user-data-dir={open_screens.PROFILES / 'edge/main'}" in command
    assert open_screens.profile("main", "chrome") == open_screens.PROFILES / "main"
    calls = []
    monkeypatch.setattr(open_screens.sys, "platform", "win32")
    monkeypatch.setattr(open_screens.subprocess, "run", lambda command, **kw: calls.append(command))
    open_screens.close_screen("main", "edge")
    assert calls == [windows_screens.close_command(open_screens.PROFILES / "edge/main")]
    assert "Name = 'msedge.exe'" in calls[0][-1]


def test_native_startup_checks_edge_without_searching_for_chrome(tmp_path, monkeypatch):
    monkeypatch.setattr(browsers, "find_edge", lambda: "msedge.exe")
    def forbidden(*args):
        raise AssertionError("explicit Edge must not fall back to Chrome")
    monkeypatch.setattr(startup_check, "find_chrome", forbidden)
    monkeypatch.setattr(startup_check, "data_checks", lambda settings: [])
    monkeypatch.setattr(native_services, "prepared", lambda *args: None)
    monkeypatch.setattr(native_services, "check_database", lambda *args: None)
    checks = startup_check.native_installation_checks("vastmanland2014", native_services.Options(tmp_path), "edge")
    assert any(c.name == "Edge" and c.passed for c in checks)


def test_edge_option_reaches_launcher_and_restart_cleanup(monkeypatch):
    monkeypatch.setattr(start_demo, "port_in_use", lambda port: False)
    calls = []
    codes = iter([start_demo.RESTART_EXIT, 0])
    def demo(name, at, *, browser):
        assert browser == "edge"
        return next(codes)
    monkeypatch.setattr(start_demo, "run_demo", demo)
    monkeypatch.setattr(start_demo.subprocess, "run", lambda command, **kw: calls.append(command))
    assert start_demo.main(["vastmanland2014", "--browser", "edge"]) == 0
    assert calls[0][-3:] == ["--close", "--browser", "edge"]


def test_explicit_chrome_flag_overrides_inherited_edge(monkeypatch):
    monkeypatch.setenv("TECHSEED_BROWSER", "edge")
    assert start_demo.browser_flags("chrome") == ["--browser", "chrome"]


def test_edge_dry_run_uses_edge_executable_and_profile(monkeypatch, capsys):
    monkeypatch.setattr(browsers, "find_edge", lambda: "msedge.exe")
    monkeypatch.setattr(open_screens, "desktop_monitors", lambda: [open_screens.Monitor("test", 1920, 1080, 0, 0)])
    def forbidden(*args, **kwargs):
        raise AssertionError("preview must not start a browser or search Chrome")
    monkeypatch.setattr(open_screens, "find_chrome", forbidden)
    monkeypatch.setattr(open_screens.subprocess, "Popen", forbidden)
    assert open_screens.main(["--browser", "edge", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "msedge.exe" in output and str(open_screens.profile("main", "edge")) in output


def test_edge_cli_selects_native_startup_check(tmp_path, monkeypatch):
    seen = []
    def checks(name, options, browser):
        seen.append(browser)
        return [startup_check.Check("Edge", True, "synthetic")]
    monkeypatch.setattr(startup_check, "native_installation_checks", checks)
    assert startup_check.main(["vastmanland2014", "--services", "native", "--node-modules", str(tmp_path),
                               "--browser", "edge"]) == 0
    assert seen == ["edge"]


@pytest.mark.parametrize("selected,channel", [("chrome", "chrome"), ("edge", "msedge")])
def test_demo_check_launches_the_selected_playwright_channel(tmp_path, monkeypatch, selected, channel):
    calls = []
    class Browser:
        def close(self): calls.append("close")
    def launch(**kwargs):
        calls.append(kwargs)
        return Browser()
    @contextmanager
    def playwright():
        yield SimpleNamespace(chromium=SimpleNamespace(launch=launch))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=playwright))
    monkeypatch.setattr(check_demo, "Demo", lambda *args: None)
    monkeypatch.setattr(check_demo, "STEPS", [])
    report = check_demo.run("http://127.0.0.1:8765", tmp_path, False, browser=selected)
    assert calls[0]["channel"] == channel
    assert report.browser_name == selected
    assert ("WebGL i Edge" if selected == "edge" else "WebGL i Chrome") in report.text()
