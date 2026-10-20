"""LSA SAF's fire risk (FRM v3) over the incident, a map a day (tools/fetch_meteosat_frm.py).

Each day's map is valid at 12:00 UTC, so the screens show it from then on: the risk class (1 low
to 5 extreme) and the FWI on a 0.05° grid, and at the fire the class and FWI the panel names.
The log has a line when the class at the fire changes. The archive is computed with ERA5's
weather and calibrated with satellite fire observations, so the screens say "Meteosat och ERA5";
it stands beside the demo's own FWI from the forecast and replaces neither.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario

FILE = scenario.METEOSAT_FRM_FILE
LABEL = "Brandrisk (LSA SAF)"
# In the form EUMETSAT's data policy (article 6.3) asks for, with the year the demo shows it.
ATTRIBUTION = "Contains modified EUMETSAT Meteosat product 2026 (LSA SAF FRM v3, CC BY 4.0)"
RISK_NAMES = {1: "låg", 2: "måttlig", 3: "hög", 4: "mycket hög", 5: "extrem"}


@lru_cache(maxsize=1)
def grid() -> dict[str, Any] | None:
    """The fetched grid: latitudes, longitudes and the days with their FWI, risk, FFMC and DC."""
    if FILE is None or not FILE.is_file():
        return None
    data = json.loads(FILE.read_text(encoding="utf-8"))
    return data if data.get("days") else None


def nearest(values: list[float], target: float) -> int:
    return min(range(len(values)), key=lambda index: abs(values[index] - target))


def at_fire(data: dict[str, Any], latitude: float, longitude: float) -> list[dict[str, Any]]:
    """Each day's class and indices in the cell nearest the fire."""
    row, column = nearest(data["latitudes"], latitude), nearest(data["longitudes"], longitude)
    return [{"date": day["date"], "valid_utc": day["valid_utc"], "risk": day["risk"][row][column],
             "fwi": day["fwi"][row][column], "ffmc": day["ffmc"][row][column], "dc": day["dc"][row][column]}
            for day in data["days"]]


def changes(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For the log: the first day's class and every day the class at the fire changes."""
    found, previous = [], None
    for day in series:
        if day["risk"] is None or day["risk"] == previous:
            continue
        found.append({**day, "name": RISK_NAMES.get(day["risk"], str(day["risk"])),
                      "direction": "start" if previous is None else "up" if day["risk"] > previous else "down"})
        previous = day["risk"]
    return found


def layer() -> dict[str, Any] | None:
    """The maps' grid, the panel's values at the fire and the log's changes, or None without data."""
    data = grid()
    if data is None:
        return None
    series = at_fire(data, *scenario.FIRE_CENTRE)
    return {"label": LABEL, "attribution": ATTRIBUTION, "risk_names": RISK_NAMES, "cell_deg": data["cell_deg"],
            "latitudes": data["latitudes"], "longitudes": data["longitudes"],
            "days": [{"valid_utc": day["valid_utc"], "risk": day["risk"], "fwi": day["fwi"]} for day in data["days"]],
            "at_fire": series, "changes": changes(series)}
