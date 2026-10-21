"""MTG's instability indices round the incident (tools/fetch_meteosat_gii.py).

The K index and lifted index from FCI's infrared channels say how favourable the air was for
thunderstorms; they have values only where the sky was clear, so they tell of the hours before
the clouds. The panel gives the latest values with the time (and, once clouds cover the area,
the last clear ones), and the log says the first time each day the K index reaches K_HIGH. The
classes are a rule of thumb, which the screens say.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario

FILE = scenario.METEOSAT_GII_FILE
LABEL = "Åskpotential (Meteosat)"
# In the form EUMETSAT's data policy (article 6.3) asks for, with the year the demo shows it.
ATTRIBUTION = "Contains modified EUMETSAT Meteosat product 2026 (MTG Global Instability Indices, CC BY 4.0)"
K_HIGH = 30.0
# The K index's classes by a rule of thumb: below 20 low, 20-30 moderate, 30-35 high, above 35 very high.
K_CLASSES = ((20.0, "låg"), (30.0, "måttlig"), (35.0, "hög"), (float("inf"), "mycket hög"))


def k_class(k: float) -> str:
    return next(name for limit, name in K_CLASSES if k < limit)


@lru_cache(maxsize=1)
def data() -> dict[str, Any] | None:
    if FILE is None or not FILE.is_file():
        return None
    loaded = json.loads(FILE.read_text(encoding="utf-8"))
    return loaded if loaded.get("times") else None


def events(times: list[dict[str, Any]], high: float = K_HIGH) -> list[dict[str, Any]]:
    """The first time each day the highest K index reaches `high`."""
    found, days = [], set()
    for item in times:
        if item.get("k_max") is not None and item["k_max"] >= high and item["time_utc"][:10] not in days:
            days.add(item["time_utc"][:10])
            found.append({"time_utc": item["time_utc"], "k_max": item["k_max"], "class": k_class(item["k_max"])})
    return found


def layer() -> dict[str, Any] | None:
    """The times with their summaries (without the fields), the log's events and the classes, or None."""
    loaded = data()
    if loaded is None:
        return None
    times = [{key: value for key, value in item.items() if key != "points"} for item in loaded["times"]]
    for item in times:
        if item.get("k_max") is not None:
            item["class"] = k_class(item["k_max"])
    return {"label": LABEL, "attribution": ATTRIBUTION, "times": times, "events": events(times)}
