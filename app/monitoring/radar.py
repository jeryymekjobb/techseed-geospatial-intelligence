"""SMHI's weather radar, live, over the monitored area: the composite every 5 minutes as rain rates
in the municipality, for the cloudburst rule (rules.cloudburst_candidates) and as an image on the
maps, as the scenarios show it (tools/fetch_smhi_radar.py, whose conversion is used here).

Each poll reads the day's list of images, fetches those of the last WINDOW that are not kept yet
(about 15 kB each) and keeps their rain rates on a grid over the area, inside the municipality's
border. The rain rate is estimated from the radar's reflectivity (Z = 200 R^1.6), not measured on
the ground. Needs numpy and Pillow (tools/requirements-data.txt), as the scenarios' radar.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw

from app.monitoring import geo
from tools import fetch_smhi_radar as smhi

ATTRIBUTION = "SMHI öppna data, väderradar (CC BY 4.0 SE); regnintensitet uppskattad ur radarn, inte mätt på marken"
WINDOW = timedelta(hours=1)
FRAME_MINUTES = 5

Fetch = Callable[[str], bytes]


def _empty_png() -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(out, "PNG")
    return out.getvalue()


EMPTY_PNG = _empty_png()


def day_list_url(day: datetime) -> str:
    return f"{smhi.API}/{day.year}/{day.month:02d}/{day.day:02d}?format=tif"


def border_mask(border: dict[str, Any] | None, bbox: tuple[float, float, float, float], size: tuple[int, int]) -> np.ndarray:
    """Which pixels of the area's grid lie in the municipality (all of them without a border)."""
    width, height = size
    if not border:
        return np.ones((height, width), dtype=bool)
    west, south, east, north = bbox
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)
    for polygon in geo.polygons(border):
        for index, ring in enumerate(polygon):
            points = [((lon - west) / (east - west) * width, (north - lat) / (north - south) * height) for lon, lat, *_ in ring]
            draw.polygon(points, fill=0 if index else 1)
    return np.array(image, dtype=bool)


class Radar:
    """The radar's frames of the last WINDOW over one area, kept between polls."""

    def __init__(self, bbox: tuple[float, float, float, float], fetch: Fetch) -> None:
        self.bbox = bbox
        self.fetch = fetch
        self.lat, self.lon, self.size = smhi.cut_out(bbox)
        self.north, self.east = smhi.sweref99tm(self.lat, self.lon)
        self.frames: dict[str, dict[str, Any]] = {}
        self.mask: np.ndarray | None = None
        self.png: bytes | None = None
        self.png_key: str | None = None

    def rates(self, tiff_bytes: bytes) -> np.ndarray:
        """mm/h on the area's grid; NaN without rain."""
        tiff = Image.open(io.BytesIO(tiff_bytes))
        left, top, size_x, size_y = smhi.geotransform(tiff)
        values = np.array(tiff)
        cols = np.floor((self.east - left) / size_x).astype(int)
        rows = np.floor((top - self.north) / size_y).astype(int)
        inside = (rows >= 0) & (rows < values.shape[0]) & (cols >= 0) & (cols < values.shape[1])
        picked = np.full(self.lat.shape, smhi.NO_DATA, dtype=np.uint8)
        picked[inside] = values[rows[inside], cols[inside]]
        return smhi.rain_rate(picked).astype(np.float32)

    def update(self, border: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
        """Fetch the frames of the last WINDOW not kept yet; the rain in the municipality."""
        now = now or datetime.now(timezone.utc)
        if self.mask is None:
            self.mask = border_mask(border, self.bbox, self.size)
        listed = []
        for day in sorted({now.date(), (now - WINDOW).date()}):
            day_time = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            for item in json.loads(self.fetch(day_list_url(day_time))).get("files") or []:
                moment = smhi.moment_of(item["key"])
                link = next((f["link"] for f in item.get("formats") or [] if f.get("key") == "tif"), None)
                if moment and link and now - WINDOW < moment <= now:
                    listed.append((moment, item["key"], link))
        for moment, key, link in listed:
            if key not in self.frames:
                self.frames[key] = {"time": moment, "rates": self.rates(self.fetch(link))}
        self.frames = {key: frame for key, frame in self.frames.items() if now - WINDOW < frame["time"] <= now}
        if not self.frames:
            return {"frames": 0, "latest_utc": None, "max_mm_h": 0.0, "hour_mm": 0.0, "max_at": None}
        latest_key = max(self.frames, key=lambda key: self.frames[key]["time"])
        latest = self.frames[latest_key]
        inside = np.where(self.mask, latest["rates"], np.nan)
        hour = np.nansum([np.where(self.mask, frame["rates"], np.nan) for frame in self.frames.values()], axis=0) * FRAME_MINUTES / 60
        peak = float(np.nanmax(inside)) if np.isfinite(inside).any() else 0.0
        at = None
        if peak > 0:
            row, col = np.unravel_index(np.nanargmax(inside), inside.shape)
            at = [round(float(self.lat[row, col]), 4), round(float(self.lon[row, col]), 4)]
        if self.png_key != latest_key:
            out = io.BytesIO()
            Image.fromarray(smhi.colours(latest["rates"]), "RGBA").save(out, "PNG", optimize=True)
            self.png, self.png_key = out.getvalue(), latest_key
        # The highest rate in the municipality in each frame, for mission control's chart.
        series = []
        for frame in sorted(self.frames.values(), key=lambda item: item["time"]):
            masked = np.where(self.mask, frame["rates"], np.nan)
            series.append({"time_utc": frame["time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "max_mm_h": round(float(np.nanmax(masked)), 1) if np.isfinite(masked).any() else 0.0})
        return {"frames": len(self.frames), "latest_utc": latest["time"].strftime("%Y-%m-%dT%H:%M:%SZ"), "series": series,
                "max_mm_h": round(peak, 1), "hour_mm": round(float(np.nanmax(hour)) if hour.size else 0.0, 1), "max_at": at,
                "bbox": list(self.bbox)}
