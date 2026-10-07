#!/usr/bin/env python3
"""Fetch SMHI's measured flows and lake levels for the scenario's hydrological stations.

SMHI's open hydrological observations (https://opendata-download-hydroobs.smhi.se) give
the flow every 15 minutes (parameter 2, m³/s) and the water level by the day (parameter
3, cm in the station's height system). For each of the scenario's HYDRO_STATIONS
("station:parameter") this tool reads the quality-controlled archive, keeps the
scenario's period - the flows as hourly means, the levels by the day at 00 UTC - and
notes the highest value before the period with its date, so the screens can say when a
value is the highest since measuring began. It writes one CSV per series and
stations.json.

    TECHSEED_SCENARIO=skane2024 .venv/bin/python -m tools.fetch_smhi_hydro

SMHI open data is licensed under Creative Commons Attribution 4.0 SE: name SMHI as
the source and state changes (here: period, hourly means, earlier highest value).
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.backend import scenario

API = "https://opendata-download-hydroobs.smhi.se/api/version/latest"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
ATTRIBUTION = "SMHI öppna data, hydrologiska observationer (CC BY 4.0 SE); urval av period, timmedelvärden"
KINDS = {2: ("flow", "m³/s"), 3: ("level", "cm")}


def archive_url(station: str, parameter: int) -> str:
    return f"{API}/parameter/{parameter}/station/{station}/period/corrected-archive/data.csv"


def download(url: str) -> str:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=300) as response:
        return response.read().decode("utf-8-sig")


def parse(text: str) -> dict[str, Any]:
    """The station's name and position and its (time, value, quality) rows, times in UTC."""
    lines = text.lstrip("﻿").splitlines()
    name, _, _, latitude, longitude = lines[1].split(";")[:5]
    header = next(index for index, line in enumerate(lines) if line.startswith("Datum"))
    rows = []
    for line in lines[header + 1:]:
        fields = line.split(";")
        if len(fields) < 3 or not fields[0] or not fields[1]:
            continue
        stamp = fields[0]
        # Flows have a time (UTC); levels only a day, given in Swedish summer time: taken as that day's 00 UTC.
        moment = datetime.fromisoformat(stamp if " " in stamp else f"{stamp} 00:00:00").replace(tzinfo=timezone.utc)
        rows.append((moment, float(fields[1]), fields[2]))
    return {"name": name.title(), "latitude": float(latitude), "longitude": float(longitude), "rows": rows}


def hourly_means(rows: list[tuple[datetime, float, str]]) -> list[tuple[datetime, float, str]]:
    """Each hour's mean of the values that start in it; the quality is the hour's worst (O before G)."""
    hours: dict[datetime, list[tuple[float, str]]] = defaultdict(list)
    for moment, value, quality in rows:
        hours[moment.replace(minute=0, second=0, microsecond=0)].append((value, quality))
    return [(hour, round(sum(v for v, _ in items) / len(items), 3), "O" if any(q != "G" for _, q in items) else "G")
            for hour, items in sorted(hours.items())]


def series(parsed: dict[str, Any], parameter: int, start: date, end: date) -> dict[str, Any]:
    """The period's values and the highest value before it."""
    rows = parsed["rows"]
    before = [row for row in rows if row[0].date() < start]
    inside = [row for row in rows if start <= row[0].date() <= end]
    if parameter == 2:
        inside = hourly_means(inside)
    record = max(before, key=lambda row: row[1]) if before else None
    return {
        "rows": inside,
        "earlier_max": None if record is None else {"value": record[1], "time_utc": record[0].strftime("%Y-%m-%dT%H:%M:%SZ")},
        "since": rows[0][0].strftime("%Y-%m-%d") if rows else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--start", type=date.fromisoformat, default=scenario.PERIOD_START)
    parser.add_argument("--end", type=date.fromisoformat, default=scenario.PERIOD_END)
    parser.add_argument("--out", type=Path, default=scenario.HYDRO_DIR)
    args = parser.parse_args(argv)
    if not scenario.HYDRO_STATIONS or args.out is None:
        parser.exit(1, f"fetch_smhi_hydro: the scenario {scenario.NAME} has no hydrological stations\n")
    args.out.mkdir(parents=True, exist_ok=True)
    stations = []
    for key, name in scenario.HYDRO_STATIONS.items():
        station, parameter = key.split(":")
        kind, unit = KINDS[int(parameter)]
        parsed = parse(download(archive_url(station, int(parameter))))
        result = series(parsed, int(parameter), args.start, args.end)
        file = f"{kind}-{station}.csv"
        with (args.out / file).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["time_utc", "value", "quality"])
            writer.writerows((moment.strftime("%Y-%m-%dT%H:%M:%SZ"), value, quality) for moment, value, quality in result["rows"])
        stations.append({"id": key, "station": station, "name": name, "kind": kind, "unit": unit, "file": file,
                         "latitude": parsed["latitude"], "longitude": parsed["longitude"],
                         "measured_since": result["since"], "earlier_max": result["earlier_max"], "values": len(result["rows"])})
        print(f"{name} ({kind}): {len(result['rows'])} values, earlier highest {result['earlier_max']}", flush=True)
    (args.out / "stations.json").write_text(json.dumps({
        "source": ATTRIBUTION, "api": API, "period": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stations": stations,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
