"""SMHI's rain by the day (06-06 UTC) at the stations that report so (tools/fetch_smhi_daily.py).

Such a station gives one sum for the 24 hours to 06 UTC, so the screens show a day's sum only
when its day has ended. The flood's assessment counts them with the hourly gauges in its rain
over five days (flood_assessment.py).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from app.backend import scenario

LABEL = "Dygnsregn (SMHI)"


def stations() -> list[dict[str, Any]]:
    """The stations with their days, or an empty list when the scenario has none."""
    directory = scenario.DAILY_RAIN_DIR
    path = directory / "stations.json" if directory else None
    if path is None or not path.is_file():
        return []
    return [station for station in json.loads(path.read_text(encoding="utf-8"))["stations"] if station["days"]]


def layer() -> dict[str, Any] | None:
    """What /api/config gives the screens, or None without daily stations."""
    items = stations()
    if not items:
        return None
    return {"label": LABEL, "attribution": "SMHI öppna data (CC BY 4.0 SE): nederbörd per dygn 06–06 UTC", "stations": items}


def upstream_stations() -> list[dict[str, Any]]:
    """The stations upstream in the river (UPSTREAM_RAIN_STATIONS), apart from the assessment's."""
    path = scenario.UPSTREAM_RAIN_DIR / "stations.json" if scenario.UPSTREAM_RAIN_DIR else None
    if path is None or not path.is_file():
        return []
    return [station for station in json.loads(path.read_text(encoding="utf-8"))["stations"] if station["days"]]


def upstream_days(items: list[dict[str, Any]], notice_mm: float) -> list[dict[str, Any]]:
    """For the log: each day that ended with at least notice_mm at a station, those stations wettest first."""
    by_end: dict[str, list[dict[str, Any]]] = {}
    for station in items:
        for day in station["days"]:
            if day["mm"] >= notice_mm:
                by_end.setdefault(day["to_utc"], []).append({"name": station["name"], "mm": day["mm"]})
    return [{"to_utc": end, "stations": sorted(found, key=lambda item: -item["mm"])} for end, found in sorted(by_end.items())]


def upstream_layer() -> dict[str, Any] | None:
    """What /api/config gives the screens for the rain upstream, or None without it. Not in the assessment."""
    items = upstream_stations()
    if not items:
        return None
    return {"label": scenario.UPSTREAM_RAIN_LABEL, "attribution": "SMHI öppna data (CC BY 4.0 SE): nederbörd per dygn 06–06 UTC",
            "stations": items, "notice_mm": scenario.UPSTREAM_RAIN_NOTICE_MM,
            "days": upstream_days(items, scenario.UPSTREAM_RAIN_NOTICE_MM)}


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def sum_since(station: dict[str, Any], clock: datetime, span: timedelta) -> float:
    """Millimetres in the days that ended within the span up to the clock."""
    return round(sum(day["mm"] for day in station["days"] if clock - span < parse_utc(day["to_utc"]) <= clock), 1)
