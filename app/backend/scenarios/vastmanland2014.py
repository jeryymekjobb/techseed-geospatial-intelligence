"""The Västmanland 2014 wildfire, replayed from NASA FIRMS archive data."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

# The kind of incident, which decides the incident's own modules (FIRMS, fire spread and
# forecast, wind barbs, fire sensors and assessment), and the words the screens use for it.
INCIDENT = "wildfire"
INCIDENT_PLACE = "branden"
INCIDENT_AREA = "brandområdet"

TITLE = "Skogsbranden i Västmanland 2014"
DATA_LABEL = "Historiska data 2014 – uppspelning, inte live"
# Mission control's header.
CONTROL_LABEL = "Scenario: WILDFIRE – Västmanland 2014, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Skogsbranden i Västmanland började den 31 juli 2014. Den återges med verkliga arkivdata, inte live.",
    "Satellitdetektioner av värme från NASA FIRMS: Terra och Aqua (MODIS) och Suomi NPP (VIIRS).",
    "Landsat 8-bilder från före (10 juni), under (4 augusti) och efter branden (14 september, en jämförelse): naturliga färger, kortvågig IR och fukt i vegetationen (NDMI).",
    "En spridningsprognos (modell) med brandväder från SMHI Sala A och vind från ERA5-Land.",
    "IoT-sensorerna är syntetiska (simulerade).",
]

FIRMS_FILES = [
    REPO_ROOT / "satellite_data" / "firms" / "fire_archive_M-C61_816007.csv",
    REPO_ROOT / "satellite_data" / "firms" / "fire_archive_SV-C2_816008.csv",
]
TERRAIN_FILE = REPO_ROOT / "app" / "layers" / "terrain-vastmanland.geojson"
TARGETS_FILE = REPO_ROOT / "osm_data" / "targets-vastmanland.geojson"
WEATHER_DIR = REPO_ROOT / "weather_data" / "smhi"
WIND_FILE = REPO_ROOT / "weather_data" / "era5-land" / "era5-land-vastmanland-2014.csv"
# The DEM tiles and the 3D terrain built from them (tools/fetch_copernicus_dem.py,
# tools/build_terrain.py), the Landsat images and the element sets.
DEM_DIR = REPO_ROOT / "data" / "dem"
TERRAIN_DIR = REPO_ROOT / "data" / "terrain"
LANDSAT_DIR = REPO_ROOT / "data" / "landsat"
TLE_DIR = REPO_ROOT / "data" / "tle"
TLE_FILE_NAME = "tle-2014.json"

# Mean position of the FIRMS detections, used for station distances.
FIRE_CENTRE = (59.89, 16.175)
# FIRMS selection box; the detections of the fire lie within 59.83-60.01 N, 16.01-16.30 E.
FIRE_BBOX = (59.70, 60.10, 15.90, 16.50)  # min_lat, max_lat, min_lon, max_lon
# Map view with a margin, so surrounding places and lakes are visible.
VIEW_BBOX = (59.75, 60.08, 15.85, 16.45)
# The area of the offline map, the DEM and the Landsat images (lon/lat, west, south, east,
# north): the map view with the margin the 2D map allows for panning.
MAP_BBOX = (15.5, 59.55, 16.8, 60.3)
PERIOD_START = date(2014, 7, 29)
PERIOD_END = date(2014, 8, 14)
PLAYBACK_START = datetime(2014, 7, 31, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2014, 8, 15, 0, 0, tzinfo=timezone.utc)
# tools/check_demo.py starts here: a VIIRS pass at 09:48 and the Landsat scene at 10:06 come within minutes.
CHECK_START_UTC = "2014-08-04T09:30:00Z"

# The local PostGIS database (docker-compose.yml) and the offline tiles in data/tiles/.
DATABASE = "firemap"
TILES_FILE = "vastmanland.mbtiles"

# Camera route from space to the incident, about ten seconds in total, so visitors can follow it.
CAMERA_ROUTE = [
    {"lon": 12, "lat": 50, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 58, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 16, "lat": 61, "height": 1_100_000, "pitch": -80, "seconds": 2.0},   # Sweden
    {"lon": 16.3, "lat": 59.6, "height": 160_000, "pitch": -60, "seconds": 2.2},  # Mälardalen
]

# The satellites of the period by NORAD number (tools/fetch_tle_history.py), a few days
# around the playback so an element set from before the start is there as well.
# Sentinel-1A was still in commissioning in August 2014 and Sentinel-2A was launched in
# 2015, so neither is here.
TLE_SATELLITES = {"25994": "Terra", "27424": "Aqua", "37849": "Suomi NPP", "39084": "Landsat 8", "25544": "ISS"}
TLE_START, TLE_END = "2014-07-27", "2014-08-17"
# What each satellite contributes to the demo; the FIRMS `satellite` field names the first three.
# half_swath_km decides when a pass covers the fire: MODIS 2330 km, VIIRS 3040 km and
# Landsat 8 OLI 185 km across; the ISS has no instrument in the demo.
SATELLITE_ROLES = {
    "27424": {"firms": "Aqua", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "25994": {"firms": "Terra", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "37849": {"firms": "SNPP", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
}
SATELLITE_LABEL = "Position 2014, beräknad ur banelement (SGP4) – inte en observation"

# Landsat 8 scenes before, during and after the fire (tools/fetch_landsat_scene.py):
# - 10 June 2014, 10:00 UTC (path 193): before the fire, clear over the fire area;
# - 4 August 2014, 10:06 UTC (path 194): Landsat 8 over the fire as it spread fastest;
# - 14 September 2014, 10:00 UTC (path 193): after the fire, clear over the whole burnt area.
LANDSAT_SCENES = {
    "before": "LC08_L2SP_193018_20140610_02_T1",
    "during": "LC08_L2SP_194018_20140804_02_T1",
    "after": "LC08_L2SP_193018_20140914_02_T1",
}
LANDSAT_ROLES = {"before": "Före branden", "during": "Under branden", "after": "Efter branden – jämförelse"}
# The area whose coverage and cloud each scene reports (the FIRMS selection of the fire),
# as west, south, east, north.
LANDSAT_FOCUS_AREA = (16.01, 59.83, 16.30, 60.01)
# About 30 m, the Landsat resolution, over MAP_BBOX: 1.3 degrees of longitude and 0.75 of latitude at 60 N.
LANDSAT_SIZE = (2410, 2780)

# The fire's own modules: the forecast (app/backend/forecast.py) and the spatial questions.
FORECAST_STATION = "SMHI Sala A"
FORECAST_WEATHER_FILES = [WEATHER_DIR / "spinup" / "sala-a-96560.csv", WEATHER_DIR / "sala-a-96560.csv"]
FORECAST_METHOD = ("FBP C-2, FWI från SMHI Sala A, rådande väder vid passagen, kalibrerad mot observerad spridning; "
                   "spann halva–dubbla hastigheten")
FORECAST_REPORT = "reports/2026-10-01-brandspridningsanalys-vastmanland-2014-claude-opus-5-5.md"
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors, brandfront och prognos ur FIRMS 2014 (forecast.py)"

ATTRIBUTION = {
    "firms": "NASA FIRMS, MODIS C6.1 och VIIRS S-NPP C2, arkivuttag 816007 och 816008",
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE), Sala A och Kloten A",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    # The Copernicus DEM licence's notice for modified data (the 3D terrain mesh).
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
