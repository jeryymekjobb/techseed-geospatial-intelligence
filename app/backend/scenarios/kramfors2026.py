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
    "Radarbilder från Sentinel-1 före och efter skyfallet, och bilder från Sentinel-2 och Landsat före och efter.",
    "Översvämmade vägar, en vattenfylld källare och ett tågstopp, enligt lokala medier. Platserna är ungefärliga.",
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
SENTINEL2_DIR = DATA / "sentinel2"
SENTINEL1_DIR = DATA / "sentinel1"
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

# The satellites over the area in the period and the ISS, by NORAD number.
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

# Landsat 8 before and after (tools/fetch_landsat_scene.py; catalogue cloud 50 % and 17 %, checked 2026-10-16).
LANDSAT_SCENES = {"before": "LC08_L2SP_195016_20260812_02_T1", "after": "LC08_L2SP_194016_20260821_02_T1"}
LANDSAT_ROLES = {"before": "Före skyfallet", "during": "Under skyfallet", "after": "Efter skyfallet"}
LANDSAT_FOCUS_AREA = (17.7, 62.9, 17.85, 62.97)  # Kramfors town
# About 30 m over MAP_BBOX: 1.1 degrees of longitude and 0.6 of latitude at 62.9 N.
LANDSAT_SIZE = (1859, 2224)
# Sentinel-1 acquisitions over the town (Planetary Computer catalogue, sentinel-1-grd, checked
# 2026-10-16): 10 August on the same descending track as 16 August, about ten hours after the rain,
# and the next day's two passes.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2026-08-10T05:21:45Z", "satellite": "Sentinel-1D", "norad": "66315"},
    {"time_utc": "2026-08-16T05:21:32Z", "satellite": "Sentinel-1C", "norad": "62261"},
    {"time_utc": "2026-08-17T05:13:33Z", "satellite": "Sentinel-1D", "norad": "66315"},
    {"time_utc": "2026-08-17T16:29:45Z", "satellite": "Sentinel-1D", "norad": "66315"},
]
# Sentinel-2 before and after (catalogue tile cloud 17-19 % and 12-15 %); 16 August is 99 % cloud.
SENTINEL2_SCENES = {
    "before": "S2C_MSIL2A_20260808T101601_R065",
    "after": "S2A_MSIL2A_20260820T101701_R065",
}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (2789, 3336)

# The damage local media reported (routes.py): times and places approximate. Tidningen Ångermanland
# is partly behind a paywall, so its details are only partly checked. The track fault on 17 August
# has no place in the reports and shows in the log only.
ROUTE_REPORT = "Lokala medier: Tidningen Ångermanland, Sveriges Radio P4 Västernorrland, SVT Västernorrland"
ROUTE_IMPACT_LABEL = "Översvämmade vägar och järnväg (rapporterat)"
ROUTE_SOURCE_LABEL = "lokala medier"
ROUTE_ATTRIBUTION = "Tidningen Ångermanland, Sveriges Radio P4 Västernorrland, SVT"
ROUTE_IMPACTS = [
    {"time_utc": "2026-08-15T16:00:00Z", "kind": "alert", "approximate_time": False, "source_label": "SMHI, via SVT",
     "text": "SMHI:s gula varning för skyfallsliknande regn gäller från klockan 18"},
    {"time_utc": "2026-08-16T06:00:00Z", "kind": "road", "approximate_time": True, "site": "Väg 855",
     "latitude": 62.96353, "longitude": 17.86098, "source_label": "Tidningen Ångermanland",
     "text": "Väg 855 avstängd av Trafikverket efter skyfallet"},
    {"time_utc": "2026-08-16T06:00:00Z", "kind": "road", "approximate_time": True, "site": "Väg 856 Butjärn",
     "latitude": 62.96765, "longitude": 17.93559, "source_label": "Tidningen Ångermanland",
     "text": "Väg 856 mellan Strinne och Finnkåtorna med mycket vatten på vägen"},
    {"time_utc": "2026-08-16T06:00:00Z", "kind": "road", "approximate_time": True, "site": "Ådalshallen",
     "latitude": 62.93042, "longitude": 17.78364, "source_label": "Tidningen Ångermanland",
     "text": "Vatten i Ådalshallens källare, räddningstjänsten länspumpar"},
    {"time_utc": "2026-08-16T06:00:00Z", "kind": "road", "approximate_time": True, "site": "Väg vid Saltsjön",
     "latitude": 62.99684, "longitude": 17.9873, "source_label": "Tidningen Ångermanland",
     "text": "En enskild väg vid Saltsjön raseras"},
    {"time_utc": "2026-08-17T05:00:00Z", "kind": "rail", "approximate_time": True, "source_label": "Sveriges Radio P4",
     "text": "Spårfel efter översvämning på banvallen stoppar tågen mellan Sundsvall och Umeå"},
    {"time_utc": "2026-08-17T22:00:00Z", "kind": "rail", "approximate_time": True, "source_label": "Sveriges Radio P4",
     "text": "Tågtrafiken mellan Sundsvall och Umeå i gång igen"},
]
# The OSM roads and railways under heavy rain, computed from SMHI's radar (tools/derive_route_exposure.py).
ROUTE_EXPOSURE_FILE = DATA / "routes" / "exposure.json"
# Synthetic overflow sensors at the reported damage with a place (ROUTE_IMPACTS with a "site"), each
# filled by the rain SMHI's radar estimates there (tools/derive_radar_sensor_points.py), since both
# hourly gauges lie outside the cell.
RADAR_SENSOR_FILE = DATA / "sensors" / "radar-points.geojson"

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
