"""The yearly shoreline lines of a coastal erosion scenario (tools/derive_shorelines.py).

Each line is the dune vegetation edge in one Sentinel-2 image, derived, not measured on the
ground, with an uncertainty of one to two pixels; the screens draw those taken up to the clock.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario


@lru_cache(maxsize=1)
def lines() -> dict[str, Any] | None:
    """The lines as GeoJSON, each with its image's role label (LANDSAT_ROLES, "Före Babet"), or None
    when the scenario has none."""
    path = scenario.SHORELINE_FILE
    if path is None or not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for feature in data["features"]:
        role = feature["properties"]["role"]
        feature["properties"]["label"] = scenario.LANDSAT_ROLES.get(role, role)
    return data


def layer() -> dict[str, Any] | None:
    """The layer for /api/config: its label, credit, where the lines are and the close view."""
    data = lines()
    if data is None:
        return None
    return {"label": data["label"], "attribution": data["attribution"], "uncertainty_m": data["uncertainty_m"],
            "url": "/api/shorelines", "view": scenario.SHORELINE_VIEW}
