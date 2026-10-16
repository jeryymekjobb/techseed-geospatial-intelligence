"""Tests for the display profiles (app/backend/profiles.py): saved per scenario with the demo's start
and stop, read by the scenario engine at its start and at RESET, and saved with SPARA PROFIL
(save_profile); a scenario without one uses the older profile of its kind of incident."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from app.backend import lantmateriet, profiles, scenario, server
from app.backend.scenario_engine import CommandError, ScenarioEngine

START = datetime(2014, 7, 31, tzinfo=timezone.utc)
END = datetime(2014, 8, 15, tzinfo=timezone.utc)


def test_a_profile_is_saved_per_scenario_and_a_scenario_without_one_has_none(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    assert profiles.load("sundsvall2026", path) is None
    saved = profiles.save("sundsvall2026", ["radar", "natural"], ["offline"], path,
                          map_layers={"Nederbörd (SMHI radar)": True},
                          playback={"start_utc": "2026-08-14T00:00:00Z", "end_utc": "2026-08-20T00:00:00Z"})
    assert (saved["image_types"], saved["base_maps"], saved["map_layers"]) == (
        ["radar", "natural"], ["offline"], {"Nederbörd (SMHI radar)": True})
    assert saved["playback"] == {"start_utc": "2026-08-14T00:00:00Z", "end_utc": "2026-08-20T00:00:00Z"}
    assert saved["saved_utc"].endswith("Z") and saved["source"] == "scenario"
    profiles.save("skane2024", None, ["online"], path)
    assert profiles.load("sundsvall2026", path)["image_types"] == ["radar", "natural"]  # the other scenario's profile is kept
    assert profiles.load("skane2024", path)["image_types"] is None  # not ticked: the default
    assert profiles.load("skane2024", path)["playback"] is None  # no start and stop: the whole period
    path.write_text("not json", encoding="utf-8")
    assert profiles.load("sundsvall2026", path) is None


def test_a_scenario_without_a_profile_uses_the_older_one_of_its_kind_of_incident(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"flood": {"image_types": ["radarwater"], "base_maps": ["offline"],
                                          "saved_utc": "2026-10-09T08:36:51Z"}}), encoding="utf-8")
    older = profiles.load("sundsvall2026", path, incident="flood")
    assert (older["image_types"], older["source"], older["playback"]) == (["radarwater"], "incident", None)
    assert profiles.load("sundsvall2026", path) is None  # without the kind of incident
    profiles.save("sundsvall2026", ["natural"], None, path)
    assert profiles.load("sundsvall2026", path, incident="flood")["source"] == "scenario"
    assert profiles.load("skane2024", path, incident="flood")["image_types"] == ["radarwater"]  # the older one is kept


def test_the_osm_land_cover_is_not_taken_from_the_older_profile_but_from_the_scenario_s_own(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"flood": {"map_layers": {"Terräng (OSM)": True, "Ortnamn": False}}}), encoding="utf-8")
    assert profiles.load("vasternorrland2025", path, incident="flood")["map_layers"] == {"Ortnamn": False}
    profiles.save("vasternorrland2025", None, None, path, map_layers={"Terräng (OSM)": True})
    assert profiles.load("vasternorrland2025", path, incident="flood")["map_layers"] == {"Terräng (OSM)": True}


def test_the_speed_is_saved_and_one_outside_the_limits_is_not_kept(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    assert profiles.save("sundsvall2026", None, None, path, speed=1800)["speed"] == 1800.0
    assert profiles.save("skane2024", None, None, path)["speed"] is None  # not saved: the default
    for speed in [5, 10 * 86400, "fast", True]:
        assert profiles.save("sundsvall2026", None, None, path, speed=speed)["speed"] is None


def test_the_engine_starts_at_the_profiles_speed_and_reset_keeps_the_speed_in_use() -> None:
    engine = ScenarioEngine(START, END, profile=lambda: {"speed": 1800.0})
    assert engine.snapshot()["speed"] == 1800.0
    engine.command("speed", speed=60)
    assert engine.command("reset")["speed"] == 60.0
    assert ScenarioEngine(START, END, profile=lambda: {"speed": 5}).snapshot()["speed"] == 600.0  # outside the limits


def test_reading_aloud_is_saved_in_the_profile_and_on_without_it(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    assert profiles.save("sundsvall2026", None, None, path, speech=False)["speech"] is False
    assert profiles.save("skane2024", None, None, path)["speech"] is True  # on unless switched off
    assert profiles.load("sundsvall2026", path)["speech"] is False
    assert profiles.load("vastmanland2014", path, incident="wildfire") is None
    engine = ScenarioEngine(START, END, profile=lambda: {"speech": False})
    assert engine.snapshot()["status"]["speech"] is False
    assert engine.command("speech", target="on")["status"]["speech"] is True
    assert engine.command("reset")["status"]["speech"] is False  # RESET: the profile's, like the ticks
    assert ScenarioEngine(START, END).snapshot()["status"]["speech"] is True  # no profile: on
    assert ScenarioEngine(START, END, profile=lambda: {"image_types": None}).snapshot()["status"]["speech"] is True
    with pytest.raises(CommandError):
        engine.command("speech", target="loud")


def test_a_playback_window_that_is_not_a_window_is_not_kept(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    for window in [{"start_utc": "2026-08-20T00:00:00Z", "end_utc": "2026-08-14T00:00:00Z"},
                   {"start_utc": "2026-08-14T00:00:00Z"}, {"start_utc": "soon", "end_utc": "later"}, "2026-08-14"]:
        assert profiles.save("sundsvall2026", None, None, path, playback=window)["playback"] is None


def test_the_engine_starts_with_the_profile_and_reset_returns_to_it() -> None:
    saved = {"image_types": ["radar"], "base_maps": ["online"], "map_layers": {"Nederbörd (SMHI radar)": True}}
    engine = ScenarioEngine(START, END, profile=lambda: saved)
    initial = engine.snapshot()["status"]
    assert initial["image_types"] == ["radar"] and initial["base_maps"] == ["online"]
    assert initial["map_layers"] == {"Nederbörd (SMHI radar)": True}
    engine.command("image_types", target="natural")
    engine.command("base_maps", target="")
    engine.command("map_layer_off", target="Nederbörd (SMHI radar)")
    saved = {"image_types": ["water"], "base_maps": None,
             "map_layers": {"Nederbörd (SMHI radar)": False}}  # saved again meanwhile: RESET takes the latest
    status = engine.command("reset")["status"]
    assert (status["image_types"], status["base_maps"], status["map_layers"]) == (
        ["water"], None, {"Nederbörd (SMHI radar)": False})
    assert ScenarioEngine(START, END).snapshot()["status"]["image_types"] is None  # no profile: the screens' default


def test_the_engine_starts_with_the_profiles_playback_window_and_reset_keeps_the_window_in_use() -> None:
    saved = {"playback": {"start_utc": "2014-08-02T06:00:00Z", "end_utc": "2014-08-05T00:00:00Z"}}
    engine = ScenarioEngine(START, END, profile=lambda: saved)
    state = engine.snapshot()
    assert (state["clock_utc"], state["start_utc"], state["end_utc"]) == (
        "2014-08-02T06:00:00Z", "2014-08-02T06:00:00Z", "2014-08-05T00:00:00Z")
    assert (state["data_start_utc"], state["data_end_utc"]) == ("2014-07-31T00:00:00Z", "2014-08-15T00:00:00Z")
    assert engine.command("seek", at="2014-08-10T00:00:00Z")["finished"]  # a seek stays inside the window
    assert engine.snapshot()["clock_utc"] == "2014-08-05T00:00:00Z"
    assert engine.command("play")["clock_utc"] == "2014-08-02T06:00:00Z"  # PLAY after the stop: from the start
    state = engine.command("playback_window", target="2014-08-01T00:00:00Z/2014-08-03T00:00:00Z")
    assert (state["start_utc"], state["end_utc"]) == ("2014-08-01T00:00:00Z", "2014-08-03T00:00:00Z")
    engine.command("seek", at="2014-08-02T00:00:00Z")
    saved = {"playback": {"start_utc": "2014-08-04T00:00:00Z", "end_utc": "2014-08-06T00:00:00Z"}}  # saved again meanwhile
    state = engine.command("reset")  # RESET: the start of the window in use, not the saved one
    assert (state["clock_utc"], state["start_utc"], state["end_utc"]) == (
        "2014-08-01T00:00:00Z", "2014-08-01T00:00:00Z", "2014-08-03T00:00:00Z")
    other = {"playback": {"start_utc": "2026-08-14T00:00:00Z", "end_utc": "2026-08-20T00:00:00Z"}}  # not this period
    state = ScenarioEngine(START, END, profile=lambda: other).snapshot()
    assert (state["clock_utc"], state["end_utc"]) == ("2014-07-31T00:00:00Z", "2014-08-15T00:00:00Z")


def test_a_playback_window_outside_the_period_or_backwards_is_refused() -> None:
    engine = ScenarioEngine(START, END)
    for target in [None, "2014-08-01", "2014-08-03T00:00:00Z/2014-08-01T00:00:00Z",
                   "2014-07-30T00:00:00Z/2014-08-01T00:00:00Z", "2014-08-01T00:00:00Z/2014-08-16T00:00:00Z", "soon/later"]:
        with pytest.raises(CommandError):
            engine.command("playback_window", target=target)
    assert engine.snapshot()["start_utc"] == "2014-07-31T00:00:00Z"
    engine.command("seek", at="2014-08-10T00:00:00Z")
    state = engine.command("playback_window", target="2014-08-01T00:00:00Z/2014-08-03T00:00:00Z")
    assert state["clock_utc"] == "2014-08-03T00:00:00Z"  # the clock moves inside the new window


@pytest.fixture()
def base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profiles, "PROFILE_FILE", tmp_path / "display-profiles.json")
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None),
        "engine": ScenarioEngine(START, END, profile=server.scenario_profile),
        "control_token": None,
    })
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def post(url: str, body: dict) -> dict:
    request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def test_spara_profil_saves_effective_display_settings_and_reset_returns_to_them(
    base_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "base_maps", lambda _settings: [{"id": "offline"}, {"id": "online"}])
    monkeypatch.setattr(server, "map_layers", lambda _settings: [
        {"name": "Nederbörd (SMHI radar)", "default_2d": True, "default_3d": True},
        {"name": "Terräng (OSM)", "default_2d": True, "default_3d": False},
    ])
    command = f"{base_url}/api/scenario/command"
    post(command, {"command": "playback_window", "target": "2014-08-01T00:00:00Z/2014-08-03T00:00:00Z"})
    post(command, {"command": "speed", "speed": 1800})
    post(command, {"command": "speech", "target": "on"})
    answer = post(command, {"command": "save_profile"})
    assert answer["display_profile"]["speech"] is True
    assert answer["display_profile"]["speed"] == 1800.0
    assert answer["display_profile"]["base_maps"] == ["offline"]
    assert answer["display_profile"]["image_types"] is None
    assert answer["display_profile"]["map_layers"] == {
        "Nederbörd (SMHI radar)": True,
        "Terräng (OSM)": False,
    }
    assert answer["display_profile"]["playback"] == {"start_utc": "2014-08-01T00:00:00Z", "end_utc": "2014-08-03T00:00:00Z"}
    saved = json.loads((tmp_path / "display-profiles.json").read_text(encoding="utf-8"))[scenario.NAME]
    assert saved["base_maps"] == ["offline"]
    assert saved["map_layers"]["Nederbörd (SMHI radar)"] is True
    post(command, {"command": "base_maps", "target": "online"})
    post(command, {"command": "map_layer_off", "target": "Nederbörd (SMHI radar)"})
    post(command, {"command": "playback_window", "target": "2014-08-05T00:00:00Z/2014-08-06T00:00:00Z"})
    state = post(command, {"command": "reset"})
    assert state["status"]["base_maps"] == ["offline"]
    assert state["status"]["map_layers"]["Nederbörd (SMHI radar)"] is True
    # RESET keeps the start and stop in use; the saved ones apply when the backend starts.
    assert (state["clock_utc"], state["end_utc"]) == ("2014-08-05T00:00:00Z", "2014-08-06T00:00:00Z")
    restarted = ScenarioEngine(START, END, profile=server.scenario_profile)
    assert (restarted.snapshot()["clock_utc"], restarted.snapshot()["end_utc"]) == ("2014-08-01T00:00:00Z", "2014-08-03T00:00:00Z")
    assert restarted.snapshot()["speed"] == 1800.0
    # The screens take the demo's start and stop from the config, and the scenario's period beside them.
    playback = server.config(lantmateriet.Settings(None, None, None, None), restarted)["playback"]
    assert (playback["start_utc"], playback["end_utc"]) == ("2014-08-01T00:00:00Z", "2014-08-03T00:00:00Z")
    assert (playback["data_start_utc"], playback["data_end_utc"]) == (
        server.utc_text(scenario.PLAYBACK_START), server.utc_text(scenario.PLAYBACK_END))
    with urlopen(f"{base_url}/api/config", timeout=10) as response:
        assert json.loads(response.read())["layers"]["display_profile"]["base_maps"] == ["offline"]
