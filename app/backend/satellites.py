"""The 2014 orbital elements of the fire's satellites, for the globe.

tools/fetch_tle_history.py writes them from Space-Track to the unversioned
data/tle/. The globe computes each satellite's position at the scenario clock
with satellite.js (SGP4) from the latest element set at or before that time.
Without the file the globe simply shows no satellites.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import scenario

TLE_FILE = scenario.REPO_ROOT / "data" / "tle" / "tle-2014.json"
SOURCE_FILE = scenario.REPO_ROOT / "data" / "tle" / "SOURCE.json"
# What each satellite contributes to the demo; the FIRMS `satellite` field names the first three.
ROLES = {
    "27424": {"firms": "Aqua", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)"},
    "25994": {"firms": "Terra", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)"},
    "37849": {"firms": "SNPP", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)"},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation"},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen"},
}
LABEL = "Position 2014, beräknad ur banelement (SGP4) – inte en observation"


@lru_cache(maxsize=1)
def satellites() -> dict[str, Any]:
    if not TLE_FILE.is_file():
        return {"available": False, "label": LABEL, "satellites": [],
                "note": "Banelementen är inte hämtade (tools/fetch_tle_history.py); globen visar inga satelliter."}
    data = json.loads(TLE_FILE.read_text(encoding="utf-8"))["satellites"]
    source = json.loads(SOURCE_FILE.read_text(encoding="utf-8")) if SOURCE_FILE.is_file() else {}
    fetched = source.get("fetched_utc", "okänt datum")
    return {
        "available": True,
        "label": LABEL,
        "source": f"Space-Track.org (gp_history), hämtad {fetched}",
        "satellites": [
            {"norad": norad, "name": entry["name"], **ROLES.get(norad, {"firms": None, "instrument": None, "role": ""}),
             "elements": entry["elements"]}
            for norad, entry in data.items() if entry["elements"]
        ],
    }
