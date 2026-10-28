"""Floods at Sundsvall in August 2023: the rain of the low Hans in the mountains and by the coast.

Decided 2026-10-28 after a meeting the user reported, where people who built embankments then
described one flood from rain in the mountains and one from local rain: this scenario is the
first of four (reports/2026-10-28-forstudie-sundsvall-2020-2021-claude-opus-5-5.md). In SMHI's
data the sea stood 76.7 cm RH2000 at Spikarna on 8 August, Sidsjö D had 48.0 mm on 10 August,
and Ljungan's peak came down from Lännässjön in the mountains (9 August) to Skallböle by
Sundsvall (449 m³/s on 14 August). The scenario replays these data; it is not live.

It shares sundsvall2026's map area, so its offline map, DEM, terrain, OSM layers, municipal
base map and flood areas are those in data/sundsvall2026/; its own data live in the unversioned
data/ljungan-aug2023/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "ljungan-aug2023"
# The map, terrain and OSM layers of sundsvall2026, over the same MAP_BBOX.
SHARED = REPO_ROOT / "data" / "sundsvall2026"

INCIDENT = "flood"
INCIDENT_PLACE = "Sundsvall"
INCIDENT_AREA = "Sundsvall och Ljungan"

TITLE = "Höga flöden i Ljungan och Sundsvall, augusti 2023"
DATA_LABEL = "Historiska data augusti 2023 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Ljungan och Sundsvall augusti 2023, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Lågtrycket Hans gav mycket regn i fjällen och vid kusten i augusti 2023. Det här är uppmätta data, inte i realtid.",
    "Havet vid Spikarna stod högt den 8 augusti, och vid Sidsjön föll 48 millimeter regn den 10 augusti.",
    "Flödet i Ljungan steg först i fjällen och nådde Sundsvall fem dygn senare, den 14 augusti.",
    "Regn och flöden från SMHI, SMHI:s väderradar och havsvattenståndet vid Spikarna. Flödena i Selångersån och Sidsjöbäcken är beräknade i SMHI:s modell, inte uppmätta.",
    "Radarbilder från Sentinel-1, som ser genom moln, och bilder från Sentinel-2 och Landsat 9.",
    "Bräddgivarna DV1–DV8 är simulerade och beräknade ur det verkliga regnet. Nivågivarna NG1–NG3 är simulerade och larmar när flödet de följer har fördubblats.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = SHARED / "osm" / "terrain-sundsvall.geojson"
TARGETS_FILE = SHARED / "osm" / "targets-sundsvall.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-ljungan-2023.csv"
# ERA5 over the sea, where ERA5-Land has no values (tools/fetch_era5_sea.py).
WIND_SEA_FILE = DATA / "era5-land" / "era5-sea-ljungan-2023.csv"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
# SMHI's weather radar as rain images (tools/fetch_smhi_radar.py).
RADAR_DIR = DATA / "radar"
DEM_DIR = SHARED / "dem"
TERRAIN_DIR = SHARED / "terrain"
LANDSAT_DIR = DATA / "landsat"
# MET Norway's archived weather forecasts, as issued (tools/fetch_met_forecasts.py, met_forecast.py).
MET_FORECAST_DIR = DATA / "met-forecast"
# SMHI's observed lightning (tools/fetch_smhi_lightning.py).
LIGHTNING_DIR = DATA / "lightning"
SENTINEL2_DIR = DATA / "sentinel2"
# The Sentinel-1 radar images of the acquisitions (tools/fetch_sentinel1_scene.py).
SENTINEL1_DIR = DATA / "sentinel1"
# The municipality's critical stormwater points and flood areas, and MCF's (shared). The synthetic
# overflow sensors DV1-DV8 of sundsvall2026 stand at the same points (flood_sensors.py), filled by 2023's rain.
MUNICIPAL_DIR = SHARED / "municipal"
MCF_DIR = SHARED / "mcf"
# Meteosat's cloud top height every 15 minutes and cloud mask every hour (MSG; MTG's lightning
# and instability start in 2024).
METEOSAT_CTH_FILE = DATA / "meteosat-cth" / "cth.json"
METEOSAT_CLM_FILE = DATA / "meteosat-clm" / "clm.json"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2023.json"
# Each image's satellite where it was when it took the image (tools/fetch_scene_elements.py).
SCENE_ELEMENTS_FILE = TLE_DIR / "scene-elements.json"

# SMHI's sea level at Spikarna (2061) outside Sundsvall, hourly in RH2000 (tools/fetch_smhi_sea_level.py).
SEA_LEVEL_DIR = DATA / "sea-level"
SEA_LEVEL_STATIONS = {"2061": "Spikarna"}
# No hourly value at Spikarna reached 100 cm in the period (76.7 cm on 8 August), so no storm lines.
SEA_LEVEL_STORM_CM = 100.0
# Thirteen days: the sea level by the hour. No forecast of it as issued in 2023 is archived (SMHI's
# NEMO-Nordic only in real time, Copernicus Marine's analyses), so, as the user chose on 2026-10-28, the
# screens mark the 72 hours after the clock as measured afterwards, not a forecast.
SEA_LEVEL_HOURLY = True
SEA_LEVEL_AHEAD_HOURS = 72

# Sundsvall's centre, where the Selånger river meets the sea.
FIRE_CENTRE = (62.391, 17.307)
FIRE_BBOX = (62.28, 62.47, 17.0, 17.55)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town, the Selånger valley and lower Ljungan with Matfors and Skallböle.
VIEW_BBOX = (62.28, 62.47, 16.9, 17.55)
# sundsvall2026's map area (lon/lat, west, south, east, north), which reaches Skallböle in the west.
MAP_BBOX = (16.9, 62.15, 17.8, 62.62)
PERIOD_START = date(2023, 8, 1)
PERIOD_END = date(2023, 8, 21)
# From before the rain to after Ljungan's peak and the clear images of 17 August.
PLAYBACK_START = datetime(2023, 8, 5, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2023, 8, 18, 0, 0, tzinfo=timezone.utc)
# Thirteen days at half an hour a second, slowing at the satellites' passes.
PLAYBACK_SPEED = 1800.0
# The sea's highest at Spikarna, 76.7 cm at 15 UTC on 8 August.
CHECK_START_UTC = "2023-08-08T12:00:00Z"

DATABASE = "ljungan-aug2023"
TILES_FILE = "sundsvall.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 15.5, "lat": 62.6, "height": 900_000, "pitch": -75, "seconds": 2.0},  # Ljungan from the mountains
    {"lon": 17.2, "lat": 62.2, "height": 160_000, "pitch": -60, "seconds": 2.2},  # Medelpad
]

FOCUS_LAND = "stans land"
RAIN_GAUGES = "kommunens mätare"
# The rain gauges (SMHI parameter 7, hourly precipitation): the municipality's own, all measuring in
# 2023 (Bredsand from April 2023), and SMHI's Brämön A. Söråker (22228110) gives implausible values.
RAIN_STATIONS = {
    "2222813": "Fillan", "2222814": "Heffners", "2222818": "Bredsand", "2222811": "Essvik",
    "2222812": "Bällsta", "2222819": "Stångom", "127130": "Brämön A",
}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC) by the town; the flood's
# assessment counts them, so the mountains' stations are not among them. Sidsjö D lies by the dam.
DAILY_RAIN_STATIONS = {"127220": "Sidsjö D", "127320": "Stordalen-Midlanda D"}
DAILY_RAIN_DIR = DATA / "smhi-daily"
# SMHI's flow stations along Ljungan, from the mountains to Sundsvall ("station:parameter"): every
# 15 minutes (parameter 2) where SMHI has it for 2023, else by the day (parameter 1). Only
# Skallböle lies on the map; the others are in the panel's chart and the log.
HYDRO_STATIONS = {
    "20035:1": "Lännässjön (fjällen)",
    "20036:2": "Östavallselet",
    "1471:1": "Torpshammar",
    "1650:2": "Skallböle",
}

# SMHI's modelled daily flows (S-HYPE) by SUBID, from Vattenwebb's files downloaded by hand into
# MODEL_FLOW_DIR/raw/ (tools/read_vattenwebb.py): the Selånger river at its outlet in the sea (449 km²)
# and Sidsjöbäcken (27 km²), which have no SMHI station.
MODEL_FLOW_DIR = DATA / "s-hype"
MODEL_FLOW_STATIONS = {"12849": "Selångersån", "12794": "Sidsjöbäcken"}

# EFAS's flow forecasts as issued (tools/fetch_efas_forecasts.py, efas.py), as the user chose on 2026-10-28 after
# a check: ECMWF's high-resolution run at 00 UTC on 5-14 August, 1-10 days ahead, on EFAS's grid of about 5 km.
# The run of 9 August gave Skallböle its peak at once (459 m³/s) and falling flows, while the measured flow rose
# to 449 m³/s on 13 August: Ljungan's lakes and reservoirs hold the water back longer than the model. Skallböle
# comes first, for the log; Sidsjöbäcken is too small for the grid.
EFAS_DIR = DATA / "efas"
EFAS_STATIONS = ["1650:2", "1471:1", "20036:2", "20035:1", "model-12849"]
EFAS_ISSUES = (date(2023, 8, 5), date(2023, 8, 14))
EFAS_AREA = (62.8, 13.5, 62.1, 17.7)

# Three synthetic level sensors (level_sensors.py; tools/derive_impact_sensor_points.py, the `level-sensors`
# step of fetch_scenario), each following its nearest flow station: Öhns Campingplats in Matfors by Ljungan,
# where SVT reported water on 15 August 2023 (OSM's camp site; Skallböle), Himlabadet by Sidsjöbäcken (OSM's
# building; Sidsjöbäcken, computed) and the Selånger river's outlet (S-HYPE's outlet point; computed). No
# station passed its record and the computed flows stayed below the 2-year flow, so, as the user chose on
# 2026-10-28, they alarm when their station's flow is twice its flow at the playback's start: Himlabadet
# 10-13 August, the outlet 8-16 August, Öhns camping from 20 UTC on 11 August to 15 August.
LEVEL_SENSOR_SITES = [
    {"site": "Öhns camping, Matfors", "latitude": 62.32671, "longitude": 17.05924, "source_label": "SVT 15 augusti 2023 (vatten vid campingen)"},
    {"site": "Himlabadet, Sidsjöbäcken", "latitude": 62.39404, "longitude": 17.28916, "source_label": "Syntetisk plats vid Sidsjöbäcken"},
    {"site": "Selångersåns utlopp", "latitude": 62.39309, "longitude": 17.3151, "source_label": "Syntetisk plats vid S-HYPE:s utloppspunkt"},
]
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
LEVEL_ALARM_RISE = 2.0
# The overflow sensors DV1-DV8 stay beside the level sensors (level_sensors.BothSensors), as the user chose.
OVERFLOW_WITH_LEVEL_SENSORS = True
SENSOR_WORDS = {"sensors": "givare", "the_sensors": "givarna", "alarming": "larmande"}

# Sidsjödammen as a marked "if", as the user chose on 2026-10-28: no open dam-break mapping exists and
# one may be classified. When NG2 Himlabadet alarms (Sidsjöbäcken's flow doubled, 10 August), the log
# says how many buildings lie within 100 m of Sidsjöbäcken below the dam (OSM's dam line, waterway=dam)
# and marks the dam and Himlabadet, where the user's meeting reported water, about 360 m from the
# stream (tools/derive_dam_exposure.py). The municipality's cloudburst plan (2018) names a dam failure
# there "katastrofala konsekvenser för nedströms bebyggelse".
DAM = {
    "name": "Sidsjödammen", "latitude": 62.3796, "longitude": 17.2823, "stream": "Sidsjöbäcken", "distance_m": 100,
    "places": [{"name": "Himlabadet", "latitude": 62.39404, "longitude": 17.28916}],
    "trigger_sensor": "ng-02", "osm_extract": REPO_ROOT / "data" / "osm" / "sundsvall2026-area.osm.pbf",
}
DAM_FILE = DATA / "dam" / "dam.json"

# The satellites that imaged Sundsvall in the period (Planetary Computer catalogue, checked
# 2026-10-28; Sentinel-1B ended in December 2021) and the ISS, by NORAD number; element sets
# a few days around the playback.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS", "38552": "Meteosat-10", "40732": "Meteosat-11",
}
TLE_START, TLE_END = "2023-07-28", "2023-08-21"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
    # The MSG satellite at 0 degrees whose cloud mask and cloud tops the demo shows (meteosat_clm.py, meteosat_cth.py).
    "38552": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
    "40732": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
}
SATELLITE_LABEL = "Position 2023, beräknad ur banelement (SGP4) – inte en observation"

# Landsat 9 before the heaviest rain and at Ljungan's peak (tools/fetch_landsat_scene.py), over the
# town (LANDSAT_FOCUS_AREA); scene cloud 16 % on 5 August and 23 % on 14 August (97 % of the town).
LANDSAT_SCENES = {
    "before": "LC09_L2SP_194016_20230805_02_T1",
    "during": "LC09_L2SP_193016_20230814_02_T1",
}
LANDSAT_ROLES = {"before": "Före regnet", "during": "Ljungans topp", "after": "Efter regnet"}
# The town and the lower Selånger valley, for the coverage and cloud of each scene.
LANDSAT_FOCUS_AREA = (17.15, 62.33, 17.45, 62.45)
# About 30 m over MAP_BBOX: 0.9 degrees of longitude and 0.47 of latitude at 62.4 N.
LANDSAT_SIZE = (1546, 1742)
# Sentinel-1A's passes over the town in the playback that cover at least 90 % of it (Planetary
# Computer catalogue, sentinel-1-grd, checked 2026-10-28; the start of each pass's product). The
# image of 9 August 05:06 covers only 57 % of the town and is left out.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2023-08-07T05:22:59Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2023-08-14T05:14:50Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2023-08-14T16:30:50Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py), by product name up to the relative orbit: before
# the rain (scene cloud 26 %), at Ljungan's peak (14 %) and after it (1.5 %); 2-9 August are 40-99 %.
SENTINEL2_SCENES = {
    "before": "S2B_MSIL2A_20230730T101609_R065",
    "during": "S2A_MSIL2A_20230814T102031_R065",
    "after": "S2A_MSIL2A_20230817T103031_R108",
}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (2320, 2613)

# MCF's overview flood maps: the 100-year and the highest calculated flow for Ljungan and
# Indalsälven, as in sundsvall2026; name MCF as the source.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": {"13": "100-årsflöde", "9": "Beräknat högsta flöde"},
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
}

# Sundsvall municipality's geoserver, which the user confirmed on 2026-10-06 the demo may use.
MUNICIPAL_WMS = {
    "url": "https://karta.sundsvall.se/geoserver/wms",
    "layers": {
        "SundsvallsKommun:Skyfallsmodell100_tiff": "Skyfallsmodell, 100-årsregn",
        "SundsvallsKommun:100-ar_maxvattendjup": "Största vattendjup, 100-årsregn",
        "SundsvallsKommun:Selangersan100ArsFlode2009_yta": "Selångersån, 100-årsflöde (2009)",
        "SundsvallsKommun:GATA_KritiskDagvatten_punkt": "Kritiska punkter för dagvatten",
    },
    "attribution": "© Sundsvalls kommun",
    "visible": [],
}

# The municipality's own map, kept locally for sundsvall2026 (the user confirmed on 2026-10-14).
MUNICIPAL_BASEMAP = {
    "url": "https://karta.sundsvall.se/geoserver/wms",
    "layer": "Kartan",
    "label": "Sundsvalls kommun (Kartan)",
    "attribution": "Karta © Sundsvalls kommun, Lantmäteriet, Trafikverket",
}
MUNICIPAL_BASEMAP_DIR = SHARED / "municipal-basemap"

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = ("PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors, 100-årsflöden © Sundsvalls kommun "
                  "och MCF (tidigare MSB)")

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": ("SMHI öppna data (CC BY 4.0 SE): nederbörd vid kommunens mätare, Brämön A, Sidsjö D och Stordalen-Midlanda D, "
             "väderradar, vattenföring i Ljungan och havsvattenstånd vid Spikarna; modellerad vattenföring (S-HYPE) i Vattenwebb"),
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2023",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land och ERA5 över havet), CC BY 4.0",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "efas": "Innehåller bearbetad information från Copernicus Emergency Management Service 2023 (EFAS)",
    "sundsvall": "Skyfallsmodeller och kartlager © Sundsvalls kommun",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
