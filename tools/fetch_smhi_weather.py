#!/usr/bin/env python3
"""Fetch hourly SMHI weather observations for stations and a period.

Downloads the quality-controlled archive (`corrected-archive`) of SMHI's
meteorological observations API for each station and parameter, keeps the
period, and writes one merged hourly CSV per station plus `stations.json`.
`--period latest-months` reads the last four months instead, for a period the
archive does not reach; SMHI may not have quality-controlled them yet (quality flag Y).
`--period both` reads both, for a long period that ends in the last months; where
both have an hour, the latest months' value is kept.
`--parameters` limits the parameters, for stations that measure only some of
them, such as precipitation gauges.

The stations in LOCAL_TIME_STATIONS stamp their hours in Swedish local time,
though SMHI's files say UTC; their rows are moved to UTC as they are read.

SMHI open data is licensed under Creative Commons Attribution 4.0 SE: name SMHI
as the source and state changes (here: period selection, merging of parameters
and, for those stations, the time moved to UTC). Only the Python standard library
is used.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

API = "https://opendata-download-metobs.smhi.se/api/version/1.0"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (exhibition demonstrator)"
ATTRIBUTION = "SMHI öppna data, meteorologiska observationer (CC BY 4.0 SE); urval av period och sammanslagning av parametrar"
# SMHI parameter key -> output column (all hourly values).
PARAMETERS = {
    1: "temp_c",          # Lufttemperatur, momentanvärde 1 gång/tim
    6: "rh_pct",          # Relativ luftfuktighet, momentanvärde 1 gång/tim
    4: "wind_speed_ms",   # Vindhastighet, medelvärde 10 min, 1 gång/tim
    3: "wind_dir_deg",    # Vindriktning, medelvärde 10 min, 1 gång/tim
    21: "gust_ms",        # Byvind, max 1 gång/tim
    7: "precip_mm",       # Nederbördsmängd, summa 1 timme
}


PERIODS = ("corrected-archive", "latest-months")

# Sundsvall municipality's own rain gauges in SMHI's "Övriga stationer" (whose data SMHI does not
# check) stamp their hours in Swedish local time, though SMHI's files say UTC: measured on
# 2026-10-30 against SMHI's radar, they come two hours late in August 2023 and 2026 and one in
# November 2023 and December 2020, while SMHI's Brämön A fits the radar as it is.
LOCAL_TIME_STATIONS = {"2222811", "2222812", "2222813", "2222814", "2222818", "2222819", "22228110"}
TIME_BASIS_LOCAL = "Svensk lokal tid (normaltid, sommartid), flyttad till UTC; SMHI:s fil anger UTC"


def last_sunday(year: int, month: int) -> date:
    day = date(year, month + 1, 1) - timedelta(days=1)
    return day - timedelta(days=(day.weekday() + 1) % 7)


def summer_time_utc(year: int) -> tuple[datetime, datetime]:
    """Swedish summer time, as the EU's: from 01 UTC on March's last Sunday to 01 UTC on October's."""
    start, end = last_sunday(year, 3), last_sunday(year, 10)
    return (datetime(start.year, start.month, start.day, 1, tzinfo=timezone.utc),
            datetime(end.year, end.month, end.day, 1, tzinfo=timezone.utc))


def local_rows_to_utc(rows: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    """`(date, time, value, quality)` rows stamped in Swedish local time, moved to UTC. October's
    repeated hour is summer time the first time and normal time the second; a time March skips is
    taken as normal time. Computed without time zone data, so it works where Python has none."""
    moved, seen = [], set()
    for day, clock, value, quality in rows:
        local = datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=timezone.utc)
        start, end = summer_time_utc(local.year)
        summer, winter = local - timedelta(hours=2), local - timedelta(hours=1)
        summer_fits = start <= summer < end
        winter_fits = not start <= winter < end
        utc = summer if summer_fits and not (winter_fits and (day, clock) in seen) else winter
        seen.add((day, clock))
        moved.append((utc.strftime("%Y-%m-%d"), utc.strftime("%H:%M"), value, quality))
    return moved


def archive_url(parameter: int, station: str, period: str = "corrected-archive") -> str:
    return f"{API}/parameter/{parameter}/station/{station}/period/{period}/data.csv"


def download(url: str) -> str:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response:
        return response.read().decode("utf-8-sig")


def parse_archive(text: str) -> dict[str, Any]:
    """Station metadata and `(date, time, value, quality)` rows of one SMHI archive CSV."""
    lines = text.lstrip("﻿").splitlines()
    station_name, station_id = lines[1].split(";")[:2]
    unit = lines[4].split(";")[2]
    header_index = next(index for index, line in enumerate(lines) if line.startswith("Datum;Tid (UTC)"))
    position = next(
        lines[index + 1].split(";") for index in range(header_index)
        if lines[index].startswith("Tidsperiod (fr.o.m);")
    )
    rows = []
    for line in lines[header_index + 1:]:
        fields = line.split(";")
        if len(fields) >= 4 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields[0]):
            rows.append((fields[0], fields[1][:5], fields[2], fields[3]))
    return {
        "station_name": station_name,
        "station_id": station_id,
        "unit": unit,
        "measurement_height_m": lines[1].split(";")[3] if len(lines[1].split(";")) > 3 else None,
        "altitude_m": float(position[2]),
        "latitude": float(position[3]),
        "longitude": float(position[4]),
        "rows": rows,
    }


def merge(archives: dict[int, dict[str, Any]], start: date, end: date) -> list[dict[str, str]]:
    """One row per UTC hour in the period with every parameter and its SMHI quality flag."""
    hours: dict[str, dict[str, str]] = {}
    for parameter, archive in archives.items():
        column = PARAMETERS[parameter]
        for day, clock, value, quality in archive["rows"]:
            if not start.isoformat() <= day <= end.isoformat():
                continue
            row = hours.setdefault(f"{day}T{clock}:00Z", {})
            row[column], row[f"{column}_quality"] = value, quality
    columns = [name for parameter in PARAMETERS for name in (PARAMETERS[parameter], f"{PARAMETERS[parameter]}_quality")]
    return [{"time_utc": moment, **{column: hours[moment].get(column, "") for column in columns}} for moment in sorted(hours)]


def station_record(archives: dict[int, dict[str, Any]], slug: str) -> dict[str, Any]:
    first = next(iter(archives.values()))
    return {
        "id": first["station_id"],
        "name": first["station_name"],
        "file": f"{slug}.csv",
        "latitude": first["latitude"],
        "longitude": first["longitude"],
        "altitude_m": first["altitude_m"],
        "parameters": {
            PARAMETERS[parameter]: {"smhi_parameter": parameter, "unit": archive["unit"], "measurement_height_m": archive["measurement_height_m"]}
            for parameter, archive in archives.items()
        },
    }


def write_station(output_dir: Path, slug: str, rows: list[dict[str, str]]) -> None:
    import csv

    with (output_dir / f"{slug}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def slug_for(name: str, station_id: str) -> str:
    ascii_name = name.lower().translate(str.maketrans("åäö", "aao"))
    return f"{re.sub(r'[^a-z0-9]+', '-', ascii_name).strip('-')}-{station_id}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("stations", nargs="+", help="SMHI station IDs, for example 96560")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--raw-dir", type=Path, help="reuse or keep downloaded archives here (raw-<station>-<parameter>.csv)")
    parser.add_argument("--period", choices=(*PERIODS, "both"), default="corrected-archive",
                        help="SMHI period: the quality-controlled archive, the last four months (not yet controlled) or both")
    parser.add_argument("--parameters", type=int, nargs="+", choices=sorted(PARAMETERS), default=list(PARAMETERS),
                        help="SMHI parameter keys, for example 7 for hourly precipitation")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for station in args.stations:
        archives = {}
        for parameter in args.parameters:
            parsed = None
            for period in PERIODS if args.period == "both" else (args.period,):
                suffix = f"-{period}" if args.period == "both" else ""
                raw_path = args.raw_dir / f"raw-{station}-{parameter}{suffix}.csv" if args.raw_dir else None
                if raw_path and raw_path.is_file():
                    text = raw_path.read_text(encoding="utf-8-sig")
                else:
                    text = download(archive_url(parameter, station, period))
                    if raw_path:
                        raw_path.parent.mkdir(parents=True, exist_ok=True)
                        raw_path.write_text(text, encoding="utf-8")
                current = parse_archive(text)
                if station in LOCAL_TIME_STATIONS:
                    current = {**current, "rows": local_rows_to_utc(current["rows"])}
                # The later period's rows come after, so merge() keeps its value for an hour both have.
                parsed = current if parsed is None else {**parsed, "rows": parsed["rows"] + current["rows"]}
            archives[parameter] = parsed
        rows = merge(archives, args.start, args.end)
        slug = slug_for(next(iter(archives.values()))["station_name"], station)
        write_station(args.out, slug, rows)
        record = {**station_record(archives, slug), "hours": len(rows)}
        if station in LOCAL_TIME_STATIONS:
            record["time_basis"] = TIME_BASIS_LOCAL
        records.append(record)
        print(f"{slug}: {len(rows)} hours")
    (args.out / "stations.json").write_text(json.dumps({
        "source": ATTRIBUTION,
        "api": API,
        "smhi_period": args.period,
        "period_utc": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "stations": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
