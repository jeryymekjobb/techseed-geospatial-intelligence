"""Tests for the display profiles (app/backend/profiles.py): saved per kind of incident, read by
the scenario engine at its start and at RESET, and saved with SPARA PROFIL (save_profile)."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from app.backend import lantmateriet, profiles, scenario, server
from app.backend.scenario_engine import ScenarioEngine

START = datetime(2014, 7, 31, tzinfo=timezone.utc)
END = datetime(2014, 8, 15, tzinfo=timezone.utc)


def test_a_profile_is_saved_per_kind_of_incident_and_a_kind_without_one_has_none(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    assert profiles.load("flood", path) is None
    saved = profiles.save("flood", ["radar", "natural"], ["offline"], path,
                          map_layers={"Nederbörd (SMHI radar)": True})
    assert (saved["image_types"], saved["base_maps"], saved["map_layers"]) == (
        ["radar", "natural"], ["offline"], {"Nederbörd (SMHI radar)": True})
    assert saved["saved_utc"].endswith("Z")
    profiles.save("wildfire", None, ["online"], path)
    assert profiles.load("flood", path)["image_types"] == ["radar", "natural"]  # the other kind's profile is kept
    assert profiles.load("wildfire", path)["image_types"] is None  # not ticked: the default
    path.write_text("not json", encoding="utf-8")
    assert profiles.load("flood", path) is None


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


@pytest.fixture()
def base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profiles, "PROFILE_FILE", tmp_path / "display-profiles.json")
    handler = type("TestHandler", (server.Handler,), {
        "settings": lantmateriet.Settings(None, None, None, None),
        "engine": ScenarioEngine(START, END, profile=lambda: profiles.load(scenario.INCIDENT)),
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
    answer = post(command, {"command": "save_profile"})
    assert answer["display_profile"]["base_maps"] == ["offline"]
    assert answer["display_profile"]["image_types"] is None
    assert answer["display_profile"]["map_layers"] == {
        "Nederbörd (SMHI radar)": True,
        "Terräng (OSM)": False,
    }
    saved = json.loads((tmp_path / "display-profiles.json").read_text(encoding="utf-8"))[scenario.INCIDENT]
    assert saved["base_maps"] == ["offline"]
    assert saved["map_layers"]["Nederbörd (SMHI radar)"] is True
    post(command, {"command": "base_maps", "target": "online"})
    post(command, {"command": "map_layer_off", "target": "Nederbörd (SMHI radar)"})
    state = post(command, {"command": "reset"})["status"]
    assert state["base_maps"] == ["offline"]
    assert state["map_layers"]["Nederbörd (SMHI radar)"] is True
    with urlopen(f"{base_url}/api/config", timeout=10) as response:
        assert json.loads(response.read())["layers"]["display_profile"]["base_maps"] == ["offline"]
