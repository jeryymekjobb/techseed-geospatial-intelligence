"""EFAS's river-flow forecasts as issued, for the flood scenarios that have them (tools/fetch_efas_forecasts.py).

/api/hydro gives each station with forecasts its issues (hydro.py), so the flow chart can draw the
latest one issued by the scenario clock beside the measured flow. `issues` gives, for the log, each
issue's highest flow at the first of EFAS_STATIONS. An issue counts as available AVAILABLE_AFTER_HOURS
after its run (an assumption, kept in the file). EFAS's forecasts are information, not a flood warning.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario

LABEL = "EFAS-prognos – information, inte en varning"


@lru_cache(maxsize=1)
def data() -> dict[str, Any] | None:
    path = scenario.EFAS_DIR / "forecasts.json" if scenario.EFAS_DIR else None
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def by_station() -> dict[str, list[dict[str, Any]]]:
    """Each station's issues by its /api/hydro id."""
    loaded = data()
    return {station["id"]: station["issues"] for station in loaded["stations"]} if loaded else {}


def issues() -> list[dict[str, Any]]:
    """For the log: each issue's highest forecast flow at the first station, and when it comes."""
    loaded = data()
    if not loaded or not loaded["stations"]:
        return []
    station = loaded["stations"][0]
    result = []
    for issue in station["issues"]:
        peak = max(issue["values"], key=lambda item: item["value"])
        result.append({"issued_utc": issue["issued_utc"], "available_utc": issue["available_utc"], "station": station["name"],
                       "peak_value": peak["value"], "peak_time_utc": peak["time_utc"]})
    return result


def layer() -> dict[str, Any] | None:
    """What /api/config gives the screens, or None without forecasts."""
    loaded = data()
    if not loaded:
        return None
    return {"label": LABEL, "attribution": loaded["source"], "available_after_hours": loaded["available_after_hours"],
            "issues": issues()}
