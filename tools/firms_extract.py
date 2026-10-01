#!/usr/bin/env python3
"""Extract FIRMS archive fire detections for one area and period.

Reads FIRMS archive CSV files (MODIS Collection 6.1 and VIIRS), keeps detections
inside a latitude/longitude box and date range, removes non-vegetation sources
and low-confidence detections, and writes:

- `hotspots.csv`: the kept detections with a UTC timestamp;
- `hotspots.geojson`: the same detections as WGS 84 points;
- `daily_summary.csv`: detections and fire radiative power per UTC day and instrument;
- `metadata.json`: inputs with SHA-256, filters, counts and source attribution.

FIRMS dates and times (`acq_date`, `acq_time` as HHMM) are UTC. Only the Python
standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ATTRIBUTION = (
    "NASA FIRMS (Fire Information for Resource Management System), archive download; "
    "https://firms.modaps.eosdis.nasa.gov/"
)
REQUIRED_COLUMNS = ("latitude", "longitude", "acq_date", "acq_time", "confidence", "frp", "type")
VIIRS_CONFIDENCE = {"l", "n", "h"}
# FIRMS `type`: 0 presumed vegetation fire, 1 active volcano, 2 other static land source, 3 offshore.
DEFAULT_TYPES = ("0",)
DEFAULT_MODIS_MIN_CONFIDENCE = 30
DEFAULT_VIIRS_CONFIDENCE = ("n", "h")
OUTPUT_COLUMNS = (
    "instrument", "satellite", "acq_datetime_utc", "acq_date", "acq_time", "latitude", "longitude",
    "confidence", "frp", "brightness", "daynight", "type", "source_file",
)


def instrument_of(row: dict[str, str]) -> str:
    """MODIS or VIIRS; VIIRS archives may name the satellite (`SNPP`) as instrument."""
    if row.get("instrument", "").upper() == "MODIS":
        return "MODIS"
    if row.get("confidence", "").lower() in VIIRS_CONFIDENCE or "VIIRS" in row.get("instrument", "").upper():
        return "VIIRS"
    raise ValueError(f"unknown FIRMS instrument: {row.get('instrument')!r}")


def acquisition_time(row: dict[str, str]) -> datetime:
    clock = row["acq_time"].strip().zfill(4)
    return datetime.strptime(f"{row['acq_date']} {clock}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)


def exclusion_reason(
    row: dict[str, str],
    *,
    start: date,
    end: date,
    bbox: tuple[float, float, float, float],
    types: set[str],
    modis_min_confidence: int,
    viirs_confidence: set[str],
) -> str | None:
    """Return why a detection is excluded, or None to keep it."""
    min_lat, max_lat, min_lon, max_lon = bbox
    if not start <= date.fromisoformat(row["acq_date"]) <= end:
        return "outside_period"
    if not (min_lat <= float(row["latitude"]) <= max_lat and min_lon <= float(row["longitude"]) <= max_lon):
        return "outside_area"
    if row["type"].strip() not in types:
        return "not_vegetation_fire_type"
    if instrument_of(row) == "MODIS":
        if int(row["confidence"]) < modis_min_confidence:
            return "low_confidence"
    elif row["confidence"].lower() not in viirs_confidence:
        return "low_confidence"
    return None


def read_detections(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing FIRMS columns {missing}")
        return [{**row, "source_file": path.name} for row in reader]


def normalized(row: dict[str, str]) -> dict[str, Any]:
    return {
        "instrument": instrument_of(row),
        "satellite": row.get("satellite", ""),
        "acq_datetime_utc": acquisition_time(row).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "acq_date": row["acq_date"],
        "acq_time": row["acq_time"].strip().zfill(4),
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "confidence": row["confidence"],
        "frp": float(row["frp"]),
        "brightness": float(row["brightness"]) if row.get("brightness") else None,
        "daynight": row.get("daynight", ""),
        "type": row["type"].strip(),
        "source_file": row["source_file"],
    }


def daily_summary(detections: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    days: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in detections:
        days.setdefault((item["acq_date"], item["instrument"]), []).append(item)
    return [
        {
            "acq_date": day,
            "instrument": instrument,
            "detections": len(items),
            "frp_sum_mw": round(sum(item["frp"] for item in items), 1),
            "frp_max_mw": round(max(item["frp"] for item in items), 1),
            "first_utc": min(item["acq_datetime_utc"] for item in items),
            "last_utc": max(item["acq_datetime_utc"] for item in items),
        }
        for (day, instrument), items in sorted(days.items())
    ]


def geojson(detections: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["longitude"], item["latitude"]]},
                "properties": {key: value for key, value in item.items() if key not in {"latitude", "longitude"}},
            }
            for item in detections
        ],
    }


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(
    inputs: list[Path],
    output_dir: Path,
    *,
    start: date,
    end: date,
    bbox: tuple[float, float, float, float],
    types: Iterable[str] = DEFAULT_TYPES,
    modis_min_confidence: int = DEFAULT_MODIS_MIN_CONFIDENCE,
    viirs_confidence: Iterable[str] = DEFAULT_VIIRS_CONFIDENCE,
) -> dict[str, Any]:
    """Write the extract files and return the metadata."""
    filters = {
        "types": set(types),
        "modis_min_confidence": modis_min_confidence,
        "viirs_confidence": {value.lower() for value in viirs_confidence},
    }
    kept: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    input_rows = 0
    for path in inputs:
        for row in read_detections(path):
            input_rows += 1
            reason = exclusion_reason(row, start=start, end=end, bbox=bbox, **filters)
            if reason:
                excluded[reason] = excluded.get(reason, 0) + 1
            else:
                kept.append(normalized(row))
    kept.sort(key=lambda item: (item["acq_datetime_utc"], item["instrument"], item["latitude"], item["longitude"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "hotspots.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
    (output_dir / "hotspots.geojson").write_text(json.dumps(geojson(kept), indent=1) + "\n", encoding="utf-8")
    summary = daily_summary(kept)
    with (output_dir / "daily_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["acq_date", "instrument", "detections", "frp_sum_mw", "frp_max_mw", "first_utc", "last_utc"]
        )
        writer.writeheader()
        writer.writerows(summary)
    metadata = {
        "source": ATTRIBUTION,
        "inputs": [{"file": path.name, "sha256": sha256_of(path)} for path in inputs],
        "period_utc": {"start": start.isoformat(), "end": end.isoformat()},
        "bbox_wgs84": dict(zip(("min_lat", "max_lat", "min_lon", "max_lon"), bbox)),
        "filters": {
            "types": sorted(filters["types"]),
            "modis_min_confidence": modis_min_confidence,
            "viirs_confidence": sorted(filters["viirs_confidence"]),
        },
        "counts": {"input": input_rows, "kept": len(kept), "excluded": dict(sorted(excluded.items()))},
        "notes": [
            "Dates and times are UTC as delivered by FIRMS.",
            "A detection is a satellite pixel with a thermal anomaly, not a mapped fire perimeter.",
        ],
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    values = tuple(float(part) for part in text.split(","))
    if len(values) != 4 or values[0] > values[1] or values[2] > values[3]:
        raise argparse.ArgumentTypeError("bbox is min_lat,max_lat,min_lon,max_lon")
    return values  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("inputs", nargs="+", type=Path, help="FIRMS archive CSV files")
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    parser.add_argument("--start", required=True, type=date.fromisoformat, help="first UTC date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, type=date.fromisoformat, help="last UTC date, YYYY-MM-DD")
    parser.add_argument("--bbox", required=True, type=parse_bbox, help="min_lat,max_lat,min_lon,max_lon")
    parser.add_argument("--types", default=",".join(DEFAULT_TYPES), help="FIRMS type values to keep")
    parser.add_argument("--modis-min-confidence", type=int, default=DEFAULT_MODIS_MIN_CONFIDENCE)
    parser.add_argument("--viirs-confidence", default=",".join(DEFAULT_VIIRS_CONFIDENCE), help="VIIRS classes to keep")
    args = parser.parse_args(argv)
    metadata = extract(
        args.inputs,
        args.out,
        start=args.start,
        end=args.end,
        bbox=args.bbox,
        types=args.types.split(","),
        modis_min_confidence=args.modis_min_confidence,
        viirs_confidence=args.viirs_confidence.split(","),
    )
    print(json.dumps(metadata["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
