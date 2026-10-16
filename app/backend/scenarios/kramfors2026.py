"""The cloudburst over Kramfors on 15-16 August 2026.

Asked for by the project on 2026-10-16 as "the flood in Kramfors on 16 August 2026"; the
investigation that day found that the rain fell on Saturday 15 August, mostly between 15 and 17
UTC (17-19 Swedish time) in a narrow cell over Kramfors, after SMHI's yellow warning for
cloudburst-like rain (Saturday 18:00 to Sunday 05:00, locally 30-60 mm). SMHI's station Kramfors
had 77.0 mm in the day to 16 August 06 UTC, Bollstabruk 50.4 and Åkroken 48.3; Härnösand 0.9.
On 16 August roads were closed or under water (855, 856 by Strinne), on 17 August a track fault
from a flooded embankment stopped the trains between Sundsvall and Umeå, and on 18 August the
cellar of Ådalshallen was pumped out (Tidningen Ångermanland, Sveriges Radio P4; partly behind
paywalls). A local cloudburst on roads and cellars, not a river flood; not the rain of 6-7
September 2025 (vasternorrland2025).

Its data live in the unversioned data/kramfors2026/. SMHI's August 2026 data are from its latest
four months, not yet quality-controlled.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "kramfors2026"

INCIDENT = "flood"
INCIDENT_PLACE = "Kramfors"
INCIDENT_AREA = "Ådalen"

TITLE = "Skyfallet i Kramfors 2026"
DATA_LABEL = "Historiska data augusti 2026 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Kramfors augusti 2026, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Skyfallet över Kramfors 15–16 augusti 2026. Det återges med verkliga data, inte i realtid.",
    "SMHI varnade för skyfallsliknande regn. Det mesta föll på lördagskvällen i ett smalt stråk över Kramfors.",
    "SMHI:s station i Kramfors fick 77 millimeter på ett dygn, Härnösand mindre än en millimeter.",
    "SMHI:s väderradar visar var regnet föll. Regnet är verkligt; SMHI:s data från augusti är ännu inte kvalitetsgranskade.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-kramfors.geojson"
TARGETS_FILE = DATA / "osm" / "targets-kramfors.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-kramfors-2026.csv"
RADAR_DIR = DATA / "radar"
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
LANDSAT_DIR = DATA / "landsat"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2026.json"

# Kramfors, where SMHI measured 77.0 mm in the day to 16 August 06 UTC.
FIRE_CENTRE = (62.929, 17.777)
FIRE_BBOX = (62.85, 63.02, 17.55, 18.0)  # min_lat, max_lat, min_lon, max_lon
# Map view: Kramfors, Bollstabruk and Ångermanälven by them.
VIEW_BBOX = (62.85, 63.02, 17.55, 18.0)
# The offline map, the DEM and the satellite images (west, south, east, north): Kramfors with
# SMHI's daily stations round it (Åkroken in the west, Sollefteå and Multrå in the north,
# Nora-Östanö in the east) and its hourly stations Lungö A and Västmarkum A.
MAP_BBOX = (17.2, 62.6, 18.3, 63.2)
PERIOD_START = date(2026, 8, 13)
PERIOD_END = date(2026, 8, 19)
PLAYBACK_START = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2026, 8, 18, 0, 0, tzinfo=timezone.utc)
# Sentinel-1C passes at 05:21 UTC on 16 August, about ten hours after the rain.
CHECK_START_UTC = "2026-08-16T05:00:00Z"

DATABASE = "kramfors2026"
TILES_FILE = "kramfors.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 17.5, "lat": 63, "height": 1_100_000, "pitch": -80, "seconds": 2.0},  # Sweden
    {"lon": 17.78, "lat": 62.82, "height": 45_000, "pitch": -60, "seconds": 2.2},  # Kramfors
]

# The flood's words for the land the radar's water is counted on and for the gauges.
FOCUS_LAND = "marken runt Kramfors"
RAIN_GAUGES = "SMHI:s mätare"
# SMHI's hourly rain (parameter 7) in the area, checked 2026-10-16: both lie outside the cell.
RAIN_STATIONS = {"128390": "Lungö A", "138070": "Västmarkum A"}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC; daily_rain.py), checked
# 2026-10-16.
DAILY_RAIN_STATIONS = {
    "127560": "Kramfors", "137020": "Bollstabruk", "127570": "Åkroken D", "137090": "Multrå D",
    "137100": "Sollefteå", "127480": "Gåltjärn", "128500": "Nora-Östanö D", "127380": "Härnösand",
}
DAILY_RAIN_DIR = DATA / "smhi-daily"

# The satellites over the area in the period and the ISS, by NORAD number; their images come in
# a later stage of the scenario.
TLE_SATELLITES = {
    "62261": "Sentinel-1C", "66315": "Sentinel-1D", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "60989": "Sentinel-2C", "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS",
}
TLE_START, TLE_END = "2026-08-11", "2026-08-23"
SATELLITE_ROLES = {
    "62261": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "66315": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "60989": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
}
SATELLITE_LABEL = "Position 2026, beräknad ur banelement (SGP4) – inte en observation"

LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före skyfallet", "during": "Under skyfallet", "after": "Efter skyfallet"}
LANDSAT_FOCUS_AREA = (17.7, 62.9, 17.85, 62.97)  # Kramfors town
# About 30 m over MAP_BBOX: 1.1 degrees of longitude and 0.6 of latitude at 62.9 N.
LANDSAT_SIZE = (1859, 2224)

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE): nederbörd per timme och dygn, väderradar; senaste månaderna, ej kvalitetsgranskade",
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2026",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
