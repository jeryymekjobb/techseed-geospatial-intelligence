"""The Västmanland 2014 wildfire scenario: data files, area, period and playback."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIRMS_FILES = [
    REPO_ROOT / "satellite_data" / "firms" / "fire_archive_M-C61_816007.csv",
    REPO_ROOT / "satellite_data" / "firms" / "fire_archive_SV-C2_816008.csv",
]
TERRAIN_FILE = REPO_ROOT / "app" / "layers" / "terrain-vastmanland.geojson"

TITLE = "Skogsbranden i Västmanland 2014"
# FIRMS selection box; the detections of the fire lie within 59.83-60.01 N, 16.01-16.30 E.
FIRE_BBOX = (59.70, 60.10, 15.90, 16.50)  # min_lat, max_lat, min_lon, max_lon
# Map view with a margin, so surrounding places and lakes are visible.
VIEW_BBOX = (59.75, 60.08, 15.85, 16.45)
PERIOD_START = date(2014, 7, 29)
PERIOD_END = date(2014, 8, 14)
PLAYBACK_START = datetime(2014, 7, 31, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2014, 8, 15, 0, 0, tzinfo=timezone.utc)

ATTRIBUTION = {
    "firms": "NASA FIRMS, MODIS C6.1 och VIIRS S-NPP C2, arkivuttag 816007 och 816008",
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
}
