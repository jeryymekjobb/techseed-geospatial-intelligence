"""Meteosat's cloud top height over the incident every 15 minutes (tools/fetch_meteosat_cth.py).

Rising cloud tops show a storm building before its rain reaches the ground. The panel draws the
mean cloud top height over the map area against the clock, the map layer colours the cells of the
area and its neighbourhood by height, and the log says when the mean passes THRESHOLDS_KM. The
grid is coarse this far north (about ten cells over Kramfors' map area), so it shows the storm
system, not a single cell. Meteosat's product, not a forecast: the screens say so.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario

FILE = scenario.METEOSAT_CTH_FILE
LABEL = "Molntoppar (Meteosat)"
# In the form EUMETSAT's data policy (article 6.3) asks for, with the year the demo shows it.
ATTRIBUTION = "Contains modified EUMETSAT Meteosat product 2026 (MSG Cloud Top Height, CC BY 4.0)"
# The log's lines when the mean cloud top over the map area rises past these, and when it falls
# below the lowest again.
THRESHOLDS_KM = (8.0, 10.0)
# A threshold counts as left only when the mean is this far below it, so a mean hovering round one
# does not give a line every quarter (Sundsvall's nine showery days).
HYSTERESIS_KM = 1.0


@lru_cache(maxsize=1)
def data() -> dict[str, Any] | None:
    if FILE is None or not FILE.is_file():
        return None
    loaded = json.loads(FILE.read_text(encoding="utf-8"))
    return loaded if loaded.get("quarters") else None


def events(quarters: list[dict[str, Any]], thresholds: tuple[float, ...] = THRESHOLDS_KM,
           hysteresis: float = HYSTERESIS_KM) -> list[dict[str, Any]]:
    """The quarters the mean cloud top rises past a threshold it was below, and those it falls
    HYSTERESIS_KM below the lowest threshold again, in time order."""
    found, level = [], 0  # how many thresholds the mean has passed and not left
    for item in quarters:
        mean = item.get("mean_km")
        if mean is None:
            continue
        reached = sum(mean >= limit for limit in thresholds)
        kept = sum(mean >= limit - hysteresis for limit in thresholds[:level])
        now = max(reached, kept)
        if now > level:
            found.append({"time_utc": item["time_utc"], "kind": "up", "km": thresholds[now - 1], "mean_km": mean})
        elif now == 0 and level > 0:
            found.append({"time_utc": item["time_utc"], "kind": "down", "km": thresholds[0] - hysteresis, "mean_km": mean})
        level = now
    return found


def layer() -> dict[str, Any] | None:
    """The cells, every quarter's heights (km, None where clear), the series and the log's events."""
    loaded = data()
    if loaded is None:
        return None
    quarters = loaded["quarters"]
    return {
        "label": LABEL, "attribution": ATTRIBUTION, "thresholds_km": list(THRESHOLDS_KM),
        "cells": [{"corners": cell["corners"], "in_area": cell["in_area"]} for cell in loaded["cells"]],
        "quarters": [{"time_utc": item["time_utc"], "mean_km": item["mean_km"], "cloud_pct": item["cloud_pct"],
                      "heights_km": [None if height is None else round(height / 1000, 1) for height in item["heights_m"]]}
                     for item in quarters],
        "events": events(quarters),
    }
