"""Display profiles: image types, base maps, map-layer visibility, the demo's start and stop and
its playback speed, saved per scenario.

SPARA PROFIL in mission control saves the running demo's display settings and its playback window
(the demo's start and stop, within the scenario's data) for that scenario in
data/display-profiles.json, which is not in the repository: it belongs to the exhibition PC. The
demo starts with them; RESET returns to the display settings and keeps the start and stop in use.
A scenario without a profile of its own uses the
older profile of its kind of incident (wildfire or flood), saved before profiles were per scenario,
until SPARA PROFIL saves one for it. Profiles without map-layer visibility keep the scenario's
defaults for those layers; profiles without a playback window play the scenario's whole period,
and profiles without a speed play at the engine's default speed. The start, stop and speed apply
when the demo starts; RESET keeps those in use.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.backend.scenario_engine import MAX_SPEED, MIN_SPEED
from app.backend.scenarios import REPO_ROOT

PROFILE_FILE = Path(os.environ.get("TECHSEED_PROFILE_FILE") or REPO_ROOT / "data" / "display-profiles.json")
LIST_KEYS = ("image_types", "base_maps")


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _utc(value: Any) -> str | None:
    """A UTC time as the profile keeps it ("2026-08-14T00:00:00Z"), or None when it is not one."""
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _playback(raw: Any) -> dict[str, str] | None:
    """The demo's start and stop, or None when either is missing or the stop is not after the start."""
    if not isinstance(raw, dict):
        return None
    start, end = _utc(raw.get("start_utc")), _utc(raw.get("end_utc"))
    return {"start_utc": start, "end_utc": end} if start and end and start < end else None


def _speed(raw: Any) -> float | None:
    """The playback speed in simulated seconds per real second, or None when it is not a valid one."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw) if MIN_SPEED <= raw <= MAX_SPEED else None


def _layers(raw: Any) -> dict[str, bool] | None:
    return ({str(name): visible for name, visible in raw.items()
             if isinstance(name, str) and isinstance(visible, bool)} if isinstance(raw, dict) else None)


def load(scenario: str, path: Path | None = None, *, incident: str | None = None) -> dict[str, Any] | None:
    """The scenario's saved profile, else its kind of incident's older one, else None.

    A value it lacks is None, the default; `source` tells whether it is the scenario's own
    ("scenario") or the older one of the kind of incident ("incident")."""
    data = _read(path or PROFILE_FILE)
    profile, source = data.get(scenario), "scenario"
    if not isinstance(profile, dict) and incident:
        profile, source = data.get(incident), "incident"
    if not isinstance(profile, dict):
        return None
    clean = {key: [str(item) for item in profile[key]] if isinstance(profile.get(key), list) else None for key in LIST_KEYS}
    return {**clean, "map_layers": _layers(profile.get("map_layers")), "playback": _playback(profile.get("playback")),
            "speed": _speed(profile.get("speed")), "saved_utc": profile.get("saved_utc"), "source": source}


def save(scenario: str, image_types: list[str] | None, base_maps: list[str] | None, path: Path | None = None,
         *, map_layers: dict[str, bool] | None = None, playback: dict[str, str] | None = None,
         speed: float | None = None) -> dict[str, Any]:
    """Save display settings, playback window and speed for the scenario, keeping the other profiles; returns the profile."""
    target = path or PROFILE_FILE
    data = _read(target)
    data[scenario] = {"image_types": image_types, "base_maps": base_maps, "map_layers": _layers(map_layers),
                      "playback": _playback(playback), "speed": _speed(speed),
                      "saved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    temporary.replace(target)
    return load(scenario, target)
