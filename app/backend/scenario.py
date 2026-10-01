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
WEATHER_DIR = REPO_ROOT / "weather_data" / "smhi"
WIND_FILE = REPO_ROOT / "weather_data" / "era5-land" / "era5-land-vastmanland-2014.csv"
# Mean position of the FIRMS detections, used for station distances.
FIRE_CENTRE = (59.89, 16.175)

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
    "smhi": "SMHI öppna data (CC BY 4.0 SE), Sala A och Kloten A",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
}
