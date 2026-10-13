"""Tests for tools/open_screens.py (no Chrome or xrandr needed)."""

from __future__ import annotations

from tools import open_screens as screens

LISTING = """Monitors: 2
 0: +*HDMI-1-0 3440/797x1440/334+0+160  HDMI-1-0
 1: +eDP-1 2560/344x1600/215+3440+0  eDP-1
"""


def test_the_monitors_are_read_from_xrandr() -> None:
    assert screens.monitors(LISTING) == [screens.Monitor("HDMI-1-0", 3440, 1440, 0, 160), screens.Monitor("eDP-1", 2560, 1600, 3440, 0)]


def test_two_monitors_the_satellite_monitor_and_main_screen_share_the_widest_and_mission_control_gets_the_other() -> None:
    windows = screens.layout(screens.monitors(LISTING), "2026-08-16T05:00:00Z")
    assert [(item.screen, item.x, item.y, item.width, item.height) for item in windows] == [
        ("monitor", 0, 160, 1146, 1440), ("main", 1146, 160, 2294, 1440), ("control", 3440, 0, 2560, 1600)]
    assert windows[1].path == "/3d.html?at=2026-08-16T05:00:00Z"
    assert windows[2].path == "/control.html?at=2026-08-16T05%3A00%3A00Z"


def test_one_monitor_the_three_screens_side_by_side() -> None:
    windows = screens.layout([screens.Monitor("eDP-1", 2560, 1600, 0, 0)])
    assert [(item.screen, item.x, item.width) for item in windows] == [("monitor", 0, 853), ("main", 853, 853), ("control", 1706, 854)]
    assert windows[1].path == "/3d.html"


def test_each_screen_is_a_chrome_app_with_its_own_profile_and_place() -> None:
    window = screens.Window("control", "/control.html", 3440, 0, 2560, 1600)
    command = screens.chrome_command("/usr/bin/google-chrome", "http://127.0.0.1:8765", window)
    assert command[1:5] == ["--app=http://127.0.0.1:8765/control.html", f"--user-data-dir={screens.PROFILES / 'control'}",
                            "--window-position=3440,0", "--window-size=2560,1600"]
    assert "--disable-features=Translate" in command


def test_the_old_screen_is_closed_with_its_own_profile_as_the_pattern() -> None:
    window = screens.Window("main", "/3d.html", 0, 0, 1, 1)
    assert screens.close_command(window) == ["pkill", "-f", "--", f"--user-data-dir={screens.PROFILES / 'main'}"]
    assert screens.close_all_command() == ["pkill", "-f", "--", f"--user-data-dir={screens.PROFILES}/"]  # STARTA OM DEMO: only the demo's Chromes


def test_the_window_is_found_by_its_process_and_moved_into_place() -> None:
    listing = ("0x04a00004  0 1234   my2nd Översvämning i Sundsvall 2026 – scenario – 3D\n"
               "0x05200004  0 5678   my2nd Översvämning i Sundsvall 2026 – scenario – 3D\n")
    assert screens.window_ids(listing, 5678) == ["0x05200004"]
    window = screens.Window("main", "/3d.html", 1146, 160, 2294, 1440)
    moved, maximised = screens.place_commands("0x05200004", window)[1:]
    assert moved == ["wmctrl", "-i", "-r", "0x05200004", "-e", "0,1146,160,2294,1080"]  # lower, so GNOME lets it move
    assert maximised[-1] == "add,maximized_vert"
    control = screens.layout(screens.monitors(LISTING))[2]
    assert control.fills_monitor and screens.place_commands("0x1", control)[2][-1] == "add,maximized_vert,maximized_horz"


def test_the_thirds_are_of_gnome_s_work_area_without_the_dock_and_top_bar() -> None:
    areas = screens.work_areas("_GTK_WORKAREAS_D0(CARDINAL) = 66, 192, 3374, 1408, 3440, 0, 2560, 1600")
    assert areas == [(66, 192, 3374, 1408), (3440, 0, 2560, 1600)]
    windows = screens.layout(screens.within_work_areas(screens.monitors(LISTING), areas))
    assert [(item.screen, item.x, item.y, item.width, item.height) for item in windows] == [
        ("monitor", 66, 192, 1124, 1408), ("main", 1190, 192, 2250, 1408), ("control", 3440, 0, 2560, 1600)]
    assert screens.within_work_areas(screens.monitors(LISTING), []) == screens.monitors(LISTING)  # no GNOME: whole monitors


def test_the_profile_does_not_offer_to_translate(tmp_path) -> None:
    import json
    (tmp_path / "Default").mkdir()
    (tmp_path / "Default" / "Preferences").write_text(json.dumps({"translate": {"enabled": True}, "kept": 1}), encoding="utf-8")
    screens.no_translation(tmp_path)
    settings = json.loads((tmp_path / "Default" / "Preferences").read_text(encoding="utf-8"))
    assert settings == {"translate": {"enabled": False}, "translate_blocked_languages": ["sv"], "kept": 1}
    screens.no_translation(tmp_path / "new")  # a profile Chrome has not made yet
    assert json.loads((tmp_path / "new" / "Default" / "Preferences").read_text(encoding="utf-8"))["translate"] == {"enabled": False}


def test_the_menu_opens_only_in_mission_control_s_place_and_the_other_screens_close() -> None:
    windows = screens.layout(screens.monitors(LISTING), "2026-08-16T05:00:00Z")
    menu, closed = screens.menu_windows(windows)
    control = windows[2]
    assert [(w.screen, w.path, w.x, w.y, w.width, w.height) for w in menu] == [
        ("control", "/menu.html", control.x, control.y, control.width, control.height)]
    assert [window.screen for window in closed] == ["monitor", "main"]
