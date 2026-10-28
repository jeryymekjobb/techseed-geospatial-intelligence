#!/usr/bin/env python3
"""Read SMHI's modelled daily flows (S-HYPE) for the scenario's sub-catchments from Vattenwebb's files.

SMHI has no measuring station in some rivers, such as the Selånger river and Sidsjöbäcken in
Sundsvall. Its hydrological model S-HYPE gives a flow for every sub-catchment (SUBID), which
Vattenwebb offers as open data in an Excel file per area ("Modelldata per område",
https://vattenwebb.smhi.se/modelarea/, the area's "Ladda ner" link). SMHI's terms for its open data
allow only its documented APIs, and Vattenwebb's download is not one, so the files are downloaded by
hand, one per SUBID, and saved as <MODEL_FLOW_DIR>/raw/<subid>.xls. This tool only reads them.

For each of the scenario's MODEL_FLOW_STATIONS it keeps the period's daily total flow ("Total
vattenföring", the sheets Dygnsvärden and Dygnsuppdaterade värden, at 00 UTC), the highest before
the period in the file's series (from 2010), the outlet point (SWEREF 99 TM, turned to WGS 84), SMHI's
flow statistics for 1991-2020 (MQ, MHQ, HQ2-HQ50) and the model version, and writes one CSV per
area and stations.json.

    TECHSEED_SCENARIO=ljungan-aug2023 .venv/bin/python -m tools.read_vattenwebb

SMHI's open data are licensed under Creative Commons Attribution 4.0 SE: name SMHI as the source
and state changes (here: period, the highest before it). SMHI asks for the model version and the
download date to be stated with Vattenwebb's data. Needs xlrd (tools/requirements-data.txt).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.backend import scenario

ATTRIBUTION = "SMHI Vattenwebb, modellerad vattenföring (S-HYPE), öppna data (CC BY 4.0 SE); urval av period"
DOWNLOAD_PAGE = "https://vattenwebb.smhi.se/modelarea/"
STATISTICS = ("MQ", "MHQ", "HQ2", "HQ5", "HQ10", "HQ25", "HQ50")
EXCEL_EPOCH = date(1899, 12, 30)


def sweref99tm_to_wgs84(northing: float, easting: float) -> tuple[float, float]:
    """Latitude and longitude (degrees) of a SWEREF 99 TM point: Lantmäteriet's formulas for the
    inverse Gauss-Krüger projection on GRS 80, central meridian 15 E, scale 0.9996, false easting 500 km."""
    axis, flattening = 6378137.0, 1 / 298.257222101
    central, scale, false_easting = math.radians(15.0), 0.9996, 500000.0
    e2 = flattening * (2 - flattening)
    n = flattening / (2 - flattening)
    a_roof = axis / (1 + n) * (1 + n * n / 4 + n ** 4 / 64)
    d1 = n / 2 - 2 * n ** 2 / 3 + 37 * n ** 3 / 96 - n ** 4 / 360
    d2 = n ** 2 / 48 + n ** 3 / 15 - 437 * n ** 4 / 1440
    d3 = 17 * n ** 3 / 480 - 37 * n ** 4 / 840
    d4 = 4397 * n ** 4 / 161280
    xi = northing / (scale * a_roof)
    eta = (easting - false_easting) / (scale * a_roof)
    xi_prim = (xi - d1 * math.sin(2 * xi) * math.cosh(2 * eta) - d2 * math.sin(4 * xi) * math.cosh(4 * eta)
               - d3 * math.sin(6 * xi) * math.cosh(6 * eta) - d4 * math.sin(8 * xi) * math.cosh(8 * eta))
    eta_prim = (eta - d1 * math.cos(2 * xi) * math.sinh(2 * eta) - d2 * math.cos(4 * xi) * math.sinh(4 * eta)
                - d3 * math.cos(6 * xi) * math.sinh(6 * eta) - d4 * math.cos(8 * xi) * math.sinh(8 * eta))
    phi_star = math.asin(math.sin(xi_prim) / math.cosh(eta_prim))
    delta_lambda = math.atan(math.sinh(eta_prim) / math.cos(xi_prim))
    a = e2 + e2 ** 2 + e2 ** 3 + e2 ** 4
    b = -(7 * e2 ** 2 + 17 * e2 ** 3 + 30 * e2 ** 4) / 6
    c = (224 * e2 ** 3 + 889 * e2 ** 4) / 120
    d = -(4279 * e2 ** 4) / 1260
    s2 = math.sin(phi_star) ** 2
    phi = phi_star + math.sin(phi_star) * math.cos(phi_star) * (a + b * s2 + c * s2 ** 2 + d * s2 ** 3)
    return math.degrees(phi), math.degrees(central + delta_lambda)


def excel_day(value: float) -> date:
    return EXCEL_EPOCH + timedelta(days=int(value))


def daily_flows(sheets: dict[str, list[list[Any]]]) -> list[tuple[date, float]]:
    """The total flow by the day from the two sheets of days, the daily-updated values after the archive."""
    days: dict[date, float] = {}
    for name in ("Dygnsvärden", "Dygnsuppdaterade värden"):
        for row in sheets.get(name, []):
            if len(row) > 1 and isinstance(row[0], float) and isinstance(row[1], float):
                days[excel_day(row[0])] = row[1]
    return sorted(days.items())


def area_information(sheets: dict[str, list[list[Any]]]) -> dict[str, Any]:
    """The area's name, outlet (SWEREF 99 TM northing, easting), flow statistics and model version."""
    found: dict[str, Any] = {"statistics": {}}
    for row in sheets.get("Områdesinformation", []):
        if len(row) < 2:
            continue
        label, value = row[0], row[1]
        if label == "Namn" and "name" not in found:
            found["name"] = value
        elif label == "Utloppspunkt (SWEREF99)":
            northing, easting = (float(part) for part in str(value).split(","))
            found["outlet"] = (northing, easting)
        elif label in STATISTICS and isinstance(value, float):
            found["statistics"][label] = value
    for row in sheets.get("Information", []):
        if len(row) > 1 and row[0] in ("Vattenwebb version", "Hype modellversion", "Hype simuleringsperiod"):
            found.setdefault("model", {})[row[0]] = row[1]
    return found


def read_workbook(path: Path) -> dict[str, list[list[Any]]]:
    import xlrd  # tools/requirements-data.txt

    book = xlrd.open_workbook(str(path))
    return {sheet.name: [sheet.row_values(row) for row in range(sheet.nrows)] for sheet in book.sheets()}


def station(subid: str, name: str, sheets: dict[str, list[list[Any]]], start: date, end: date) -> tuple[dict[str, Any], list[tuple[date, float]]]:
    """The station's catalogue entry and the period's days."""
    days = daily_flows(sheets)
    info = area_information(sheets)
    if not days or "outlet" not in info:
        raise ValueError(f"no daily flows or outlet for SUBID {subid}")
    before = [item for item in days if item[0] < start]
    record = max(before, key=lambda item: item[1]) if before else None
    latitude, longitude = sweref99tm_to_wgs84(*info["outlet"])
    inside = [item for item in days if start <= item[0] <= end]
    return {
        "subid": subid, "name": name, "area_name": info.get("name"), "kind": "flow", "unit": "m³/s", "file": f"model-flow-{subid}.csv",
        "latitude": round(latitude, 5), "longitude": round(longitude, 5), "modelled_since": days[0][0].isoformat(),
        "earlier_max": None if record is None else {"value": round(record[1], 3), "time_utc": f"{record[0].isoformat()}T00:00:00Z"},
        "statistics": {key: round(value, 3) for key, value in info["statistics"].items()},
        "statistics_period": "1991–2020", "model": info.get("model", {}), "values": len(inside),
    }, inside


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--start", type=date.fromisoformat, default=scenario.PERIOD_START)
    parser.add_argument("--end", type=date.fromisoformat, default=scenario.PERIOD_END)
    parser.add_argument("--dir", type=Path, default=scenario.MODEL_FLOW_DIR)
    args = parser.parse_args(argv)
    if not scenario.MODEL_FLOW_STATIONS or args.dir is None:
        parser.exit(1, f"read_vattenwebb: the scenario {scenario.NAME} has no modelled flows\n")
    missing = [subid for subid in scenario.MODEL_FLOW_STATIONS if not (args.dir / "raw" / f"{subid}.xls").is_file()]
    if missing:
        parser.exit(1, "read_vattenwebb: download by hand from " + DOWNLOAD_PAGE + " (search the SUBID, the area's "
                    "'Ladda ner' link) and save as " + ", ".join(str(args.dir / "raw" / f"{subid}.xls") for subid in missing) + "\n")
    stations = []
    for subid, name in scenario.MODEL_FLOW_STATIONS.items():
        raw = args.dir / "raw" / f"{subid}.xls"
        entry, days = station(subid, name, read_workbook(raw), args.start, args.end)
        entry["downloaded_utc"] = datetime.fromtimestamp(raw.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with (args.dir / entry["file"]).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["time_utc", "value"])
            writer.writerows((f"{day.isoformat()}T00:00:00Z", round(value, 3)) for day, value in days)
        stations.append(entry)
        print(f"{name}: {len(days)} days, earlier highest {entry['earlier_max']}, MHQ {entry['statistics'].get('MHQ')}", flush=True)
    (args.dir / "stations.json").write_text(json.dumps({
        "source": ATTRIBUTION, "download_page": DOWNLOAD_PAGE, "period": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "read_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stations": stations,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
