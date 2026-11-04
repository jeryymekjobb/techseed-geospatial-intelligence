"""The latest Sentinel-2 image over the area, and in the same way the latest Landsat 8 or 9 image
(LANDSAT, as the Flen scenarios' Landsat images), as the scenarios show their satellite images
(tools/fetch_sentinel2_scene.py), but live and without GDAL: Microsoft Planetary Computer's open
STAC catalogue gives the scenes, and its data API cuts the area out of each scene in true colour
(bands B04, B03 and B02) as a PNG in WGS 84, which are laid together when the area spans two tiles.

Each poll asks again at most once every SEARCH_EVERY. The newest datatake of the last RECENT days
with at most CLOUD_PERCENT cloud is chosen; without one, the least cloudy of the last FALLBACK days,
and the screens say how cloudy it is. Copernicus Sentinel data are free and open; the image says so.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

STAC_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
DATA_API = "https://planetarycomputer.microsoft.com/api/data/v1/item/bbox"
COLLECTION = "sentinel-2-l2a"
RECENT = timedelta(days=14)
FALLBACK = timedelta(days=30)
CLOUD_PERCENT = 60.0
SEARCH_EVERY = timedelta(hours=1)
# The image's size: 1500 px a degree east-west (about 40 m at 59 N), 3000 north-south (about 40 m).
PIXELS_PER_DEGREE = (1500, 3000)
# True colour from the bands, as the scenarios' natural colour: Level-2A reflectance x 10000 with its
# offset of 1000, stretched from 1000 to 3600, a little brighter in the middle (gamma 1.4).
BANDS = ("B04", "B03", "B02")
RESCALE = "1000,3600"
COLOR_FORMULA = "Gamma RGB 1.4"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (monitoring)"

Fetch = Callable[[str], bytes]
Post = Callable[[str, dict[str, Any]], bytes]


def post_json(url: str, body: dict[str, Any]) -> bytes:
    request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read()


# Landsat Collection 2 Level-2 surface reflectance (x 0.0000275 - 0.2), stretched from 0 to 0.25 as the
# scenarios' Landsat natural colour; its credit as the USGS asks.
LANDSAT = {"collection": "landsat-c2-l2", "bands": ("red", "green", "blue"), "rescale": "7273,16364", "folder": "landsat",
           "credit": "Landsat-data med tillstånd av U.S. Geological Survey (Microsoft Planetary Computer)"}
SENTINEL2 = {"collection": COLLECTION, "bands": BANDS, "rescale": RESCALE, "folder": "satellite",
             "credit": "Innehåller Copernicus Sentinel-data {year} (Microsoft Planetary Computer)"}


def platform_name(value: str) -> str:
    """Planetary Computer's platform as the screens name it: landsat-9 Landsat 9, Sentinel-2A as it is."""
    return value.replace("landsat-", "Landsat ") if value.startswith("landsat-") else value


def search(bbox: tuple[float, float, float, float], since: datetime, now: datetime, post: Post,
           collection: str = COLLECTION) -> list[dict[str, Any]]:
    body = {"collections": [collection], "bbox": list(bbox), "limit": 100,
            "datetime": f"{since:%Y-%m-%dT%H:%M:%SZ}/{now:%Y-%m-%dT%H:%M:%SZ}",
            "sortby": [{"field": "datetime", "direction": "desc"}]}
    return json.loads(post(STAC_SEARCH, body)).get("features") or []


def datatakes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The scenes by datatake (one pass, every tile of it), newest first, with their mean cloud."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(item["properties"]["datetime"][:16], []).append(item)
    takes = [{"time_utc": key + ":00Z", "items": [item["id"] for item in group],
              "platform": platform_name(group[0]["properties"].get("platform", "Sentinel-2")),
              "cloud": round(sum(item["properties"].get("eo:cloud_cover", 100) for item in group) / len(group))}
             for key, group in groups.items()]
    return sorted(takes, key=lambda take: take["time_utc"], reverse=True)


def choose(takes: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    recent = [take for take in takes if datetime.fromisoformat(take["time_utc"].replace("Z", "+00:00")) >= now - RECENT
              and take["cloud"] <= CLOUD_PERCENT]
    if recent:
        return recent[0]
    return min(takes, key=lambda take: (take["cloud"], take["time_utc"])) if takes else None


def image_url(item: str, bbox: tuple[float, float, float, float], kind: dict[str, Any] = SENTINEL2) -> str:
    west, south, east, north = bbox
    width, height = round((east - west) * PIXELS_PER_DEGREE[0]), round((north - south) * PIXELS_PER_DEGREE[1])
    params = [("collection", kind["collection"]), ("item", item), *(("assets", band) for band in kind["bands"]),
              ("rescale", kind["rescale"]), ("nodata", "0"), ("color_formula", COLOR_FORMULA)]
    return f"{DATA_API}/{west},{south},{east},{north}/{width}x{height}.png?" + urlencode(params)


class Latest:
    """The latest image, kept in data/monitoring/<area>/satellite/ between polls and restarts."""

    def __init__(self, bbox: tuple[float, float, float, float], data_dir: Path, fetch: Fetch, post: Post = post_json,
                 kind: dict[str, Any] = SENTINEL2) -> None:
        self.bbox = bbox
        self.kind = kind
        self.dir = data_dir / kind["folder"]
        self.fetch = fetch
        self.post = post
        self.searched: datetime | None = None
        try:
            self.meta: dict[str, Any] | None = json.loads((self.dir / "latest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.meta = None

    @property
    def png(self) -> bytes | None:
        try:
            return (self.dir / "latest.png").read_bytes()
        except OSError:
            return None

    def update(self, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or datetime.now(timezone.utc)
        if self.searched and now - self.searched < SEARCH_EVERY:
            return self.meta
        take = choose(datatakes(search(self.bbox, now - FALLBACK, now, self.post, self.kind["collection"])), now)
        self.searched = now
        if take is None or (self.meta and self.meta["items"] == take["items"]):
            return self.meta
        layers = [Image.open(io.BytesIO(self.fetch(image_url(item, self.bbox, self.kind)))).convert("RGBA") for item in take["items"]]
        image = layers[0]
        for layer in layers[1:]:
            image = Image.alpha_composite(image, layer.resize(image.size))
        self.dir.mkdir(parents=True, exist_ok=True)
        image.save(self.dir / "latest.png", "PNG", optimize=True)
        self.meta = {**take, "bbox": list(self.bbox), "attribution": self.kind["credit"].format(year=take["time_utc"][:4]),
                     "recent": take["cloud"] <= CLOUD_PERCENT
                     and datetime.fromisoformat(take["time_utc"].replace("Z", "+00:00")) >= now - RECENT}
        (self.dir / "latest.json").write_text(json.dumps(self.meta), encoding="utf-8")
        return self.meta
