"""The coastal erosion on Falsterbonäset, 2012–2026.

Chosen 2026-10-26 from the feasibility study
reports/2026-10-26-forstudie-falsterbo-stranderosion-claude-opus-5-5.md: the long-term trend
rather than one storm. A 2026 LTH student thesis (Sennmark, TVVR26/5021) finds that the beaches'
growth seaward, seen in orthophotos since 1939, stopped round 2012 and turned sharply landward
after storm Babet (October 2023), and that by March 2026 about half the dune sand Babet took had
come back, most at Falsterbo and least at Kämpinge. SMHI's Skanör gauge gives the storm surges:
168.6 cm (RH2000) at storm Axel on 4 January 2017 and 149.5 cm at Babet on 21 October 2023.

Unlike the other floods this scenario spans many years: it starts at a month a second, does
not slow down at satellite passes and shows no satellite orbits or wind. Its images (orthophotos
and satellite scenes, with each satellite's position when it took the image), SGU's erosion
layers, Copernicus Marine's waves and synthetic beach sensors are later steps of the study's plan.

Its data live in the unversioned data/falsterbo/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "falsterbo"

INCIDENT = "flood"
INCIDENT_PLACE = "Falsterbonäset"
INCIDENT_AREA = "Falsterbonäsets stränder"

TITLE = "Stranderosionen på Falsterbonäset 2012–2026"
DATA_LABEL = "Historiska data 2012–2026 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: EROSION – Falsterbonäset 2012–2026, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, at the scenario's start.
SUMMARY = [
    "Stränderna på Falsterbonäset 2012 till 2026. De återges med verkliga data, inte i realtid.",
    "Stränderna växte ut mot havet i många år. Omkring 2012 stannade det, och efter stormen Babet i oktober 2023 backade dynerna kraftigt.",
    "SMHI:s havsvattenstånd vid Skanör och nederbörd vid Falsterbo A. Varje storm med högt vattenstånd står i loggen.",
    "Uppspelningen går en månad per sekund och visar inga satellitbanor eller vindpilar.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-falsterbo.geojson"
TARGETS_FILE = DATA / "osm" / "targets-falsterbo.geojson"
WEATHER_DIR = DATA / "smhi"
# No wind: over many years at a month a second the arrows would only flicker.
WIND_FILE = None
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
LANDSAT_DIR = DATA / "landsat"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2012-2026.json"
# SMHI's hourly sea level (tools/fetch_smhi_sea_level.py), shown as each day's highest (hydro.py).
SEA_LEVEL_DIR = DATA / "sea-level"
SEA_LEVEL_STATIONS = {"30488": "Skanör"}
SEA_LEVEL_STORM_CM = 100.0

# Ljunghusen's beach, between Falsterbo in the west and Kämpinge in the east (approximate).
FIRE_CENTRE = (55.393, 12.915)
FIRE_BBOX = (55.37, 55.43, 12.79, 12.99)  # min_lat, max_lat, min_lon, max_lon
# Map view: the peninsula from Falsterbo's point to Kämpinge and Höllviken.
VIEW_BBOX = (55.37, 55.45, 12.78, 13.00)
# The offline map, the DEM and the images (west, south, east, north), with Skanör's gauge and Falsterbo A.
MAP_BBOX = (12.76, 55.36, 13.02, 55.46)
PERIOD_START = date(2012, 1, 1)
PERIOD_END = date(2026, 10, 21)
PLAYBACK_START = datetime(2012, 1, 1, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc)
# A month a second: the 14 years in about three minutes, without slowing down at passes.
PLAYBACK_SPEED = 30 * 86400.0
SLOW_AT_PASSES = False
# Babet's peak at Skanör.
CHECK_START_UTC = "2023-10-21T00:00:00Z"

DATABASE = "falsterbo"
TILES_FILE = "falsterbo.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 13.5, "lat": 56, "height": 1_500_000, "pitch": -90, "seconds": 2.0},  # Southern Sweden
    {"lon": 12.9, "lat": 55.42, "height": 150_000, "pitch": -80, "seconds": 2.0},  # South-west Skåne
    {"lon": 12.88, "lat": 55.34, "height": 12_000, "pitch": -55, "seconds": 2.2},  # Falsterbonäset from the sea
]

# The flood's words for the land the radar's water is counted on and for the gauges.
FOCUS_LAND = "stränderna på Falsterbonäset"
RAIN_GAUGES = "SMHI:s mätare"
# SMHI's hourly rain (parameter 7) on the peninsula, checked 2026-10-26: Falsterbo A.
RAIN_STATIONS = {"52240": "Falsterbo A"}

# No satellite orbits; the images' satellites are shown where they were when they took them (step 5).
TLE_SATELLITES: dict = {}
TLE_START, TLE_END = "2012-01-01", "2026-10-21"
SATELLITE_ROLES: dict = {}
SATELLITE_LABEL = "Position beräknad ur banelement (SGP4) – inte en observation"

LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före", "during": "Under", "after": "Efter"}
LANDSAT_FOCUS_AREA = (12.79, 55.37, 12.99, 55.43)  # the peninsula's beaches
# About 30 m over MAP_BBOX: 0.26 degrees of longitude and 0.10 of latitude at 55.41 N.
LANDSAT_SIZE = (548, 371)

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "smhi": "SMHI öppna data (CC BY 4.0 SE): havsvattenstånd vid Skanör, nederbörd vid Falsterbo A",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
