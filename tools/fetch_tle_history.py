#!/usr/bin/env python3
"""Fetch the orbital elements of the scenario's satellites from Space-Track into its TLE directory.

The globe shows where Aqua and Terra (MODIS), Suomi NPP (VIIRS), Landsat 8 and the
ISS were at the scenario clock, so it needs their historical two-line elements
(class gp_history) for the fire period. Space-Track needs an account: the login
is read from ~/.spacetrackrc (`identity=` and `password=` lines, as on the
Space-Track login form) or from --credentials, and is never printed or stored.
One query fetches all satellites, well inside Space-Track's rate limits.

The scenario's TLE file (for Västmanland `data/tle/tle-2014.json`) holds the
elements per satellite and `SOURCE.json` next to it the query, the time of fetching and the terms; data/ is not
versioned, so the elements are not redistributed through the repository. Only
the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from app.backend import scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
TLE_DIR = scenario.TLE_DIR
BASE_URL = "https://www.space-track.org"
TERMS_URL = "https://www.space-track.org/documentation#/user_agree"
DEFAULT_CREDENTIALS = Path.home() / ".spacetrackrc"
# NORAD catalogue numbers and the epoch days, from the scenario.
SATELLITES = scenario.TLE_SATELLITES
DEFAULT_START, DEFAULT_END = scenario.TLE_START, scenario.TLE_END
USER_AGENT = "techseed-geospatial-intelligence/0.1"


class FetchError(RuntimeError):
    """A failure whose message never contains the login."""


def read_credentials(path: Path) -> dict[str, str]:
    """`identity` and `password` from key=value lines; comments and blank lines are skipped."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FetchError(f"cannot read the credentials file {path}: {exc.strerror}") from None
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    missing = [key for key in ("identity", "password") if not values.get(key)]
    if missing:
        raise FetchError(f"{path} lacks {' and '.join(missing)}")
    return {"identity": values["identity"], "password": values["password"]}


def query_path(start: str, end: str) -> str:
    ids = ",".join(SATELLITES)
    return (f"/basicspacedata/query/class/gp_history/NORAD_CAT_ID/{ids}/EPOCH/{start}--{end}"
            "/orderby/NORAD_CAT_ID,EPOCH/format/json")


def fetch(credentials: dict[str, str], start: str, end: str, base_url: str = BASE_URL) -> list[dict[str, Any]]:
    """Log in, run the one query and log out; the session cookie stays in this function."""
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", USER_AGENT)]

    def call(path: str, data: bytes | None = None) -> bytes:
        try:
            with opener.open(Request(base_url + path, data=data), timeout=120) as response:
                return response.read()
        except HTTPError as exc:
            raise FetchError(f"Space-Track answered HTTP {exc.code} for {path.split('?')[0]}") from None
        except URLError as exc:
            raise FetchError(f"Space-Track could not be reached: {exc.reason}") from None

    reply = call("/ajaxauth/login", urlencode(credentials).encode())
    if b"Failed" in reply:
        raise FetchError("Space-Track refused the login (check ~/.spacetrackrc)")
    try:
        body = call(query_path(start, end))
    finally:
        try:
            call("/ajaxauth/logout")
        except FetchError:
            pass
    try:
        records = json.loads(body)
    except json.JSONDecodeError:
        raise FetchError("Space-Track did not answer with JSON") from None
    if not isinstance(records, list):
        raise FetchError("Space-Track did not answer with a list of element sets")
    return records


def by_satellite(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The element sets per satellite in epoch order, keeping only what the globe needs."""
    result: dict[str, dict[str, Any]] = {norad: {"name": name, "elements": []} for norad, name in SATELLITES.items()}
    for record in records:
        norad = str(record.get("NORAD_CAT_ID", ""))
        lines = (record.get("TLE_LINE1"), record.get("TLE_LINE2"))
        if norad not in result or not all(isinstance(line, str) and len(line) == 69 for line in lines):
            continue
        result[norad]["elements"].append({"epoch_utc": str(record["EPOCH"]).replace(" ", "T") + "Z", "line1": lines[0], "line2": lines[1]})
    for entry in result.values():
        entry["elements"].sort(key=lambda item: item["epoch_utc"])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS, help="file with identity= and password=")
    parser.add_argument("--start", default=DEFAULT_START, help="first epoch day (UTC)")
    parser.add_argument("--end", default=DEFAULT_END, help="last epoch day (UTC)")
    parser.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, default=TLE_DIR, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        satellites = by_satellite(fetch(read_credentials(args.credentials), args.start, args.end, args.base_url))
    except FetchError as exc:
        parser.exit(1, f"fetch_tle_history: {exc}\n")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / scenario.TLE_FILE_NAME).write_text(json.dumps({"satellites": satellites}, indent=1) + "\n", encoding="utf-8")
    counts = {entry["name"]: len(entry["elements"]) for entry in satellites.values()}
    (args.out / "SOURCE.json").write_text(json.dumps({
        "source": "Space-Track.org, class gp_history",
        "query": args.base_url + query_path(args.start, args.end),
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "terms": TERMS_URL,
        "note": "Fetched with a personal Space-Track account; not versioned or redistributed.",
        "element_sets": counts,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, count in counts.items():
        print(f"{name}: {count} element sets")
    missing = [name for name, count in counts.items() if not count]
    if missing:
        print(f"warning: no element sets for {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
