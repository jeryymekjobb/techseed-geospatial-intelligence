#!/usr/bin/env python3
"""Fetch Meteosat's fire pixels over the scenario's map area from LSA SAF's archive.

LSA SAF's MSG FRP-Pixel product (LSA-502; before 2016 the data record FRPPixel-R, LSA-550)
lists every fire pixel SEVIRI on Meteosat sees on the full disk, every 15 minutes, with its
position, fire radiative power (FRP), pixel area and view angle. This tool fetches the lists
of the scenario's playback period into a cache outside the repository (about 100 kB each, 96
a day), keeps the pixels inside the scenario's MAP_BBOX and writes
data/<scenario>/meteosat-frp/frp-pixels.geojson and SOURCE.json. A list already in the cache
is not fetched again; quarters missing on the server are counted. A scenario may also name a
comparison area (METEOSAT_FRP_COMPARE), a fire Meteosat saw near one it missed; its pixels are kept
too, marked "compare".

The archive needs a free LSA SAF account (https://mokey.lsasvcs.ipma.pt/auth/signup), read
from ~/.netrc ("machine datalsasaf.lsasvcs.ipma.pt login ... password ..."), never from the
repository. The lists are HDF5: install h5py first (tools/requirements-meteosat.txt).

    TECHSEED_SCENARIO=vastmanland2014 .venv/bin/python -m tools.fetch_meteosat_frp
"""

from __future__ import annotations

import argparse
import json
import netrc
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError
from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm, build_opener

from app.backend import scenario
from app.backend.meteosat import ATTRIBUTION as PRODUCT_ATTRIBUTION

HOST = "datalsasaf.lsasvcs.ipma.pt"
BASE_URL = f"https://{HOST}/PRODUCTS/MSG/FRP-PIXEL/HDF5"
FILE_NAME = "HDF5_LSASAF_MSG_FRP-PIXEL-ListProduct_MSG-Disk_{slot:%Y%m%d%H%M}"
SLOT = timedelta(minutes=15)
CACHE = Path.home() / ".cache" / "techseed-meteosat-frp"
LICENCE = "CC BY 4.0, LSA SAF data policy (https://lsa-saf.eumetsat.int)"
# The list's datasets kept for each pixel, with the names written to the GeoJSON.
FIELDS = {"FRP": "frp_mw", "FRP_UNCERTAINTY": "frp_uncertainty_mw", "FIRE_CONFIDENCE": "confidence",
          "PIXEL_SIZE": "pixel_area_km2", "PIXEL_VZA": "view_zenith_deg"}


def slots(start: datetime, end: datetime) -> list[datetime]:
    """Every quarter from `start` up to, not including, `end`."""
    found, slot = [], start
    while slot < end:
        found.append(slot)
        slot += SLOT
    return found


def url(slot: datetime) -> str:
    return f"{BASE_URL}/{slot:%Y/%m/%d}/{FILE_NAME.format(slot=slot)}"


def scaled(values: Iterable[float], factor: float, missing: float) -> list[float | None]:
    """A list's raw integers as values: divided by the dataset's SCALING_FACTOR, None where missing."""
    return [None if value == missing else float(value) / factor for value in values]


def pixels_in(columns: dict[str, list[float | None]], bbox: tuple[float, float, float, float], slot: datetime,
              satellite: str) -> list[dict[str, Any]]:
    """The pixels of one list (scaled columns, LATITUDE and LONGITUDE among them) inside bbox (west, south, east, north)."""
    west, south, east, north = bbox
    kept = []
    for index, (lat, lon) in enumerate(zip(columns["LATITUDE"], columns["LONGITUDE"])):
        if lat is None or lon is None or not (south <= lat <= north and west <= lon <= east):
            continue
        kept.append({"time_utc": slot.strftime("%Y-%m-%dT%H:%M:%SZ"), "satellite": satellite, "latitude": lat, "longitude": lon,
                     **{name: columns[field][index] for field, name in FIELDS.items() if field in columns}})
    return kept


def read_list(path: Path, bbox: tuple[float, float, float, float], slot: datetime) -> list[dict[str, Any]]:
    import h5py  # only this tool needs it (tools/requirements-meteosat.txt)

    with h5py.File(path) as stream:
        satellite = stream.attrs["SATELLITE"][0].decode()
        columns = {name: scaled(stream[name][:], float(stream[name].attrs["SCALING_FACTOR"]), stream[name].attrs["MISSING_VALUE"])
                   for name in ("LATITUDE", "LONGITUDE", *FIELDS) if name in stream}
    return pixels_in(columns, bbox, slot, satellite)


def opener():
    login = netrc.netrc().authenticators(HOST)
    if not login:
        raise SystemExit(f"fetch_meteosat_frp: no LSA SAF account for {HOST} in ~/.netrc")
    passwords = HTTPPasswordMgrWithDefaultRealm()
    passwords.add_password(None, f"https://{HOST}/", login[0], login[2])
    return build_opener(HTTPBasicAuthHandler(passwords))


def fetch(slot: datetime, cache: Path, open_url) -> Path | None:
    """The quarter's list in the cache, fetched if needed; None when the server has none."""
    target = cache / FILE_NAME.format(slot=slot)
    if target.is_file() and target.stat().st_size:
        return target
    for attempt in range(3):
        try:
            with open_url(url(slot), timeout=120) as response:
                target.write_bytes(response.read())
            return target
        except HTTPError as error:
            if error.code == 404:
                return None
            if error.code == 401:
                raise SystemExit("fetch_meteosat_frp: LSA SAF refused the account in ~/.netrc") from error
        except OSError:
            if attempt == 2:
                return None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--cache", type=Path, default=CACHE, help=f"where the lists are kept (default {CACHE})")
    parser.add_argument("--out", type=Path, default=scenario.METEOSAT_FRP_FILE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.exit(1, f"fetch_meteosat_frp: the scenario {scenario.NAME} has no METEOSAT_FRP_FILE\n")
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wanted = slots(scenario.PLAYBACK_START, scenario.PLAYBACK_END)
    open_url = opener().open
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda slot: fetch(slot, args.cache, open_url), wanted))
    # The map area's pixels, and those of the scenario's comparison area (METEOSAT_FRP_COMPARE: a fire
    # Meteosat saw near one it missed), each marked with its area.
    areas = {"incident": scenario.MAP_BBOX, **({"compare": scenario.METEOSAT_FRP_COMPARE["bbox"]} if scenario.METEOSAT_FRP_COMPARE else {})}
    found = [{**item, "area": area} for slot, path in zip(wanted, paths) if path
             for area, bbox in areas.items() for item in read_list(path, bbox, slot)]
    missing = [slot.strftime("%Y-%m-%dT%H:%MZ") for slot, path in zip(wanted, paths) if path is None]
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [item.pop("longitude"), item.pop("latitude")]},
                 "properties": item} for item in found]
    args.out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out.parent / "SOURCE.json").write_text(json.dumps({
        "source": "LSA SAF MSG FRP-Pixel (LSA-502; FRPPixel-R, LSA-550), EUMETSAT",
        "url": BASE_URL,
        "licence": LICENCE,
        "attribution": PRODUCT_ATTRIBUTION,
        "map_bbox_west_south_east_north": list(scenario.MAP_BBOX),
        "compare": scenario.METEOSAT_FRP_COMPARE,
        "period_utc": [wanted[0].strftime("%Y-%m-%dT%H:%MZ"), (wanted[-1] + SLOT).strftime("%Y-%m-%dT%H:%MZ")],
        "quarters": len(wanted),
        "quarters_missing_on_server": missing,
        "pixels": len(features),
        "processed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    inside = sum(feature["properties"]["area"] == "incident" for feature in features)
    print(f"{inside} pixlar i kartområdet, {len(features) - inside} i jämförelseområdet, "
          f"{len(wanted) - len(missing)} av {len(wanted)} kvartar hämtade; {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
