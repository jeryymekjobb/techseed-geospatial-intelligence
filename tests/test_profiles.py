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
    saved = profiles.save("flood", ["radar", "natural"], ["offline"], path)
    assert (saved["image_types"], saved["base_maps"]) == (["radar", "natural"], ["offline"]) and saved["saved_utc"].endswith("Z")
    profiles.save("wildfire", None, ["online"], path)
    assert profiles.load("flood", path)["image_types"] == ["radar", "natural"]  # the other kind's profile is kept
    assert profiles.load("wildfire", path)["image_types"] is None  # not ticked: the default
    path.write_text("not json", encoding="utf-8")
    assert profiles.load("flood", path) is None


def test_the_engine_starts_with_the_profile_and_reset_returns_to_it() -> None:
    saved = {"image_types": ["radar"], "base_maps": ["online"]}
    engine = ScenarioEngine(START, END, profile=lambda: saved)
    assert engine.snapshot()["status"]["image_types"] == ["radar"] and engine.snapshot()["status"]["base_maps"] == ["online"]
    engine.command("image_types", target="natural")
    engine.command("base_maps", target="")
    saved = {"image_types": ["water"], "base_maps": None}  # saved again meanwhile: RESET takes the latest
    status = engine.command("reset")["status"]
    assert (status["image_types"], status["base_maps"]) == (["water"], None)
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


def test_spara_profil_saves_the_ticks_shown_and_reset_returns_to_them(base_url: str, tmp_path: Path) -> None:
    command = f"{base_url}/api/scenario/command"
    post(command, {"command": "base_maps", "target": "online"})
    answer = post(command, {"command": "save_profile"})
    assert answer["display_profile"]["base_maps"] == ["online"] and answer["display_profile"]["image_types"] is None
    assert json.loads((tmp_path / "display-profiles.json").read_text(encoding="utf-8"))[scenario.INCIDENT]["base_maps"] == ["online"]
    post(command, {"command": "base_maps", "target": ""})
    assert post(command, {"command": "reset"})["status"]["base_maps"] == ["online"]
    with urlopen(f"{base_url}/api/config", timeout=10) as response:
        assert json.loads(response.read())["layers"]["display_profile"]["base_maps"] == ["online"]
