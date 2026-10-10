"""Display profiles: image types, base maps and map-layer visibility, saved per incident kind.

SPARA PROFIL in mission control saves the running demo's display settings for its kind of incident
(wildfire or flood) in data/display-profiles.json, which is not in the repository: it belongs to
the exhibition PC. Every demo of that kind starts with them, and RESET returns to them. Older
profiles without map-layer visibility keep the scenario's defaults for those layers.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.backend.scenarios import REPO_ROOT

PROFILE_FILE = Path(os.environ.get("TECHSEED_PROFILE_FILE") or REPO_ROOT / "data" / "display-profiles.json")
LIST_KEYS = ("image_types", "base_maps")


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load(incident: str, path: Path | None = None) -> dict[str, Any] | None:
    """The saved profile of the kind of incident, or None; a value it lacks is None, the default."""
    profile = _read(path or PROFILE_FILE).get(incident)
    if not isinstance(profile, dict):
        return None
    clean = {key: [str(item) for item in profile[key]] if isinstance(profile.get(key), list) else None for key in LIST_KEYS}
    raw_layers = profile.get("map_layers")
    layers = ({str(name): visible for name, visible in raw_layers.items()
               if isinstance(name, str) and isinstance(visible, bool)} if isinstance(raw_layers, dict) else None)
    return {**clean, "map_layers": layers, "saved_utc": profile.get("saved_utc")}


def save(incident: str, image_types: list[str] | None, base_maps: list[str] | None, path: Path | None = None,
         *, map_layers: dict[str, bool] | None = None) -> dict[str, Any]:
    """Save display settings for the incident kind, keeping the other profiles; returns the profile."""
    target = path or PROFILE_FILE
    data = _read(target)
    clean_layers = ({str(name): visible for name, visible in map_layers.items()
                     if isinstance(name, str) and isinstance(visible, bool)} if isinstance(map_layers, dict) else None)
    data[incident] = {"image_types": image_types, "base_maps": base_maps, "map_layers": clean_layers,
                      "saved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    temporary.replace(target)
    return load(incident, target)
