"""The winter floods in Skåne 2024: Ringsjöarna, Hörbyån, Kävlingeån and Vombsjön.

Chosen 2026-10-07 from the archive naturkatastrofer-sverige-demos-2026-10-07 (event
"Översvämningar i Skåne och Östergötland", January-February 2024, source K32). SMHI's
account (https://www.smhi.se/kunskapsbanken/hydrologi/historiska-oversvamningar/
2024---vinteroversvamningar-i-skane-och-ostergotland): Ringsjöarna peaked at 54.94 m
(RH00) on 10 February, the highest since measuring began in 1974, and Heåkra in Hörbyån
and Eggelstad in Tolångaån had their highest flows since 1973. Unlike the Sundsvall
scenario this is a replayed event with real data, not a scenario.

Its data live in the unversioned data/skane2024/. The screens show SMHI's measured
flows and lake levels (HYDRO_DIR) and the rain; the satellite images, the sensors, the
assessment and the questions come in later steps.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "skane2024"

INCIDENT = "flood"
INCIDENT_PLACE = "Ringsjöarna"
INCIDENT_AREA = "Mellersta Skåne"

TITLE = "Översvämningarna i Skåne 2024"
DATA_LABEL = "Historiska data vintern 2024 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Skåne vintern 2024, historiska data"

FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-skane.geojson"
TARGETS_FILE = DATA / "osm" / "targets-skane.geojson"
WEATHER_DIR = DATA / "smhi"
# SMHI's measured flows and lake levels (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
WIND_FILE = DATA / "era5-land" / "era5-land-skane-2024.csv"
RADAR_DIR = DATA / "radar"
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
LANDSAT_DIR = DATA / "landsat"
SENTINEL2_DIR = DATA / "sentinel2"
SENTINEL1_DIR = DATA / "sentinel1"
MCF_DIR = DATA / "mcf"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2024.json"

# Ringsjöarna, whose level set the record on 10 February.
FIRE_CENTRE = (55.885, 13.47)
FIRE_BBOX = (55.62, 55.97, 13.05, 13.85)  # min_lat, max_lat, min_lon, max_lon
# Map view: Ringsjöarna, Hörbyån, Vombsjön and Kävlingeån down to Kävlinge.
VIEW_BBOX = (55.62, 55.97, 13.05, 13.85)
# The offline map, the DEM and the satellite images (west, south, east, north), with every
# station used, from Högsmölla in the west to Hörby A and Eggelstad in the east.
MAP_BBOX = (13.0, 55.6, 13.9, 55.98)
PERIOD_START = date(2024, 1, 20)
PERIOD_END = date(2024, 2, 25)
PLAYBACK_START = datetime(2024, 1, 20, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2024, 2, 26, 0, 0, tzinfo=timezone.utc)
# Sentinel-1A passes over Ringsjöarna at 05:33 UTC on 8 February, two days before the lake's peak.
CHECK_START_UTC = "2024-02-08T05:00:00Z"

DATABASE = "skane2024"
TILES_FILE = "skane.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 14, "lat": 57, "height": 3_000_000, "pitch": -90, "seconds": 2.0},   # Southern Scandinavia
    {"lon": 13.5, "lat": 56.0, "height": 600_000, "pitch": -80, "seconds": 2.0},  # Skåne
    {"lon": 13.45, "lat": 55.62, "height": 90_000, "pitch": -60, "seconds": 2.2},  # Mid-Skåne
]

# The rain gauges with hourly sums in SMHI's open data (parameter 7): SMHI's Hörby A and
# the water utilities' gauges round Ringsjöarna and the Kävlingeån catchment. Härlösa PST
# is left out: it has two hours in the period.
RAIN_STATIONS = {
    "53530": "Hörby A", "22128523": "Kungshult VV", "22128522": "Billinge VV", "22128520": "Eslöv VV",
    "22128524": "Löberöd PST", "22128144": "Veberöd TS",
}
# SMHI's hydrological stations (tools/fetch_smhi_hydro.py): flow every 15 minutes (parameter
# 2) or water level by the day (parameter 3). Checked 2026-10-07; the outflows at Ringsjödammen
# and Vombsjön have no 15-minute archive.
HYDRO_STATIONS = {
    "2176:3": "Ringsjödammen övre",  # the level of Ringsjöarna
    "2018:3": "Vombsjön övre",
    "2128:2": "Heåkra",              # Hörbyån, into Östra Ringsjön
    "2126:2": "Ellinge",             # Kävlingeån below Vombsjön
    "2171:2": "Högsmölla",           # Kävlingeån near the sea
    "2125:2": "Eggelstad",           # Tolångaån
}

# The satellites that imaged the area in the period (Planetary Computer catalogue, checked
# 2026-10-07) and the ISS, by NORAD number. In 2024 only Sentinel-1A was in orbit.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS",
}
TLE_START, TLE_END = "2024-01-16", "2024-02-28"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
}
SATELLITE_LABEL = "Position 2024, beräknad ur banelement (SGP4) – inte en observation"

# The satellite images come in a later step.
LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före översvämningen", "during": "Under översvämningen", "after": "Efter översvämningen"}
LANDSAT_FOCUS_AREA = (13.35, 55.82, 13.65, 55.95)  # Ringsjöarna and the lower Hörbyån
# About 30 m over MAP_BBOX: 0.9 degrees of longitude and 0.38 of latitude at 55.8 N.
LANDSAT_SIZE = (1880, 1410)
SENTINEL1_ACQUISITIONS: list = []
SENTINEL2_SCENES: dict = {}

# MCF's (formerly MSB's) overview flood maps; in the area they map Kävlingeån (2020) and
# Höje å (2025). Same service and layers as the Sundsvall scenario.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": {"13": "100-årsflöde", "9": "Beräknat högsta flöde"},
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
    "visible": ["13"],
}

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors, 100-årsflöden © MCF (tidigare MSB)"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE): nederbörd vid Hörby A och VA-huvudmännens mätare, vattenföring och vattenstånd",
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2024",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
