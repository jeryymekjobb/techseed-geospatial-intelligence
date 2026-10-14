"""The orbital elements of the scenario's satellites, for the globe.

tools/fetch_tle_history.py writes them from Space-Track to the scenario's
unversioned TLE directory (for Västmanland 2014 data/tle/). The globe computes each satellite's position at the scenario clock
with satellite.js (SGP4) from the latest element set at or before that time.
Without the file the globe simply shows no satellites.

Only the satellites that send the scenario data to the ground are given (contributes): the
FIRMS satellites, those with known Sentinel-1 acquisitions and those of the scenario's images.
The others' element sets stay in the file, but no screen, log line or pass shows them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.backend import landsat, scenario

TLE_FILE = scenario.TLE_DIR / scenario.TLE_FILE_NAME
SOURCE_FILE = scenario.TLE_DIR / "SOURCE.json"
# What each satellite contributes to the demo, by NORAD number (the scenario's SATELLITE_ROLES).
ROLES = scenario.SATELLITE_ROLES
LABEL = scenario.SATELLITE_LABEL


def contributes(item: dict[str, Any], imaged: set[str]) -> bool:
    """Whether a satellite sends the scenario data: FIRMS detections, known acquisitions or one of its images."""
    return bool(item.get("firms") or item.get("acquisitions") or item["name"] in imaged)


@lru_cache(maxsize=1)
def satellites() -> dict[str, Any]:
    if not TLE_FILE.is_file():
        return {"available": False, "label": LABEL, "satellites": [],
                "note": "Banelementen är inte hämtade (tools/fetch_tle_history.py); globen visar inga satelliter."}
    data = json.loads(TLE_FILE.read_text(encoding="utf-8"))["satellites"]
    source = json.loads(SOURCE_FILE.read_text(encoding="utf-8")) if SOURCE_FILE.is_file() else {}
    fetched = source.get("fetched_utc", "okänt datum")
    # Satellites whose passes over the incident are known acquisitions rather than computed (Sentinel-1).
    acquisitions: dict[str, list[str]] = {}
    for item in scenario.SENTINEL1_ACQUISITIONS:
        acquisitions.setdefault(item["norad"], []).append(item["time_utc"])
    scenes = landsat.layer()
    imaged = {scene["satellite"] for scene in scenes["scenes"]} if scenes else set()
    items = [
        {"norad": norad, "name": entry["name"],
         **ROLES.get(norad, {"firms": None, "instrument": None, "role": "", "half_swath_km": None}),
         **({"acquisitions": acquisitions[norad]} if norad in acquisitions else {}),
         "elements": entry["elements"]}
        for norad, entry in data.items() if entry["elements"]
    ]
    return {
        "available": True,
        "label": LABEL,
        "source": f"Space-Track.org (gp_history), hämtad {fetched}",
        "satellites": [item for item in items if contributes(item, imaged)],
    }
