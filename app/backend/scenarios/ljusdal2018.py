"""The Kårböle fire in Ljusdal 2018, replayed from NASA FIRMS archive data.

Chosen 2026-10-07 from the archive naturkatastrofer-sverige-demos-2026-10-07 ("Ljusdal/
Kårböle 2018"). Lightning set the forest alight near Kårböle on 14 July 2018; the fire grew
fast round 17-18 July, the rescue service put it at about 8,500 ha, 70-90 people in Kårböle
were evacuated and 7-8 buildings burnt (SVT, Sveriges Radio, Länsstyrelsen Gävleborg).
Copernicus EMS mapped it as area 01 Enskogen of activation EMSR298, from 828 ha on 17 July
to 17,936 ha in 16 areas on 7 August. The FIRMS requests 818930, 818932 and 818934 are in
satellite_data/firms/.

Its data apart from FIRMS live in the unversioned data/ljusdal2018/. The satellite images
and the EMS perimeters come in a later step.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "ljusdal2018"
FIRMS_DIR = REPO_ROOT / "satellite_data" / "firms"

INCIDENT = "wildfire"
INCIDENT_PLACE = "branden"
INCIDENT_AREA = "brandområdet"

TITLE = "Skogsbranden vid Kårböle 2018"
DATA_LABEL = "Historiska data 2018 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: WILDFIRE – Ljusdal/Kårböle 2018, historiska data"

FIRMS_FILES = [
    FIRMS_DIR / "fire_archive_M-C61_818930.csv",
    FIRMS_DIR / "fire_archive_SV-C2_818934.csv",
    FIRMS_DIR / "fire_archive_J1V-C2_818932.csv",
]
TERRAIN_FILE = DATA / "osm" / "terrain-ljusdal.geojson"
TARGETS_FILE = DATA / "osm" / "targets-ljusdal.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-ljusdal-2018.csv"
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
LANDSAT_DIR = DATA / "landsat"
SENTINEL2_DIR = DATA / "sentinel2"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2018.json"

# Mean position of the FIRMS detections of the fire (14-28 July 2018).
FIRE_CENTRE = (61.954, 15.407)
# FIRMS selection box round Copernicus EMS's area Enskogen (15.20-15.51 E, 61.89-62.04 N).
FIRE_BBOX = (61.85, 62.10, 15.05, 15.65)  # min_lat, max_lat, min_lon, max_lon
VIEW_BBOX = (61.82, 62.12, 15.0, 15.7)
# The offline map, the DEM and the satellite images (west, south, east, north): the fire, Ängra
# and Kårböle with a margin. The weather stations, Hamra A and Sveg A, lie outside it.
MAP_BBOX = (14.9, 61.75, 15.8, 62.2)
PERIOD_START = date(2018, 7, 12)
PERIOD_END = date(2018, 8, 8)
PLAYBACK_START = datetime(2018, 7, 12, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2018, 8, 9, 0, 0, tzinfo=timezone.utc)
# The first MODIS detections came on 14 July; the check starts on the 17th, as it grew fast.
CHECK_START_UTC = "2018-07-17T08:30:00Z"

DATABASE = "ljusdal2018"
TILES_FILE = "ljusdal.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 15.5, "lat": 62.5, "height": 1_100_000, "pitch": -80, "seconds": 2.0},  # Sweden
    {"lon": 15.35, "lat": 61.75, "height": 120_000, "pitch": -60, "seconds": 2.2},  # Hälsingland
]

# The satellites of the period by NORAD number (tools/fetch_tle_history.py). The FIRMS
# `satellite` field names Aqua, Terra, SNPP and N20 (NOAA-20).
TLE_SATELLITES = {
    "25994": "Terra", "27424": "Aqua", "37849": "Suomi NPP", "43013": "NOAA-20", "39084": "Landsat 8",
    "39634": "Sentinel-1A", "41456": "Sentinel-1B", "40697": "Sentinel-2A", "42063": "Sentinel-2B", "25544": "ISS",
}
TLE_START, TLE_END = "2018-07-08", "2018-08-11"
SATELLITE_ROLES = {
    "27424": {"firms": "Aqua", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "25994": {"firms": "Terra", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "37849": {"firms": "SNPP", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "43013": {"firms": "N20", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln och rök", "half_swath_km": None},
    "41456": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln och rök", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
}
SATELLITE_LABEL = "Position 2018, beräknad ur banelement (SGP4) – inte en observation"

# The satellite images come in a later step.
LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före branden", "during": "Under branden", "after": "Efter branden – jämförelse"}
LANDSAT_FOCUS_AREA = (15.20, 61.89, 15.51, 62.04)  # Copernicus EMS's area Enskogen
# About 30 m over MAP_BBOX: 0.9 degrees of longitude and 0.45 of latitude at 62 N.
LANDSAT_SIZE = (1570, 1670)
SENTINEL2_SCENES: dict = {}

# The fire's own modules: the forecast from SMHI Hamra A, the nearest station with complete
# hourly weather (temperature, humidity, wind, rain) from 1 May 2018.
FORECAST_STATION = "SMHI Hamra A"
FORECAST_WEATHER_FILES = [WEATHER_DIR / "spinup" / "hamra-a-114410.csv", WEATHER_DIR / "hamra-a-114410.csv"]
FORECAST_METHOD = ("FBP C-2, FWI från SMHI Hamra A, rådande väder vid passagen, kalibrerad mot observerad spridning; "
                   "spann halva–dubbla hastigheten")
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors, brandfront och prognos ur FIRMS 2018 (forecast.py)"

ATTRIBUTION = {
    "firms": "NASA FIRMS, MODIS C6.1 och VIIRS S-NPP och NOAA-20 C2, arkivuttag 818930, 818934 och 818932",
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE), Hamra A och Sveg A",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
