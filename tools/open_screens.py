#!/usr/bin/env python3
"""Open the demo's three screens as Chrome app windows, each in its place.

Select Edge explicitly with --browser edge or TECHSEED_BROWSER=edge; Chrome remains
the default. Edge uses separate demo profiles, never the user's ordinary profile.

Ubuntu/X11 uses xrandr, xprop and wmctrl. Windows uses native monitor/window
APIs and PowerShell process selection (tools/windows_screens.py); VM verification
is still required. Chrome discovery also covers macOS, but automatic placement
and closing there are not implemented: open the demo URLs manually instead.

A new window in a running Chrome opens where Chrome likes; its position cannot be set.
So each screen gets a Chrome of its own, with a profile of its own under
~/.cache/techseed-screens/. The window manager places new windows itself, so once a
screen's window is there (found by its Chrome's process id) it is moved with `wmctrl`,
lower than the monitor, since GNOME refuses a move that does not fit below its top bar
and the title bar, and then maximised vertically - or wholly, for a window that fills
its monitor - so it fits the monitor's work area exactly. The thirds are of the work area
(GNOME's _GTK_WORKAREAS_D0, without the dock and the top bar) where GNOME gives one. The monitors are read with `xrandr --listmonitors`:

- two or more: the widest has the satellite monitor on its left third and the main
  screen on the rest; mission control fills the next;
- one: the satellite monitor, the main screen and mission control side by side.

A screen already open with this tool is closed first, so it opens in its place again; --close
only closes them all (STARTA OM DEMO in tools/start_demo.py), and --only opens just the screens
named (kiosk mode in tools/start_demo.py opens a screen whose window has gone).
Chrome's own messages go nowhere. Press F11 in the main screen for full screen.

    .venv/bin/python -m tools.open_screens
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import quote

from tools.startup_check import find_chrome
from tools import browsers

PROFILES = Path.home() / ".cache" / "techseed-screens"
SCREENS = ("monitor", "main", "control")
MONITOR_LINE = re.compile(r"^\s*\d+:\s+\S+\s+(\d+)/\d+x(\d+)/\d+([+-]\d+)([+-]\d+)\s+(\S+)")


@dataclass(frozen=True)
class Monitor:
    name: str
    width: int
    height: int
    x: int
    y: int


@dataclass(frozen=True)
class Window:
    screen: str
    path: str
    x: int
    y: int
    width: int
    height: int
    fills_monitor: bool = False


def monitors(listing: str) -> list[Monitor]:
    """The monitors of `xrandr --listmonitors`."""
    found = []
    for line in listing.splitlines():
        match = MONITOR_LINE.match(line)
        if match:
            width, height, x, y, name = match.groups()
            found.append(Monitor(name, int(width), int(height), int(x), int(y)))
    return found


def work_areas(prop: str) -> list[tuple[int, int, int, int]]:
    """GNOME's work area per monitor from `xprop -root _GTK_WORKAREAS_D0`: x, y, width, height."""
    values = [int(value) for value in re.findall(r"-?\d+", prop.partition("=")[2])]
    return [tuple(values[index:index + 4]) for index in range(0, len(values) - 3, 4)]


def within_work_areas(screens: list[Monitor], areas: list[tuple[int, int, int, int]]) -> list[Monitor]:
    """Each monitor shrunk to the work area that lies on it, if any."""
    shrunk = []
    for screen in screens:
        area = next((area for area in areas if screen.x <= area[0] < screen.x + screen.width
                     and screen.y <= area[1] < screen.y + screen.height), None)
        shrunk.append(Monitor(screen.name, area[2], area[3], area[0], area[1]) if area else screen)
    return shrunk


def layout(screens: list[Monitor], at: str | None = None) -> list[Window]:
    """Where the satellite monitor, the main screen and mission control go."""
    main_path = "/3d.html" + (f"?at={at}" if at else "")
    control_path = "/control.html" + (f"?at={quote(at, safe='')}" if at else "")
    ordered = sorted(screens, key=lambda item: item.width * item.height, reverse=True)
    wide = ordered[0]
    third = wide.width // 3
    if len(ordered) >= 2:
        other = ordered[1]
        return [
            Window("monitor", "/monitor.html", wide.x, wide.y, third, wide.height),
            Window("main", main_path, wide.x + third, wide.y, wide.width - third, wide.height),
            Window("control", control_path, other.x, other.y, other.width, other.height, fills_monitor=True),
        ]
    return [
        Window("monitor", "/monitor.html", wide.x, wide.y, third, wide.height),
        Window("main", main_path, wide.x + third, wide.y, third, wide.height),
        Window("control", control_path, wide.x + 2 * third, wide.y, wide.width - 2 * third, wide.height),
    ]


def menu_windows(windows: list[Window]) -> tuple[list[Window], list[Window]]:
    """tools/start_demo.py's menu of demos in mission control's place, and the screens to close
    until a demo is chosen (the satellite monitor and the main screen)."""
    return ([replace(window, path="/menu.html") for window in windows if window.screen == "control"],
            [window for window in windows if window.screen != "control"])


def profile(screen: str, browser: str = "chrome") -> Path:
    return PROFILES / "edge" / screen if browser == "edge" else PROFILES / screen


def chrome_command(chrome: str, base_url: str, window: Window, browser: str = "chrome") -> list[str]:
    return [chrome, f"--app={base_url}{window.path}", f"--user-data-dir={profile(window.screen, browser)}",
            f"--window-position={window.x},{window.y}", f"--window-size={window.width},{window.height}",
            # The screens are in Swedish: no offer to translate them over the demo.
            "--no-first-run", "--no-default-browser-check", "--disable-features=Translate", "--lang=sv",
            # With automatic login the desktop's keyring stays locked, and Chrome would ask for its
            # password over the screens; the demo's profiles keep no passwords anyway.
            "--password-store=basic"]


def no_translation(profile: Path) -> None:
    """Switch off Chrome's offer to translate in the screen's profile: the screens are in Swedish."""
    preferences = profile / "Default" / "Preferences"
    try:
        settings = json.loads(preferences.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = {}
    settings.setdefault("translate", {})["enabled"] = False
    settings["translate_blocked_languages"] = sorted({*settings.get("translate_blocked_languages", []), "sv"})
    preferences.parent.mkdir(parents=True, exist_ok=True)
    preferences.write_text(json.dumps(settings), encoding="utf-8")


def close_all_command() -> list[str]:
    """Closes every screen this tool opened (their Chromes' profiles are under PROFILES), not the user's own Chrome."""
    return ["pkill", "-f", "--", f"--user-data-dir={PROFILES}/"]


def close_command(window: Window) -> list[str]:
    """Stop the screen's own Chrome, if this tool opened it before; `--` since the pattern starts with dashes."""
    return ["pkill", "-f", "--", f"--user-data-dir={PROFILES / window.screen}"]


def running_command(screen: str, browser: str = "chrome") -> list[str]:
    """Finds the screen's own browser, if it runs (exit code 0), by the same complete profile argument
    close_screen stops it by."""
    if sys.platform == "win32":
        from tools import windows_screens
        return windows_screens.running_command(profile(screen, browser))
    if sys.platform == "linux":
        return ["pgrep", "-f", "--", re.escape(f"--user-data-dir={profile(screen, browser)}") + r"(\s|$)"]
    raise RuntimeError("Finding the demo's windows is not implemented on this platform.")


def window_ids(listing: str, pid: int) -> list[str]:
    """The windows of a process in `wmctrl -lp` (id, desktop, pid, host, title)."""
    return [fields[0] for fields in (line.split(None, 4) for line in listing.splitlines()) if len(fields) >= 3 and fields[2] == str(pid)]


def place_commands(window_id: str, window: Window) -> list[list[str]]:
    """Un-maximise the window, move it there at three quarters of the height, then maximise it to fit."""
    maximise = "add,maximized_vert,maximized_horz" if window.fills_monitor else "add,maximized_vert"
    return [["wmctrl", "-i", "-r", window_id, "-b", "remove,maximized_vert,maximized_horz"],
            ["wmctrl", "-i", "-r", window_id, "-e", f"0,{window.x},{window.y},{window.width},{window.height * 3 // 4}"],
            ["wmctrl", "-i", "-r", window_id, "-b", maximise]]


def place(pid: int, window: Window, seconds: float = 20.0) -> bool:
    """Wait for the Chrome's window and move it into place; False when it did not appear."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        listing = subprocess.run(["wmctrl", "-lp"], capture_output=True, text=True, check=False).stdout
        ids = window_ids(listing, pid)
        if ids:
            time.sleep(0.5)  # let the window manager finish its own placing first
            for command in place_commands(ids[0], window):
                subprocess.run(command, check=False)
                time.sleep(0.3)
            return True
        time.sleep(0.25)
    return False


def desktop_monitors() -> list[Monitor]:
    if sys.platform == "win32":
        from tools import windows_screens
        return windows_screens.monitors()
    if sys.platform != "linux":
        raise RuntimeError("Automatic window placement is not implemented on macOS; open the demo URLs manually.")
    for command in ("xrandr", "xprop", "wmctrl", "pkill"):
        if not shutil.which(command):
            raise RuntimeError(f"Missing {command}; automatic Linux placement requires an X11 desktop.")
    listing = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True, check=False).stdout
    prop = subprocess.run(["xprop", "-root", "_GTK_WORKAREAS_D0"], capture_output=True, text=True, check=False).stdout
    return within_work_areas(monitors(listing), work_areas(prop))


def close_screen(screen: str, browser: str = "chrome") -> None:
    if sys.platform == "win32":
        from tools import windows_screens
        command = windows_screens.close_command(profile(screen, browser))
    elif sys.platform == "linux":
        # Escape profile paths as regex literals and require a complete argument.
        command = ["pkill", "-f", "--", re.escape(f"--user-data-dir={profile(screen, browser)}") + r"(\s|$)"]
    else:
        raise RuntimeError("Automatic demo window closing is not implemented on this platform.")
    subprocess.run(command, check=False, timeout=15)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="the backend")
    parser.add_argument("--at", help="start the main screen at this UTC time, for example 2026-08-16T05:00:00Z")
    parser.add_argument("--menu", action="store_true",
                        help="only mission control, with the menu of demos (tools/start_demo.py); the other screens close")
    parser.add_argument("--close", action="store_true", help="only close every screen this tool opened")
    parser.add_argument("--only", help=f"open only these screens, separated by commas ({', '.join(SCREENS)})")
    parser.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    parser.add_argument("--browser", choices=("chrome", "edge"))
    args = parser.parse_args(argv)
    try:
        browser = browsers.choice(args.browser)
    except ValueError as exc:
        parser.error(str(exc))
    only = set(args.only.split(",")) if args.only else set(SCREENS)
    if only - set(SCREENS):
        parser.error(f"--only takes {', '.join(SCREENS)}")
    if args.close:
        print("Stänger demons skärmar")
        if not args.dry_run:
            for screen in SCREENS:
                close_screen(screen, browser)
        return 0
    chrome = browsers.find_edge() if browser == "edge" else find_chrome()
    if not chrome:
        parser.exit(1, f"open_screens: selected browser {browser} was not found\n")
    try:
        screens = desktop_monitors()
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"open_screens: {exc}\n")
    if not screens:
        parser.exit(1, "open_screens: no monitors found\n")
    windows, closed = menu_windows(layout(screens)) if args.menu else (layout(screens, args.at), [])
    windows = [window for window in windows if window.screen in only]
    for window in closed:
        print(f"{window.screen}: stängs tills en demo är vald")
        if not args.dry_run:
            close_screen(window.screen, browser)
    for window in windows:
        command = chrome_command(chrome, args.base_url.rstrip("/"), window, browser)
        print(f"{window.screen}: {window.width}x{window.height} at {window.x},{window.y} – {args.base_url}{window.path}")
        if args.dry_run:
            print("  " + " ".join(command))
            continue
        close_screen(window.screen, browser)
        time.sleep(1.0)  # the old Chrome lets go of its profile
        no_translation(profile(window.screen, browser))
        chrome_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        if sys.platform == "win32":
            from tools.windows_screens import place as place_window
        else:
            place_window = place
        if not place_window(chrome_process.pid, window):
            print(f"  {window.screen}: the window did not appear; move it by hand")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
