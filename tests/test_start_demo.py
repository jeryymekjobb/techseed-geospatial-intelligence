"""Tests for tools/start_demo.py (no demo is started)."""

from __future__ import annotations

import json
import socket
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from tools import start_demo


def test_each_scenario_starts_with_its_own_map_and_time() -> None:
    assert start_demo.scenario_settings("vastmanland2014") == ("vastmanland.mbtiles", "2014-07-31T00:00:00Z")
    assert start_demo.scenario_settings("sundsvall2026") == ("sundsvall.mbtiles", "2026-08-14T00:00:00Z")
    assert start_demo.scenario_settings("skane2024") == ("skane.mbtiles", "2024-01-20T00:00:00Z")
    assert start_demo.scenario_settings("ljusdal2018") == ("ljusdal.mbtiles", "2018-07-12T00:00:00Z")
    assert start_demo.services_command() == ["docker", "compose", "up", "-d", "tiles", "postgis", "mosquitto"]


def test_a_demo_starts_at_the_start_saved_in_its_profile(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.backend import profiles

    monkeypatch.setattr(profiles, "PROFILE_FILE", tmp_path / "display-profiles.json")
    profiles.save("sundsvall2026", None, None, playback={"start_utc": "2026-08-14T22:00:00Z", "end_utc": "2026-08-18T00:00:00Z"})
    profiles.save("skane2024", None, None, playback={"start_utc": "2026-08-14T22:00:00Z", "end_utc": "2026-08-18T00:00:00Z"})
    assert start_demo.scenario_settings("sundsvall2026") == ("sundsvall.mbtiles", "2026-08-14T22:00:00Z")
    # A start outside the scenario's period (not Skåne's winter): the scenario's own start.
    assert start_demo.scenario_settings("skane2024") == ("skane.mbtiles", "2024-01-20T00:00:00Z")


def test_a_port_in_use_is_found() -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        busy = server.getsockname()[1]
        assert start_demo.port_in_use(busy)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    assert not start_demo.port_in_use(free)


def test_the_menu_lists_the_demos_with_their_titles_and_labels() -> None:
    assert [(demo["name"], demo["title"]) for demo in start_demo.demos()] == [
        ("vastmanland2014", "Skogsbranden i Västmanland 2014"),
        ("sundsvall2026", "Översvämning i Sundsvall 2026 – scenario"),
        ("skane2024", "Översvämningarna i Skåne 2024"),
        ("ljusdal2018", "Skogsbranden vid Kårböle 2018"),
        ("vasternorrland2025", "Regnet i Västernorrland 2025"),
        ("kramfors2026", "Skyfallet i Kramfors 2026"),
        ("flenkommun2024", "Höga flöden i Flens kommun 2024"),
        ("flen2024", "Högt vatten i Flen 2024"),
        ("flenkommun2021", "Regnet i Flens kommun 2021"),
        ("flen2019", "Höga flöden i Flen 2019"),
    ]
    assert all(demo["label"] for demo in start_demo.demos())


def request(url: str, body: dict | None = None) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urlopen(Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=10) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def test_the_menu_page_serves_the_demos_and_takes_one_valid_choice() -> None:
    server = start_demo.menu_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, page = request(f"{base}/")
        assert status == 200 and b"Techseed Geospatial Intelligence Demos" in page
        status, body = request(f"{base}/api/demos")
        assert status == 200 and json.loads(body)["title"] == "Techseed Geospatial Intelligence Demos"
        assert json.loads(body)["kiosk"] is False
        assert request(f"{base}/api/demo/start", {"scenario": "atlantis"})[0] == 400
        assert request(f"{base}/api/demo/start", {"scenario": "sundsvall2026", "kiosk": "yes"})[0] == 400
        assert request(f"{base}/api/demo/start", {"scenario": "sundsvall2026", "kiosk": True})[0] == 202
        thread.join(timeout=5)
        # The menu closes once chosen, with KIOSKLÄGE as chosen.
        assert not thread.is_alive() and (server.chosen, server.kiosk) == ("sundsvall2026", True)
    finally:
        server.shutdown()
        server.server_close()


def test_byt_demo_goes_back_to_the_menu_and_ctrl_c_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    started = []
    choices = iter([("sundsvall2026", True), ("vastmanland2014", True)])
    menus = []
    codes = iter([start_demo.MENU_EXIT, 0])
    monkeypatch.setattr(start_demo, "port_in_use", lambda port: False)
    monkeypatch.setattr(start_demo, "choose_demo", lambda kiosk=False, **options: menus.append(kiosk) or next(choices))
    monkeypatch.setattr(start_demo, "run_demo", lambda name, at, kiosk=False, **options: started.append((name, at, kiosk)) or next(codes))
    assert start_demo.main([]) == 0
    # KIOSKLÄGE chosen on the menu holds for the next demo, and the menu shows it again.
    assert started == [("sundsvall2026", None, True), ("vastmanland2014", None, True)] and menus == [False, True]

    # STARTA OM DEMO: the screens close and the same scenario starts again, from its saved start.
    started.clear()
    closed = []
    monkeypatch.setattr(start_demo.subprocess, "run", lambda command, **kwargs: closed.append(command[2:]))
    codes = iter([start_demo.RESTART_EXIT, 0])
    assert start_demo.main(["sundsvall2026", "--at", "2026-08-16T06:00:00Z"]) == 0
    assert started == [("sundsvall2026", "2026-08-16T06:00:00Z", False), ("sundsvall2026", None, False)]
    assert closed == [["tools.open_screens", "--close"]]

    started.clear()
    codes = iter([0])
    assert start_demo.main(["sundsvall2026", "--at", "2026-08-16T06:00:00Z", "--kiosk"]) == 0  # a name skips the menu
    assert started == [("sundsvall2026", "2026-08-16T06:00:00Z", True)]


class Process:
    def __init__(self, code: int | None) -> None:
        self.returncode = code

    def poll(self) -> int | None:
        return self.returncode


def test_kiosk_mode_starts_stopped_nodes_again_and_opens_the_screens_that_have_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    started, reopened = [], []
    fresh = Process(None)
    nodes = start_demo.look_after(Process(1), lambda: started.append(1) or fresh, lambda: ["main"], reopened.append)
    assert nodes is fresh and started == [1] and reopened == [["main"]]
    running = Process(None)
    assert start_demo.look_after(running, lambda: started.append(2), lambda: [], reopened.append) is running
    assert started == [1] and reopened == [["main"]]  # nothing to do while all runs
    # A screen is missing when pgrep finds no Chrome with its profile.
    answers = {"monitor": 0, "main": 1, "control": 0}
    asked = []
    monkeypatch.setattr(start_demo.open_screens, "running_command", lambda screen, browser: asked.append(browser) or [screen])
    monkeypatch.setattr(start_demo.subprocess, "run", lambda command, **kwargs: Process(answers[command[0]]))
    assert start_demo.missing_screens("edge") == ["main"] and asked == ["edge"] * 3  # the chosen browser's profiles


def test_kiosk_mode_starts_a_stopped_demo_again_and_only_kiosk_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    started, commands = [], []
    monkeypatch.setattr(start_demo, "port_in_use", lambda port: False)
    monkeypatch.setattr(start_demo.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(start_demo.subprocess, "run", lambda command, **kwargs: commands.append(command[2:]))

    def run(name, at, kiosk=False, **options):
        started.append((name, at, kiosk))
        outcome = next(outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
    monkeypatch.setattr(start_demo, "run_demo", run)
    # A crash, a demo that did not start, then Ctrl+C: started again each time, from its saved start.
    outcomes = iter([1, SystemExit("start_demo: the backend did not answer within 180 s"), 0])
    assert start_demo.main(["sundsvall2026", "--at", "2026-08-16T06:00:00Z", "--kiosk"]) == 0
    assert started == [("sundsvall2026", "2026-08-16T06:00:00Z", True), ("sundsvall2026", None, True), ("sundsvall2026", None, True)]
    assert commands == [["tools.open_screens", "--close"]] * 2
    # Without kiosk mode a crash ends start_demo, as before.
    started.clear()
    outcomes = iter([1])
    assert start_demo.main(["sundsvall2026"]) == 1 and len(started) == 1
