#!/usr/bin/env python3
"""Fetch hourly SMHI weather observations for stations and a period.

Downloads the quality-controlled archive (`corrected-archive`) of SMHI's
meteorological observations API for each station and parameter, keeps the
period, and writes one merged hourly CSV per station plus `stations.json`.

SMHI open data is licensed under Creative Commons Attribution 4.0 SE: name SMHI
as the source and state changes (here: period selection and merging of
parameters). Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
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


def archive_url(parameter: int, station: str) -> str:
    return f"{API}/parameter/{parameter}/station/{station}/period/corrected-archive/data.csv"


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
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for station in args.stations:
        archives = {}
        for parameter in PARAMETERS:
            raw_path = args.raw_dir / f"raw-{station}-{parameter}.csv" if args.raw_dir else None
            if raw_path and raw_path.is_file():
                text = raw_path.read_text(encoding="utf-8-sig")
            else:
                text = download(archive_url(parameter, station))
                if raw_path:
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_path.write_text(text, encoding="utf-8")
            archives[parameter] = parse_archive(text)
        rows = merge(archives, args.start, args.end)
        slug = slug_for(archives[1]["station_name"], station)
        write_station(args.out, slug, rows)
        records.append({**station_record(archives, slug), "hours": len(rows)})
        print(f"{slug}: {len(rows)} hours")
    (args.out / "stations.json").write_text(json.dumps({
        "source": ATTRIBUTION,
        "api": API,
        "period_utc": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "stations": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
