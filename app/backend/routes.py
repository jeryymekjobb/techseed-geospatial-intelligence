"""Roads and railways the incident damaged, and those under heavy rain.

Two layers, kept apart because one is documented and the other computed:

- the scenario's ROUTE_IMPACTS, roads and railways a report says were damaged, with their time
  and an approximate place; the screens show each when the scenario clock reaches it, in the
  log (read aloud) and on the maps;
- ROUTE_EXPOSURE_FILE (tools/derive_route_exposure.py): OSM's larger roads and the railways in
  pieces, with the rain SMHI's radar estimates fell on each since the playback's start, hour by
  hour. The maps colour a piece once it passes EXPOSURE_THRESHOLDS_MM. That is rain, not damage.
"""

from __future__ import annotations

import json
from typing import Any

from app.backend import scenario

IMPACT_LABEL = "Skadade vägar och järnvägar (Länsstyrelsen)"
EXPOSURE_LABEL = "Vägar och järnvägar i kraftigt regn (beräknat ur radar)"
# Rain since the playback's start that colours a piece: heavy, then very heavy.
EXPOSURE_THRESHOLDS_MM = (50.0, 80.0)


def impacts() -> list[dict[str, Any]]:
    """The documented damage, oldest first, each with the report as its source."""
    return sorted(({**item, "source": scenario.ROUTE_REPORT} for item in scenario.ROUTE_IMPACTS),
                  key=lambda item: item["time_utc"])


def exposure() -> dict[str, Any] | None:
    """The computed pieces (tools/derive_route_exposure.py), or None when the scenario has none."""
    path = scenario.ROUTE_EXPOSURE_FILE
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def layer() -> dict[str, Any] | None:
    """What /api/config gives the screens, or None when the scenario has neither layer."""
    documented = impacts()
    computed = exposure()
    if not documented and computed is None:
        return None
    return {
        "impact_label": IMPACT_LABEL,
        "impacts": documented,
        "exposure_label": EXPOSURE_LABEL if computed is not None else None,
        "exposure_url": "/api/routes/exposure" if computed is not None else None,
        "thresholds_mm": list(EXPOSURE_THRESHOLDS_MM),
        "attribution": "Skador: Länsstyrelsen Västernorrland, utredning 2026; vägar och järnvägar © OpenStreetMap contributors",
    }


def exposure_class(cumulative_mm: list[float], hours_since_start: float,
                   thresholds: tuple[float, ...] = EXPOSURE_THRESHOLDS_MM) -> int:
    """0 below the first threshold, 1 above it, 2 above the second, at a moment of the playback.

    `cumulative_mm[i]` is the rain from the playback's start to the end of hour i; before the
    first hour has passed nothing has fallen yet."""
    index = int(hours_since_start) - 1
    if index < 0 or not cumulative_mm:
        return 0
    rain = cumulative_mm[min(index, len(cumulative_mm) - 1)]
    return sum(rain >= limit for limit in thresholds)
