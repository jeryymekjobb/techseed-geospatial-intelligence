"""The coastal erosion on Falsterbonäset, 2012–2026.

Chosen 2026-10-26 from the feasibility study
reports/2026-10-26-forstudie-falsterbo-stranderosion-claude-opus-5-5.md: the long-term trend
rather than one storm. A 2026 LTH student thesis (Sennmark, TVVR26/5021) finds that the beaches'
growth seaward, seen in orthophotos since 1939, stopped round 2012 and turned sharply landward
after storm Babet (October 2023), and that by March 2026 about half the dune sand Babet took had
come back, most at Falsterbo and least at Kämpinge. SMHI's Skanör gauge gives the storm surges:
168.6 cm (RH2000) at storm Axel on 4 January 2017 and 149.5 cm at Babet on 21 October 2023.

Unlike the other floods this scenario spans many years: it starts at a month a second, does
not slow down at satellite passes and shows no satellite orbits or wind. It shows a clear satellite image
a year, Landsat 8 in 2013-2014 and Sentinel-2 from 2015, and one before and one after Babet. The
orthophotos (with a Geotorget account), each satellite's position when it took its image, SGU's
erosion layers, Copernicus Marine's waves and synthetic beach sensors are later steps of the study's plan.

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
    "En klar satellitbild varje år från 2013, Landsat 8 och sedan Sentinel-2, och en före och en efter Babet.",
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

# One clear image a year, mostly in late spring or summer, and the two round Babet; the maps show the
# latest up to the clock (landsat.py), so the series changes as the years play. Chosen 2026-10-26 from
# the Planetary Computer catalogue with less than 10 % cloud in the whole scene; the tools measure the
# beaches' own (0.0-2.9 %). 2014 takes row 194021 (15 % cloud in the whole scene, 1.8 % over the beaches), as
# row 194022 the same day covers only 19 % of them. 2012 has only Landsat 7, whose images have gaps (SLC-off),
# and is left out.
LANDSAT_SCENES = {
    "2013": "LC08_L2SP_195021_20130707_02_T1",
    "2014": "LC08_L2SP_194021_20140719_02_T1",
}
SENTINEL2_SCENES = {
    "2015": "S2A_MSIL2A_20150819T103026_R108",
    "2016": "S2A_MSIL2A_20160512T102032_R065",
    "2017": "S2A_MSIL2A_20170527T102031_R065",
    "2018": "S2A_MSIL2A_20180704T103021_R108",
    "2019": "S2A_MSIL2A_20190629T103031_R108",
    "2020": "S2B_MSIL2A_20200615T101559_R065",
    "2021": "S2A_MSIL2A_20210618T103021_R108",
    "2022": "S2A_MSIL2A_20220812T103031_R108",
    "before-babet": "S2B_MSIL2A_20230921T102649_R108",
    "after-babet": "S2B_MSIL2A_20231230T103349_R108",
    "2024": "S2B_MSIL2A_20240518T102559_R108",
    "2025": "S2A_MSIL2A_20250520T102701_R108",
    "2026": "S2A_MSIL2A_20260525T102701_R108",
}
LANDSAT_ROLES = {
    **{str(year): f"Årsbild {year}" for year in range(2013, 2027)},
    "before-babet": "Före Babet", "after-babet": "Efter Babet",
}
SENTINEL2_DIR = DATA / "sentinel2"
LANDSAT_FOCUS_AREA = (12.79, 55.37, 12.99, 55.43)  # the peninsula's beaches
# About 30 m over MAP_BBOX: 0.26 degrees of longitude and 0.10 of latitude at 55.41 N.
LANDSAT_SIZE = (548, 371)
# About 10 m over MAP_BBOX, Sentinel-2's own resolution, so the beaches stay sharp.
SENTINEL2_SIZE = (1644, 1112)

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "smhi": "SMHI öppna data (CC BY 4.0 SE): havsvattenstånd vid Skanör, nederbörd vid Falsterbo A",
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2015–2026",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
