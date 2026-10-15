#!/usr/bin/env python3
"""Fetch SMHI's daily rain (06-06 UTC) for the scenario's DAILY_RAIN_STATIONS.

Many of SMHI's stations report the rain once a day, at 06 UTC, for the 24 hours before
(parameter 5). This tool reads each station's quality-controlled archive, keeps the days that
end within the scenario's period and writes them with the station's place to
DAILY_RAIN_DIR/stations.json for app/backend/daily_rain.py.

    TECHSEED_SCENARIO=vasternorrland2025 .venv/bin/python -m tools.fetch_smhi_daily

SMHI open data is licensed under Creative Commons Attribution 4.0 SE.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.backend import scenario

API = "https://opendata-download-metobs.smhi.se/api/version/1.0"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
ATTRIBUTION = "SMHI öppna data (CC BY 4.0 SE): nederbörd per dygn 06–06 UTC"


def archive_url(station: str) -> str:
    return f"{API}/parameter/5/station/{station}/period/corrected-archive/data.csv"


def utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def parse(text: str) -> dict[str, Any]:
    """The station's latest place and its days: [{from_utc, to_utc, mm, quality}]."""
    lines = text.lstrip("﻿").splitlines()
    place_index = next(index for index, line in enumerate(lines) if line.startswith("Tidsperiod (fr.o.m)"))
    place = None
    for line in lines[place_index + 1:]:
        if not line.strip():
            break
        fields = line.split(";")
        place = (float(fields[3]), float(fields[4]))
    header = next(index for index, line in enumerate(lines) if line.startswith("Från Datum Tid (UTC)"))
    days = []
    for line in lines[header + 1:]:
        fields = line.split(";")
        if len(fields) < 5 or not fields[3]:
            continue
        # The archive's day starts a second after 06 UTC; the screens say 06-06.
        start = utc(fields[0]) - timedelta(seconds=1)
        days.append({"from_utc": start, "to_utc": utc(fields[1]), "mm": float(fields[3]), "quality": fields[4]})
    return {"latitude": place[0], "longitude": place[1], "days": days}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=scenario.DAILY_RAIN_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not scenario.DAILY_RAIN_STATIONS or args.out is None:
        parser.exit(1, f"fetch_smhi_daily: the scenario {scenario.NAME} has no DAILY_RAIN_STATIONS\n")
    first = datetime.combine(scenario.PERIOD_START, datetime.min.time(), tzinfo=timezone.utc)
    last = datetime.combine(scenario.PERIOD_END, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=2)
    stations = []
    for key, name in scenario.DAILY_RAIN_STATIONS.items():
        with urlopen(Request(archive_url(key), headers={"User-Agent": USER_AGENT}), timeout=120) as response:
            parsed = parse(response.read().decode("utf-8"))
        days = [{**day, "from_utc": day["from_utc"].strftime("%Y-%m-%dT%H:%M:%SZ"), "to_utc": day["to_utc"].strftime("%Y-%m-%dT%H:%M:%SZ")}
                for day in parsed["days"] if first < day["to_utc"] <= last]
        stations.append({"id": key, "name": name, "latitude": parsed["latitude"], "longitude": parsed["longitude"], "days": days})
        print(f"{name}: {len(days)} days, most {max((day['mm'] for day in days), default=0)} mm")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "stations.json").write_text(json.dumps({
        "source": API, "parameter": 5, "attribution": ATTRIBUTION,
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stations": stations,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
