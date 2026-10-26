#!/usr/bin/env python3
"""Fetch SMHI's measured sea level for the scenario's sea-level stations.

SMHI's open oceanographic observations (https://opendata-download-ocobs.smhi.se) give the
sea level by the hour (parameter 6, cm, at Skanör in RH2000). For each of the scenario's
SEA_LEVEL_STATIONS this tool reads every period SMHI offers - the quality-controlled
archive and, where there is one, the latest months - keeps the scenario's period, the
newer period's value where both have an hour, and notes the highest value before the
period with its time. It writes one CSV per station and SOURCE.json.

    TECHSEED_SCENARIO=falsterbo .venv/bin/python -m tools.fetch_smhi_sea_level
    .venv/bin/python -m tools.fetch_smhi_sea_level --station 30488 --start 2012-01-01 --end 2026-10-22 --out /tmp/sea

SMHI open data is licensed under Creative Commons Attribution 4.0 SE: name SMHI as the
source and state changes (here: period, newer period preferred, earlier highest value).
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.backend import scenario

API = "https://opendata-download-ocobs.smhi.se/api/version/latest"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
PARAMETER = 6  # Havsvattenstånd, timvärde
ATTRIBUTION = "SMHI öppna data, havsvattenstånd (CC BY 4.0 SE); urval av period, nyare period före arkivet"
# Older to newer: where two periods have the same hour, the later one's value is kept.
PERIODS = ("corrected-archive", "latest-months")


def station_url(station: str) -> str:
    return f"{API}/parameter/{PARAMETER}/station/{station}.json"


def data_url(station: str, period: str) -> str:
    return f"{API}/parameter/{PARAMETER}/station/{station}/period/{period}/data.csv"


def download(url: str) -> str:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=300) as response:
        return response.read().decode("utf-8-sig")


def periods(station_json: str) -> list[str]:
    """The periods SMHI offers for the station, older first, of those this tool reads."""
    offered = {item["key"] for item in json.loads(station_json).get("period", [])}
    return [period for period in PERIODS if period in offered]


def parse(text: str) -> dict[str, Any]:
    """The station's name, position and height system and its (time, value, quality) rows, times in UTC."""
    lines = text.lstrip("﻿").splitlines()
    name, _, latitude, longitude = lines[1].split(";")[:4]
    header = next(index for index, line in enumerate(lines) if line.startswith("Datum"))
    rows, height_system = [], None
    for line in lines[header + 1:]:
        fields = line.split(";")
        for field in fields[4:]:
            if field.startswith("Höjdsystem:"):
                height_system = field.split(":", 1)[1].strip()
        if len(fields) < 3 or not fields[0] or not fields[1]:
            continue
        moment = datetime.fromisoformat(fields[0]).replace(tzinfo=timezone.utc)
        rows.append((moment, float(fields[1]), fields[2]))
    return {"name": name, "latitude": float(latitude), "longitude": float(longitude),
            "height_system": height_system, "rows": rows}


def merge(parts: list[list[tuple[datetime, float, str]]]) -> list[tuple[datetime, float, str]]:
    """The rows of all periods in time order; a later period's value replaces an earlier one's for the same hour."""
    hours: dict[datetime, tuple[datetime, float, str]] = {}
    for rows in parts:
        for row in rows:
            hours[row[0]] = row
    return [hours[moment] for moment in sorted(hours)]


def series(rows: list[tuple[datetime, float, str]], start: date, end: date) -> dict[str, Any]:
    """The period's values and the highest value before it."""
    before = [row for row in rows if row[0].date() < start]
    record = max(before, key=lambda row: row[1]) if before else None
    return {
        "rows": [row for row in rows if start <= row[0].date() <= end],
        "earlier_max": None if record is None else {"value": record[1], "time_utc": record[0].strftime("%Y-%m-%dT%H:%M:%SZ")},
        "since": rows[0][0].strftime("%Y-%m-%d") if rows else None,
    }


def fetch_station(station: str, get: Callable[[str], str] | None = None) -> dict[str, Any]:
    """The station's details and its rows from every period SMHI offers."""
    get = get or download
    wanted = periods(get(station_url(station)))
    if not wanted:
        raise SystemExit(f"fetch_smhi_sea_level: SMHI offers no hourly sea level for station {station}")
    parsed, parts = None, []
    for period in wanted:
        try:
            text = get(data_url(station, period))
        except HTTPError as error:
            if error.code == 404:  # listed but empty, as a latest-months can be
                continue
            raise
        current = parse(text)
        parsed = parsed or current
        parsed["height_system"] = parsed["height_system"] or current["height_system"]
        parts.append(current["rows"])
    if parsed is None:
        raise SystemExit(f"fetch_smhi_sea_level: SMHI gave no sea level for station {station}")
    return {**parsed, "rows": merge(parts), "periods": wanted}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--station", action="append", help="an SMHI station id; repeat for more (default: the scenario's)")
    parser.add_argument("--start", type=date.fromisoformat, default=scenario.PERIOD_START)
    parser.add_argument("--end", type=date.fromisoformat, default=scenario.PERIOD_END)
    parser.add_argument("--out", type=Path, default=scenario.SEA_LEVEL_DIR)
    args = parser.parse_args(argv)
    stations = {station: None for station in args.station} if args.station else scenario.SEA_LEVEL_STATIONS
    if not stations or args.out is None:
        parser.exit(1, f"fetch_smhi_sea_level: the scenario {scenario.NAME} has no sea-level stations; give --station and --out\n")
    args.out.mkdir(parents=True, exist_ok=True)
    written = []
    for station, name in stations.items():
        fetched = fetch_station(station)
        result = series(fetched["rows"], args.start, args.end)
        file = f"sea-level-{station}.csv"
        with (args.out / file).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["time_utc", "value", "quality"])
            writer.writerows((moment.strftime("%Y-%m-%dT%H:%M:%SZ"), value, quality) for moment, value, quality in result["rows"])
        written.append({"station": station, "name": name or fetched["name"], "unit": "cm",
                        "height_system": fetched["height_system"], "file": file, "periods": fetched["periods"],
                        "latitude": fetched["latitude"], "longitude": fetched["longitude"],
                        "measured_since": result["since"], "earlier_max": result["earlier_max"],
                        "values": len(result["rows"]),
                        "quality_counts": {code: sum(1 for row in result["rows"] if row[2] == code)
                                           for code in sorted({row[2] for row in result["rows"]})}})
        print(f"{written[-1]['name']}: {len(result['rows'])} hourly values ({fetched['height_system']}), "
              f"earlier highest {result['earlier_max']}", flush=True)
    (args.out / "SOURCE.json").write_text(json.dumps({
        "source": ATTRIBUTION, "api": API, "parameter": PARAMETER,
        "quality_codes": {"G": "kontrollerade och godkända värden", "O": "okontrollerade värden"},
        "period": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stations": written,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
