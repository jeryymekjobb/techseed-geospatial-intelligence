"""The rain in Västernorrland on 6-7 September 2025: Härnösand, Kramfors and the High Coast.

Chosen 2026-10-15 from the feasibility study reports/2026-10-15-forstudie-
oversvamningsscenarier-claude-opus-5-5.md. Länsstyrelsen Västernorrland's investigation
"Utredning av konsekvenser av kraftig nederbörd 6-7 september 2025" (2026:12, 28 August
2026) calls it extreme areal precipitation: a band of rain came in just south of Härnösand
and moved north towards Västerbotten in the evening of 6 September and the morning of
7 September. Myckelgensjö had 140.0 mm and Kramfors 123.5 mm in the day; small
watercourses flooded, roads were washed away, and two trains derailed on the morning of
7 September, at Stugusjön west of Skorped and north of Prästmon. Like Skåne 2024 this is a
replayed event with real data, not a scenario.

Its data live in the unversioned data/vasternorrland2025/. SMHI measures rain by the hour
only outside the core (Hemling A, Västmarkum A, Lungö A); the core stations report by the
day, so the radar shows where the rain fell.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "vasternorrland2025"

INCIDENT = "flood"
INCIDENT_PLACE = "Kramfors"
INCIDENT_AREA = "Västernorrland"

TITLE = "Regnet i Västernorrland 2025"
DATA_LABEL = "Historiska data september 2025 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Västernorrland september 2025, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Det kraftiga regnet i Västernorrland 6–7 september 2025. Det återges med verkliga data, inte i realtid.",
    "Ett regnband drog norrut från Härnösand under kvällen och natten. Kramfors fick 123,5 millimeter på ett dygn.",
    "SMHI:s väderradar visar var regnet föll. SMHI:s egna mätare låg utanför regnets kärna.",
    "Radarbilder från Sentinel-1 före, mitt i och efter regnet, och bilder från Sentinel-2 och Landsat 8 före och efter, som är delvis molniga.",
    "Vägar spolades bort och två tåg spårade ur på morgonen den 7 september, enligt Länsstyrelsens utredning.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-vasternorrland.geojson"
TARGETS_FILE = DATA / "osm" / "targets-vasternorrland.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-vasternorrland-2025.csv"
RADAR_DIR = DATA / "radar"
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
LANDSAT_DIR = DATA / "landsat"
# MET Norway's archived weather forecasts, as issued (tools/fetch_met_forecasts.py, met_forecast.py).
MET_FORECAST_DIR = DATA / "met-forecast"
# SMHI's observed lightning (tools/fetch_smhi_lightning.py).
LIGHTNING_DIR = DATA / "lightning"
SENTINEL2_DIR = DATA / "sentinel2"
SENTINEL1_DIR = DATA / "sentinel1"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2025.json"

# Kramfors, where SMHI measured 123.5 mm on 6 September.
FIRE_CENTRE = (62.929, 17.762)
FIRE_BBOX = (62.55, 63.62, 17.3, 18.6)  # min_lat, max_lat, min_lon, max_lon
# Map view: Härnösand in the south to Myckelgensjö and Skorped in the north.
VIEW_BBOX = (62.55, 63.62, 17.3, 18.6)
# The offline map, the DEM and the satellite images (west, south, east, north): Härnösand,
# Kramfors, the High Coast, Prästmon, Stugusjön by Skorped and the rain's core round
# Myckelgensjö, with SMHI's hourly stations Lungö A and Hemling A.
MAP_BBOX = (17.2, 62.5, 18.9, 63.7)
PERIOD_START = date(2025, 9, 4)
PERIOD_END = date(2025, 9, 10)
PLAYBACK_START = datetime(2025, 9, 6, 12, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2025, 9, 8, 12, 0, tzinfo=timezone.utc)
# Sentinel-1 passes at 05:21 UTC on 7 September, in the middle of the rain.
CHECK_START_UTC = "2025-09-07T05:00:00Z"

DATABASE = "vasternorrland2025"
TILES_FILE = "vasternorrland.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 17.5, "lat": 63, "height": 1_100_000, "pitch": -80, "seconds": 2.0},  # Sweden
    {"lon": 17.9, "lat": 62.3, "height": 220_000, "pitch": -60, "seconds": 2.2},  # Västernorrland
]

# The flood's words for the land the radar's water is counted on and for the gauges.
FOCUS_LAND = "marken runt Kramfors"
RAIN_GAUGES = "SMHI:s mätare"
# The rain gauges with hourly sums in SMHI's open data (parameter 7) in the area, checked
# 2026-10-15. They all lie outside the rain's core; Söråker (22228110) gives implausible values.
RAIN_STATIONS = {"128390": "Lungö A", "138070": "Västmarkum A", "138390": "Hemling A"}

# The satellites that imaged the area in the period (Planetary Computer catalogue, checked
# 2026-10-15) and the ISS, by NORAD number.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "62261": "Sentinel-1C", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "60989": "Sentinel-2C", "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS",
}
TLE_START, TLE_END = "2025-09-01", "2025-09-14"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "62261": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "60989": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
}
SATELLITE_LABEL = "Position 2025, beräknad ur banelement (SGP4) – inte en observation"

# Landsat 8 after the rain (tools/fetch_landsat_scene.py), 58 % cloud in the catalogue; no
# usable scene before it (checked 2026-10-15).
LANDSAT_SCENES = {"after": "LC08_L2SP_195016_20250910_02_T1"}
LANDSAT_ROLES = {"before": "Före regnet", "during": "Under regnet", "after": "Efter regnet"}
LANDSAT_FOCUS_AREA = (17.6, 62.85, 17.95, 63.0)  # Kramfors and the Ångermanälven by it
# About 30 m over MAP_BBOX: 1.7 degrees of longitude and 1.2 of latitude at 63.1 N.
LANDSAT_SIZE = (2854, 4448)
# Sentinel-1 radar acquisitions (Planetary Computer catalogue, sentinel-1-grd, checked 2026-10-15;
# the start of the pass's first product): before the rain, in the middle of it and the morning
# after. Each covers Härnösand, Kramfors, Prästmon and Stugusjön whole.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2025-09-02T05:13:19Z", "satellite": "Sentinel-1C", "norad": "62261"},
    {"time_utc": "2025-09-07T05:21:30Z", "satellite": "Sentinel-1C", "norad": "62261"},
    {"time_utc": "2025-09-08T05:14:39Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py): the clearest datatakes before and after, by product
# name up to the relative orbit; 7 September is 99-100 % cloud. Catalogue tile cloud 9-15 % on
# 31 August and 39-53 % on 10 September; the tool measures the focus area's own.
SENTINEL2_SCENES = {
    "before": "S2B_MSIL2A_20250831T102559_R108",
    "after": "S2B_MSIL2A_20250910T102559_R108",
}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (4281, 6672)

# Roads and railways the rain damaged, as Länsstyrelsen Västernorrland's investigation tells it
# ("Utredning av konsekvenser av kraftig nederbörd 6-7 september 2025", 2026:12, pages 11-12, 16,
# 41 and 51-56). The places are approximate: the report names them in words, and the points are
# the nearest OSM way to the place it names (checked 2026-10-15). Times the report gives to the
# minute are exact; "strax innan 8-tiden" and "förmiddagen" are approximated and marked so, and
# the roads without a time are put at the morning of 7 September, also marked. No causes of the
# derailments are stated: the Swedish Accident Investigation Authority (SHK O-7/25) has not reported.
ROUTE_REPORT = ("Länsstyrelsen Västernorrland, Utredning av konsekvenser av kraftig nederbörd 6–7 september 2025 "
                "(2026:12)")
ROUTE_IMPACTS = [
    {"time_utc": "2025-09-07T02:41:00Z", "kind": "alert", "approximate_time": False,
     "text": "Första larmet till Länsstyrelsen om skador på vägar och järnväg"},
    {"time_utc": "2025-09-07T05:00:00Z", "kind": "road", "approximate_time": False, "latitude": 62.80321, "longitude": 17.85806,
     "text": "Väg 738 vid Judeby bortspolad vid en vägtrumma – en person omkom"},
    {"time_utc": "2025-09-07T05:50:00Z", "kind": "rail", "approximate_time": True, "latitude": 63.38113, "longitude": 17.7737,
     "text": "Godståg spårar ur på Stambanan genom övre Norrland vid Stugusjön, väster om Skorped"},
    {"time_utc": "2025-09-07T06:00:00Z", "kind": "road", "approximate_time": True, "latitude": 63.05743, "longitude": 17.6088,
     "text": "Riksväg 90 avspolad vid Kyrkdal, avstängd mellan Hållsätter och Kärr"},
    {"time_utc": "2025-09-07T06:00:00Z", "kind": "road", "approximate_time": True, "latitude": 63.56755, "longitude": 17.80761,
     "text": "Väg 1036 skadad mellan Remmarbäcken och Seltjärn"},
    {"time_utc": "2025-09-07T06:00:00Z", "kind": "road", "approximate_time": True, "latitude": 63.17686, "longitude": 17.56248,
     "text": "Väg 335 avstängd vid Sånga kyrka"},
    {"time_utc": "2025-09-07T07:45:00Z", "kind": "alert", "approximate_time": True,
     "text": "VMA: farligt att färdas på vägar i de fyra drabbade kommunerna"},
    {"time_utc": "2025-09-07T08:30:00Z", "kind": "rail", "approximate_time": True, "latitude": 63.09583, "longitude": 17.7471,
     "text": "Timmertåg spårar ur på övre Ådalsbanan norr om Prästmon"},
    {"time_utc": "2025-09-07T09:38:00Z", "kind": "alert", "approximate_time": False,
     "text": "SMHI:s första varning för höga flöden i små vattendrag"},
]
# The OSM roads and railways under heavy rain, computed from SMHI's radar (tools/derive_route_exposure.py).
ROUTE_EXPOSURE_FILE = DATA / "routes" / "exposure.json"

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE): nederbörd vid Lungö A, Västmarkum A och Hemling A, väderradar",
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2025",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
