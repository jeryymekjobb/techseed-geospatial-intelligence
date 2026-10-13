#!/usr/bin/env python3
"""Fetch SMHI's observed lightning for the scenario's period, over the weather chart's area.

SMHI's open lightning archive (opendata-download-lightning.smhi.se) gives every located flash of
a day with its time, position, peak current and whether it was a cloud flash. For each day of
the scenario's period this tool keeps the flashes over AREA (the weather chart's Scandinavia,
fetch_met_forecasts.ISOBAR_AREA) with only those fields, and writes
data/<scenario>/lightning/<date>.json and SOURCE.json with the licence (CC BY 4.0, credit SMHI).
These are observations, not forecasts.

    TECHSEED_SCENARIO=ljusdal2018 .venv/bin/python -m tools.fetch_smhi_lightning

A day already fetched is kept; --force fetches it again.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.backend import scenario
from tools.fetch_met_forecasts import ISOBAR_AREA

DAY_URL = "https://opendata-download-lightning.smhi.se/api/version/latest/year/{day:%Y}/month/{day:%m}/day/{day:%d}/data.json"
AREA = ISOBAR_AREA  # west, south, east, north
LICENCE = "CC BY 4.0, https://www.smhi.se/data/oppna-data/villkor-for-anvandning"
ATTRIBUTION = "Blixtdata: SMHI öppna data (CC BY 4.0)"
OUT_DIR = scenario.LIGHTNING_DIR


def strikes(values: list[dict[str, Any]], area: tuple[float, float, float, float] = AREA) -> list[list[float]]:
    """The day's flashes over `area` as [epoch seconds, latitude, longitude, peak current kA, cloud flash 0/1]."""
    west, south, east, north = area
    kept = []
    for item in values:
        if not (south <= item["lat"] <= north and west <= item["lon"] <= east):
            continue
        moment = datetime(item["year"], item["month"], item["day"], item["hours"], item["minutes"], item["seconds"], tzinfo=timezone.utc)
        kept.append([int(moment.timestamp()), round(item["lat"], 4), round(item["lon"], 4), round(item["peakCurrent"]), int(item["cloudIndicator"])])
    return sorted(kept)


def fetch_day(day: date, attempts: int = 3) -> list[dict[str, Any]]:
    """The archive's flashes of a day; a passing failure is tried again."""
    for attempt in range(attempts):
        try:
            request = Request(DAY_URL.format(day=day), headers={"User-Agent": "techseed-geospatial-demo"})
            with urlopen(request, timeout=180) as response:
                return json.loads(response.read())["values"]
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(10 * (attempt + 1))
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--force", action="store_true", help="fetch days already fetched again")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_smhi_lightning: the scenario {scenario.NAME} has no LIGHTNING_DIR\n")
    args.out.mkdir(parents=True, exist_ok=True)
    days, counts = [], {}
    day = scenario.PERIOD_START
    while day <= scenario.PERIOD_END:
        target = args.out / f"{day.isoformat()}.json"
        if not target.is_file() or args.force:
            kept = strikes(fetch_day(day))
            target.write_text(json.dumps({"date": day.isoformat(), "strikes": kept}, separators=(",", ":")) + "\n", encoding="utf-8")
        counts[day.isoformat()] = len(json.loads(target.read_text(encoding="utf-8"))["strikes"])
        print(f"{day}: {counts[day.isoformat()]} blixtar", flush=True)
        days.append(day.isoformat())
        day += timedelta(days=1)
    (args.out / "SOURCE.json").write_text(json.dumps({
        "source": DAY_URL.split("/year/")[0],
        "days": days,
        "flashes_per_day": counts,
        "area_west_south_east_north": list(AREA),
        "fields": ["epoch seconds (UTC)", "latitude", "longitude", "peak current (kA)", "cloud flash (1) or to the ground (0)"],
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "note": "Observed lightning located by SMHI's network, not a forecast.",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(days)} dagar i {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
