"""Flooding in Sundsvall 2026: a scenario built on the real rain of 16-19 August 2026.

Decided 2026-10-06: the demo is a scenario, clearly marked as such, not a replayed
event; a flood in Sundsvall that day is not confirmed in open sources (see
reports/2026-10-06-datakallor-oversvamning-sundsvall-claude-opus-5-5.md). The rain
comes from Sundsvall municipality's own gauges in SMHI's open data. The user confirmed
on 2026-10-06 that the municipality's layers in bxkarta, among them its cloudburst
models, may be used in the demo (MUNICIPAL_WMS).

Its data live in the unversioned data/sundsvall2026/. The screens cannot run it yet:
the flood's own modules come in a later step; until then only the tools use it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "sundsvall2026"
# Whether the backend and the screens can run this scenario.
SCREENS_READY = False

TITLE = "Översvämning i Sundsvall 2026 – scenario"
DATA_LABEL = "Scenario byggt på verkligt regn augusti 2026 – inte en återgiven händelse"
CONTROL_LABEL = "Scenario: FLOOD – Sundsvall 2026, verkligt regn, scenario"

# The fire's FIRMS detections and forecast have no part in this scenario.
FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-sundsvall.geojson"
TARGETS_FILE = DATA / "osm" / "targets-sundsvall.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-sundsvall-2026.csv"
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
LANDSAT_DIR = DATA / "landsat"
SENTINEL2_DIR = DATA / "sentinel2"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2026.json"

# Sundsvall's centre, where the Selånger river meets the sea.
FIRE_CENTRE = (62.391, 17.307)
FIRE_BBOX = (62.28, 62.47, 17.0, 17.55)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town, the Selånger valley and the municipality's rain gauges around it.
VIEW_BBOX = (62.28, 62.47, 17.0, 17.55)
# The area of the offline map, the DEM and the satellite images (lon/lat, west, south, east,
# north), with every gauge used, from Bällsta in the west to Brämön A in the sea.
MAP_BBOX = (16.9, 62.15, 17.8, 62.62)
PERIOD_START = date(2026, 8, 14)
PERIOD_END = date(2026, 8, 22)
PLAYBACK_START = datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc)
# Sentinel-1C passes at 05:21 UTC on 16 August, before the heaviest rain at 08 UTC.
CHECK_START_UTC = "2026-08-16T05:00:00Z"

DATABASE = "sundsvall2026"
TILES_FILE = "sundsvall.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 16.5, "lat": 63, "height": 1_100_000, "pitch": -80, "seconds": 2.0},  # Sweden
    {"lon": 17.3, "lat": 62.2, "height": 160_000, "pitch": -60, "seconds": 2.2},  # Medelpad
]

# The rain gauges (SMHI parameter 7, hourly precipitation): the municipality's own and
# SMHI's Brämön A. Söråker (22228110) is left out: it gives implausible values.
RAIN_STATIONS = {
    "2222813": "Fillan", "2222814": "Heffners", "2222818": "Bredsand", "2222811": "Essvik",
    "2222812": "Bällsta", "2222819": "Stångom", "127130": "Brämön A",
}

# The satellites that imaged Sundsvall in the period (Planetary Computer catalogue, checked
# 2026-10-06) and the ISS, by NORAD number; element sets a few days around the playback.
TLE_SATELLITES = {
    "62261": "Sentinel-1C", "66315": "Sentinel-1D", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "60989": "Sentinel-2C", "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS",
}
TLE_START, TLE_END = "2026-08-10", "2026-08-24"
# half_swath_km: Sentinel-1 IW 250 km, Sentinel-2 MSI 290 km and Landsat OLI 185 km across.
SATELLITE_ROLES = {
    "62261": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": 125.0},
    "66315": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": 125.0},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "60989": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
}
SATELLITE_LABEL = "Position 2026, beräknad ur banelement (SGP4) – inte en observation"

# Landsat 8 scenes before and after the rain (tools/fetch_landsat_scene.py), over the town
# (LANDSAT_FOCUS_AREA): 13 July is cloud-free but covers 94 % of it, at the scene's edge;
# the August scenes before the rain (6 and 13 August) are 92-100 % cloud, 20 July 48 %.
# 21 August, after the rain, has 7.7 % cloud. None is clear during the rain.
LANDSAT_SCENES = {
    "before": "LC08_L2SP_193016_20260713_02_T1",
    "after": "LC08_L2SP_194016_20260821_02_T1",
}
LANDSAT_ROLES = {"before": "Före regnet", "during": "Under regnet", "after": "Efter regnet"}
# The town and the lower Selånger valley, for the coverage and cloud of each scene.
LANDSAT_FOCUS_AREA = (17.15, 62.33, 17.45, 62.45)
# About 30 m over MAP_BBOX: 0.9 degrees of longitude and 0.47 of latitude at 62.4 N.
LANDSAT_SIZE = (1546, 1742)
# Sentinel-2 (tools/fetch_sentinel2_scene.py): the clearest datatakes before and after the
# rain, by product name up to the relative orbit; 16 August is 98 % cloud. Over the town
# the scene classification gives 72 % cloud on 11 August and 37 % on 20 August.
SENTINEL2_SCENES = {
    "before": "S2C_MSIL2A_20260811T102601_R108",
    "after": "S2A_MSIL2A_20260820T101701_R065",
}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (2320, 2613)

# MCF's (formerly MSB's) overview flood maps: the 100-year and the highest calculated flow
# for Ljungan and Indalsälven; the Selånger river is not mapped there. No limitations on
# public access and no conditions according to the INSPIRE record; name MCF as the source.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": {"2": "100-årsflöde", "5": "Beräknat högsta flöde"},
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
}

# Sundsvall municipality's geoserver (the Origo map bxkarta), in EPSG:3006, 4326 and 3857.
# Its terms allow use only by five municipalities unless agreed; the user confirmed on
# 2026-10-06 that the demo may use it. Only the municipality's own layers: those of
# MSVAB, the county board and Lantmäteriet in the same service have other owners.
MUNICIPAL_WMS = {
    "url": "https://karta.sundsvall.se/geoserver/wms",
    "layers": {
        "SundsvallsKommun:Skyfallsmodell30_tiff": "Skyfallsmodell, 30-årsregn",
        "SundsvallsKommun:Skyfallsmodell100_tiff": "Skyfallsmodell, 100-årsregn",
        "SundsvallsKommun:Skyfallsmodell500_tiff": "Skyfallsmodell, 500-årsregn",
        "SundsvallsKommun:30-ar_maxvattendjup": "Största vattendjup, 30-årsregn",
        "SundsvallsKommun:100-ar_maxvattendjup": "Största vattendjup, 100-årsregn",
        "SundsvallsKommun:500-ar_maxvattendjup": "Största vattendjup, 500-årsregn",
        "SundsvallsKommun:30-ar_maxvattenhastighet": "Största strömhastighet, 30-årsregn",
        "SundsvallsKommun:100-ar_maxvattenhastighet": "Största strömhastighet, 100-årsregn",
        "SundsvallsKommun:500-ar_maxvattenhastighet": "Största strömhastighet, 500-årsregn",
        "SundsvallsKommun:Selangersan100ArsFlode2009_yta": "Selångersån, 100-årsflöde (2009)",
        "SundsvallsKommun:GATA_KritiskDagvatten_punkt": "Kritiska punkter för dagvatten",
        "SundsvallsKommun:td_hojdkurva_1m_linje": "Höjdkurvor, 1 m",
    },
    "attribution": "© Sundsvalls kommun",
}

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": "SMHI öppna data (CC BY 4.0 SE), Sundsvalls kommuns nederbördsmätare och Brämön A; senaste månaderna, ej kvalitetsgranskade",
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2026",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "sundsvall": "Skyfallsmodeller och kartlager © Sundsvalls kommun",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
