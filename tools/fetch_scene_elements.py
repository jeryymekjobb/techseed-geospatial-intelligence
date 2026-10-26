#!/usr/bin/env python3
"""Fetch, for each of the scenario's satellite images, the element set its satellite had then.

A scenario of many years (Falsterbo 2012–2026) shows no orbits, but each image's satellite where
it was when it took the image (app/backend/scene_satellites.py). For each Landsat and Sentinel-2
scene in the scenario's image SOURCE.json files this tool asks Space-Track's gp_history for the
satellite's element sets from three days before to three days after the image and keeps the one
whose epoch is nearest it. The login is read from ~/.spacetrackrc as by fetch_tle_history; it never
appears in the output. It writes SCENE_ELEMENTS_FILE with the query, the time of fetching and the
terms. data/ is not versioned.

    TECHSEED_SCENARIO=falsterbo .venv/bin/python -m tools.fetch_scene_elements

The element sets are USSPACECOM's basic SSA data, which may be redistributed with an appropriate
citation (reports/2026-10-21-space-track-villkor-claude-opus-5-5.md). Only the Python standard
library is used.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from app.backend import scenario
from tools.fetch_tle_history import BASE_URL, DEFAULT_CREDENTIALS, TERMS_URL, USER_AGENT, FetchError, read_credentials

# The images' satellites by the names landsat.py gives them, with their NORAD numbers.
NORAD = {"Landsat 8": "39084", "Landsat 9": "49260", "Sentinel-2A": "40697", "Sentinel-2B": "42063"}
PREFIXES = {"LC08": "Landsat 8", "LC09": "Landsat 9", "S2A": "Sentinel-2A", "S2B": "Sentinel-2B"}
WINDOW = timedelta(days=3)


def scenes(directories: list[Path | None]) -> list[dict[str, str]]:
    """The scenes of the image SOURCE.json files: scene id, satellite and time taken."""
    found = []
    for directory in directories:
        source = directory / "SOURCE.json" if directory else None
        if source is None or not source.is_file():
            continue
        for record in json.loads(source.read_text(encoding="utf-8"))["scenes"]:
            satellite = PREFIXES.get(record["scene"].split("_")[0])
            if satellite:
                found.append({"scene": record["scene"], "satellite": satellite, "acquired_utc": record["acquired_utc"]})
    return sorted(found, key=lambda item: item["acquired_utc"])


def query_path(norad: str, moment: datetime) -> str:
    start, end = ((moment + shift).strftime("%Y-%m-%d") for shift in (-WINDOW, WINDOW))
    return f"/basicspacedata/query/class/gp_history/NORAD_CAT_ID/{norad}/EPOCH/{start}--{end}/orderby/EPOCH/format/json"


def nearest(records: list[dict[str, Any]], moment: datetime) -> dict[str, str] | None:
    """The element set whose epoch is nearest the moment, with valid lines."""
    best = None
    for record in records:
        lines = (record.get("TLE_LINE1"), record.get("TLE_LINE2"))
        if not all(isinstance(line, str) and len(line) == 69 for line in lines):
            continue
        epoch = datetime.fromisoformat(str(record["EPOCH"]).replace(" ", "T")).replace(tzinfo=timezone.utc)
        if best is None or abs(epoch - moment) < abs(best[0] - moment):
            best = (epoch, lines)
    if best is None:
        return None
    return {"epoch_utc": best[0].strftime("%Y-%m-%dT%H:%M:%SZ"), "line1": best[1][0], "line2": best[1][1]}


def session(credentials: dict[str, str], base_url: str = BASE_URL) -> tuple[Callable[[str], Any], Callable[[], None]]:
    """A logged-in Space-Track session: a query function and a logout; the cookie stays inside."""
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

    if b"Failed" in call("/ajaxauth/login", urlencode(credentials).encode()):
        raise FetchError("Space-Track refused the login (check ~/.spacetrackrc)")

    def query(path: str) -> Any:
        try:
            return json.loads(call(path))
        except json.JSONDecodeError:
            raise FetchError("Space-Track did not answer with JSON") from None

    def logout() -> None:
        try:
            call("/ajaxauth/logout")
        except FetchError:
            pass

    return query, logout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS, help="file with identity= and password=")
    parser.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, default=scenario.SCENE_ELEMENTS_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    found = scenes([scenario.LANDSAT_DIR, scenario.SENTINEL2_DIR])
    if args.out is None or not found:
        parser.exit(1, f"fetch_scene_elements: the scenario {scenario.NAME} has no scene element file or no fetched images\n")
    result: dict[str, dict[str, str]] = {}
    try:
        query, logout = session(read_credentials(args.credentials), args.base_url)
        try:
            for item in found:
                moment = datetime.fromisoformat(item["acquired_utc"].replace("Z", "+00:00"))
                norad = NORAD[item["satellite"]]
                records = query(query_path(norad, moment))
                element = nearest(records if isinstance(records, list) else [], moment)
                if element is None:
                    print(f"warning: no element set for {item['satellite']} near {item['acquired_utc']}")
                    continue
                result[item["scene"]] = {"satellite": item["satellite"], "norad": norad, "acquired_utc": item["acquired_utc"], **element}
                print(f"{item['scene']}: {item['satellite']}, epoch {element['epoch_utc']}")
        finally:
            logout()
    except FetchError as exc:
        parser.exit(1, f"fetch_scene_elements: {exc}\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "source": "Space-Track.org, class gp_history: the element set nearest each image",
        "query": f"{args.base_url}/basicspacedata/query/class/gp_history/NORAD_CAT_ID/<norad>/EPOCH/<image - 3 d>--<image + 3 d>"
                 "/orderby/EPOCH/format/json",
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "terms": TERMS_URL,
        "attribution": "Banelement: USSPACECOM via Space-Track.org",
        "note": "Fetched with a personal Space-Track account; data/ is not versioned.",
        "scenes": result,
    }, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
