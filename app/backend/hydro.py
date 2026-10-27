"""SMHI's measured flows and lake levels for the flood scenarios that have them (tools/fetch_smhi_hydro.py).

/api/hydro gives each station's series over the period with the highest value measured
before it, so the screens can say when the water is the highest since measuring began, and
for how many days after (HYDRO_RECORD_HOLD_DAYS, None for the whole period).

A scenario's SMHI sea-level stations (tools/fetch_smhi_sea_level.py) are given the same way, as
levels with each day's highest hourly value at 00 UTC, since a playback of many years cannot show
the hours; `storms` gives the hourly peaks above SEA_LEVEL_STORM_CM for the log.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from functools import lru_cache
from typing import Any

from app.backend import scenario

HYDRO_DIR = scenario.HYDRO_DIR
SEA_LEVEL_DIR = scenario.SEA_LEVEL_DIR
# Peaks at least this far apart are separate storms.
STORM_GAP_HOURS = 72


@lru_cache(maxsize=1)
def stations() -> dict[str, Any] | None:
    """The stations with their observations, or None when the scenario has none."""
    catalogue_file = HYDRO_DIR / "stations.json" if HYDRO_DIR else None
    sea = sea_levels()
    if catalogue_file is None or not catalogue_file.is_file():
        return None if sea is None else {"source": sea["source"], "stations": sea["stations"]}
    catalogue = json.loads(catalogue_file.read_text(encoding="utf-8"))
    result = []
    for station in catalogue["stations"]:
        with (HYDRO_DIR / station["file"]).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        result.append({
            **{key: station[key] for key in ("id", "name", "kind", "unit", "latitude", "longitude", "measured_since", "earlier_max")},
            # SMHI's quality code: G checked and approved, anything else not yet checked.
            "unchecked": any(row["quality"] != "G" for row in rows), "record_hold_days": scenario.HYDRO_RECORD_HOLD_DAYS,
            "observations": [{"time_utc": row["time_utc"], "value": float(row["value"])} for row in rows],
        })
    if sea is not None:
        return {"source": f"{catalogue['source']}; {sea['source']}", "stations": result + sea["stations"]}
    return {"source": catalogue["source"], "stations": result}


def _sea_rows(station: dict[str, Any]) -> list[dict[str, Any]]:
    with (SEA_LEVEL_DIR / station["file"]).open(encoding="utf-8", newline="") as stream:
        return [{"time_utc": row["time_utc"], "value": float(row["value"]), "quality": row["quality"]} for row in csv.DictReader(stream)]


@lru_cache(maxsize=1)
def sea_levels() -> dict[str, Any] | None:
    """The sea-level stations as levels, each day's highest hourly value at 00 UTC, or None."""
    source_file = SEA_LEVEL_DIR / "SOURCE.json" if SEA_LEVEL_DIR else None
    if source_file is None or not source_file.is_file():
        return None
    source = json.loads(source_file.read_text(encoding="utf-8"))
    result = []
    for station in source["stations"]:
        days: dict[str, float] = {}
        rows = _sea_rows(station)
        for row in rows:
            day = row["time_utc"][:10]
            days[day] = max(days.get(day, row["value"]), row["value"])
        result.append({
            "id": f"sea-{station['station']}", "name": f"{scenario.SEA_LEVEL_STATIONS.get(station['station']) or station['name']} (havet)",
            "kind": "level", "unit": station["unit"], "sea": True, "height_system": station["height_system"],
            **{key: station[key] for key in ("latitude", "longitude", "measured_since", "earlier_max")},
            "unchecked": any(row["quality"] != "G" for row in rows), "record_hold_days": scenario.HYDRO_RECORD_HOLD_DAYS,
            "observations": [{"time_utc": f"{day}T00:00:00Z", "value": value} for day, value in sorted(days.items())],
        })
    return {"source": source["source"], "stations": result}


@lru_cache(maxsize=1)
def storms() -> list[dict[str, Any]]:
    """Each sea-level station's hourly peaks of at least SEA_LEVEL_STORM_CM, STORM_GAP_HOURS apart, in time order,
    and whether each was the highest since measuring began (above the earlier highest and every peak before it)."""
    source_file = SEA_LEVEL_DIR / "SOURCE.json" if SEA_LEVEL_DIR else None
    if source_file is None or not source_file.is_file():
        return []
    found = []
    for station in json.loads(source_file.read_text(encoding="utf-8"))["stations"]:
        rows = [row for row in _sea_rows(station) if row["value"] >= scenario.SEA_LEVEL_STORM_CM]
        peaks: list[dict[str, Any]] = []
        for row in sorted(rows, key=lambda item: -item["value"]):
            moment = datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00"))
            if all(abs((moment - peak["moment"]).total_seconds()) > STORM_GAP_HOURS * 3600 for peak in peaks):
                peaks.append({**row, "moment": moment})
        highest = (station["earlier_max"] or {}).get("value", float("-inf"))
        name = scenario.SEA_LEVEL_STATIONS.get(station["station"]) or station["name"]
        for peak in sorted(peaks, key=lambda item: item["moment"]):
            record = peak["value"] > highest
            highest = max(highest, peak["value"])
            found.append({"time_utc": peak["time_utc"], "station": name, "value_cm": peak["value"],
                          "height_system": station["height_system"], "record": record,
                          "measured_since": station["measured_since"]})
    return sorted(found, key=lambda item: item["time_utc"])
