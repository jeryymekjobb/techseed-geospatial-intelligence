"""Sentinel-1's wind over the sea at each pass, for the scenarios that have it (tools/fetch_sentinel1_wind.py).

The radar measures the wind over the sea only as it passes, so the maps show a pass's arrows for
SHOW_HOURS after it and then nothing until the next; the log has a line at each pass. The wind is the
product's retrieval from the radar image, measured, not a model's: the screens say so beside
ERA5-Land's modelled wind.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario
from app.backend.met_forecast import COMPASS_WORDS, compass

LABEL = "Havsvind (Sentinel-1)"
# How long after a pass the maps keep its arrows.
SHOW_HOURS = 12


@lru_cache(maxsize=1)
def data() -> dict[str, Any] | None:
    path = scenario.SENTINEL1_WIND_DIR / "wind.json" if scenario.SENTINEL1_WIND_DIR else None
    if path is None or not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if loaded.get("passes") else None


def layer() -> dict[str, Any] | None:
    """What /api/config gives the screens: every pass with its arrows, and in words where the wind blew from."""
    loaded = data()
    if loaded is None:
        return None
    passes = [{**item, "from_words": COMPASS_WORDS[compass(item["from_deg"], 8)]} for item in loaded["passes"]]
    return {"label": LABEL, "attribution": scenario.ATTRIBUTION.get("sentinel", loaded["source"]), "show_hours": SHOW_HOURS,
            "passes": passes}
