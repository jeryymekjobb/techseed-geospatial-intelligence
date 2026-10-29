"""The flood of Svartån in Västerås in September 2023.

Decided 2026-10-28 from the feasibility study reports/2026-10-28-forstudie-vasteras-claude-opus-5-5.md.
After a wet August (254 mm at Skultuna) it rained heavily in the night to 2 September; SMHI's
Åkesta kvarn above the town measured 56.4 m³/s that day as a daily mean, the highest since 1980
(42.9 m³/s in 1983). On Saturday 2 September about sixty cottages in Biskopsängen stood under
water and the city built embankments to protect the city hall (SVT, TV4). Like flen2019 this is
a replayed event with real data, not a scenario.

The user confirmed on 2026-10-28 that Techseed may use Västerås stad's data internally; no
public showings are planned. Its data live in the unversioned data/vasteras-sep2023/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "vasteras-sep2023"

INCIDENT = "flood"
INCIDENT_PLACE = "Västerås"
INCIDENT_AREA = "Svartån i Västerås"

TITLE = "Svartån i Västerås, september 2023"
DATA_LABEL = "Historiska data september 2023 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Svartån i Västerås september 2023, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Svartån i Västerås i september 2023. Det här är uppmätta data, inte i realtid.",
    "Efter en blöt augusti regnade det kraftigt natten till den 2 september. Svartån fick det högsta flödet sedan mätningarna började 1980.",
    "Ett sextiotal fritidshus i Biskopsängen stod under vatten, och staden byggde vallar vid stadshuset.",
    "Regn och flöden från SMHI och SMHI:s väderradar. Stadens skyfallskartering och MCF:s översvämningskartering av Svartån.",
    "Radarbilder från Sentinel-1, som ser genom moln, och bilder från Sentinel-2 och Landsat 9 efter regnet.",
    "Nivågivarna är simulerade. De står vid Biskopsängen, stadshuset och Svartåns mynning och följer SMHI:s station vid Åkesta kvarn.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = DATA / "osm" / "terrain-vasteras.geojson"
TARGETS_FILE = DATA / "osm" / "targets-vasteras.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-vasteras-2023.csv"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
# SMHI's weather radar as rain images (tools/fetch_smhi_radar.py).
RADAR_DIR = DATA / "radar"
DEM_DIR = DATA / "dem"
TERRAIN_DIR = DATA / "terrain"
LANDSAT_DIR = DATA / "landsat"
# MET Norway's archived weather forecasts, as issued (tools/fetch_met_forecasts.py, met_forecast.py).
MET_FORECAST_DIR = DATA / "met-forecast"
# SMHI's observed lightning (tools/fetch_smhi_lightning.py).
LIGHTNING_DIR = DATA / "lightning"
SENTINEL2_DIR = DATA / "sentinel2"
# The Sentinel-1 radar images of the acquisitions (tools/fetch_sentinel1_scene.py).
SENTINEL1_DIR = DATA / "sentinel1"
MCF_DIR = DATA / "mcf"
# Meteosat's cloud top height every 15 minutes and cloud mask every hour (MSG; MTG's lightning
# and instability start in 2024).
METEOSAT_CTH_FILE = DATA / "meteosat-cth" / "cth.json"
METEOSAT_CLM_FILE = DATA / "meteosat-clm" / "clm.json"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2023.json"
# Each image's satellite where it was when it took the image (tools/fetch_scene_elements.py).
SCENE_ELEMENTS_FILE = TLE_DIR / "scene-elements.json"

# The city hall by Svartån, in the town's centre.
FIRE_CENTRE = (59.6085, 16.5473)
FIRE_BBOX = (59.58, 59.70, 16.40, 16.65)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town and Svartån from Åkesta kvarn to Mälaren.
VIEW_BBOX = (59.58, 59.70, 16.40, 16.65)
# The offline map, the DEM and the satellite images (west, south, east, north): the town, Svartån from
# Skultuna to Mälaren, and SMHI's stations at Berg (Kolbäcksån) and Gränvad (Sagån) to the west and east.
MAP_BBOX = (16.10, 59.50, 16.90, 59.80)
# Åkesta kvarn's present number (2773) measures every 15 minutes from 15 UTC on 29 August 2023.
PERIOD_START = date(2023, 8, 29)
PERIOD_END = date(2023, 9, 8)
# From before the rain to after Sentinel-1's pass on the morning of 7 September.
PLAYBACK_START = datetime(2023, 8, 30, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2023, 9, 7, 12, 0, tzinfo=timezone.utc)
# Eight and a half days at half an hour a second, slowing at the satellites' passes.
PLAYBACK_SPEED = 1800.0
# Sentinel-1A passes at 05:07 UTC on 2 September, the day of the peak.
CHECK_START_UTC = "2023-09-02T05:00:00Z"
# The demo check: at noon on 2 September all three level sensors alarm (Åkesta kvarn above its record from
# 02 UTC) and the assessment says "Flood probable" ("Possible flood" at 05:30). Its SATCOM outage starts in
# the evening before the radar acquisition at 05:15 UTC on 7 September.
CHECK_PEAK_UTC = "2023-09-02T12:00:00Z"
CHECK_SENSORS = "3/3"
CHECK_OUTCOME = "Flood probable"
CHECK_SATCOM_UTC = "2023-09-06T21:00:00Z"

DATABASE = "vasteras-sep2023"
TILES_FILE = "vasteras.mbtiles"

CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 59, "height": 3_000_000, "pitch": -90, "seconds": 2.0},   # Southern Scandinavia
    {"lon": 16.5, "lat": 59.7, "height": 400_000, "pitch": -80, "seconds": 2.0},  # Mälardalen
    {"lon": 16.55, "lat": 59.54, "height": 25_000, "pitch": -60, "seconds": 2.2},  # Västerås
]

# The flood's words for the land the radar's water is counted on and for the gauges.
FOCUS_LAND = "marken runt Västerås"
RAIN_GAUGES = "SMHI:s mätare"
# SMHI's hourly rain (parameter 7), checked 2026-10-28: none in the map area in 2023; the nearest is
# Eskilstuna A, 28 km south across Mälaren. SMHI's radar gives the hourly rain over the town.
RAIN_STATIONS = {"96190": "Eskilstuna A"}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC) in the map area, checked
# 2026-10-28 (tools/fetch_smhi_daily.py, daily_rain.py): Skultuna had 59.7 mm on 1 September.
DAILY_RAIN_STATIONS = {"96350": "Västerås", "96440": "Skultuna", "96390": "Hallstaberg"}
DAILY_RAIN_DIR = DATA / "smhi-daily"
# The rain chart starts at Västerås's daily rain: Eskilstuna A had 0.5 mm on 31 August - 3 September.
RAIN_CHART_STATION = "daily-96350"
# SMHI's flow stations ("station:parameter"), every 15 minutes, checked 2026-10-28: Svartån at Åkesta
# kvarn above the town, Kolbäcksån at Berg and Sagån at Gränvad.
HYDRO_STATIONS = {
    "2773:2": "Åkesta kvarn (Svartån)",
    "2218:2": "Berg (Kolbäcksån)",
    "2217:2": "Gränvad (Sagån)",
}
# Åkesta kvarn was 2216 until November 2021 and 2771 until 29 August 2023; its record (42.9 m³/s in
# 1983) lies in 2216's daily flows.
HYDRO_EARLIER_STATIONS = {"2773:2": ("2771", "2216")}

# The satellites that imaged Västerås in the period (Planetary Computer catalogue, checked
# 2026-10-28) and the ISS, by NORAD number; element sets a few days around the playback.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "39084": "Landsat 8", "49260": "Landsat 9", "25544": "ISS", "38552": "Meteosat-10", "40732": "Meteosat-11",
}
TLE_START, TLE_END = "2023-08-26", "2023-09-10"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
    # The MSG satellites at 0 degrees whose cloud mask and cloud tops the demo shows (meteosat_clm.py, meteosat_cth.py).
    "38552": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
    "40732": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
}
SATELLITE_LABEL = "Position 2023, beräknad ur banelement (SGP4) – inte en observation"

# Landsat 9 after the rain (tools/fetch_landsat_scene.py), scene cloud 4.7 %; 29-30 August are 59-77 %.
LANDSAT_SCENES = {"after": "LC09_L2SP_194018_20230906_02_T1"}
LANDSAT_ROLES = {"before": "Före regnet", "during": "Under de höga flödena", "after": "Efter regnet"}
# The town, for the coverage and cloud of each scene.
LANDSAT_FOCUS_AREA = (16.45, 59.58, 16.62, 59.66)
# About 30 m over MAP_BBOX: 0.8 degrees of longitude and 0.3 of latitude at 59.65 N.
LANDSAT_SIZE = (1500, 1113)
# Sentinel-1A's passes in the playback (Planetary Computer catalogue, sentinel-1-grd, checked
# 2026-10-28; the start of each pass's product): before the rain, on the morning of the peak, and after.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2023-08-31T05:23:50Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2023-09-02T05:07:30Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2023-09-07T05:15:41Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py), by product name up to the relative orbit: before the
# rain (scene cloud 28 %) and after it (2 %); 1 and 3 September are 97-100 %.
SENTINEL2_SCENES = {
    "before": "S2A_MSIL2A_20230831T100601_R022",
    "after": "S2B_MSIL2A_20230905T100559_R022",
}
# About 20 m over MAP_BBOX.
SENTINEL2_SIZE = (2250, 1670)

# What SVT and TV4 reported on Saturday 2 September 2023. The reports give the morning but no time,
# so the times are approximate; the places are OSM's Biskopsängen (allotments) and city hall.
ROUTE_REPORT = "SVT och TV4 2 september 2023"
ROUTE_IMPACT_LABEL = "Översvämmat enligt medierna"
ROUTE_SOURCE_LABEL = "lokala medier"
ROUTE_ATTRIBUTION = "SVT och TV4"
ROUTE_IMPACTS = [
    {"time_utc": "2023-09-02T06:00:00Z", "kind": "alert", "approximate_time": True, "source_label": "SMHI, via SVT",
     "text": "SMHI varnar för höga flöden i Svartån (röd varning)"},
    {"time_utc": "2023-09-02T06:00:00Z", "kind": "road", "approximate_time": True, "site": "Biskopsängen",
     "latitude": 59.6258, "longitude": 16.5178, "source_label": "SVT",
     "text": "Ett sextiotal fritidshus i Biskopsängen står under vatten"},
    {"time_utc": "2023-09-02T10:00:00Z", "kind": "road", "approximate_time": True, "site": "Stadshuset",
     "latitude": 59.6085, "longitude": 16.5473, "source_label": "SVT och TV4",
     "text": "Staden bygger vallar för att skydda stadshuset mot Svartån"},
]
# Synthetic level sensors at the places above and at Svartån's outlet in Mälaren (the southern end of
# OSM's river in the scenario's extract, checked 2026-10-28), each
# following Åkesta kvarn (tools/derive_impact_sensor_points.py, level_sensors.py). They alarm when its
# flow is above its record (42.9 m³/s, 1983).
LEVEL_SENSOR_SITES = [
    {"site": "Svartåns mynning", "latitude": 59.6032, "longitude": 16.5474, "source_label": "Syntetisk plats vid Svartåns mynning"},
]
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
SENSOR_WORDS = {"sensors": "nivågivare", "the_sensors": "nivågivarna", "alarming": "larmande"}

# MCF's flood mapping of Svartån in Västerås (2025): the climate-adapted 100- and 200-year flows and
# the highest calculated flow (checked 2026-10-28; the plain 100-year layer has none there).
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": {"12": "100-årsflöde, klimatanpassat (slutet av seklet)", "11": "200-årsflöde, klimatanpassat (slutet av seklet)",
               "9": "Beräknat högsta flöde"},
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
    "visible": [],
}
# The same layers for PostGIS (tools/fetch_mcf_flood_maps.py): REST id, title and label.
MCF_LAYERS = {
    "100ar": (3, "100-årsflöde (Klimatanpassat flöde för slutet av seklet)", "MCF, klimatanpassat"),
    "bhf": (5, "Beräknat högsta flöde", "MCF"),
}
FLOOD_AREA_WORD = "det klimatanpassade 100-årsflödet"
FLOOD_MODELS = "MCF:s modell för slutet av seklet"

# Västerås stad's cloudburst mapping (ArcGIS Server, WMS in EPSG:4326), which Techseed may use
# internally (the user, 2026-10-28).
MUNICIPAL_WMS = {
    "url": "https://kartor.vasteras.se/arcgis/services/ext/sk_skyfall_wms/MapServer/WMSServer",
    "layers": {
        "1": "Största vattendjup, 100-årsregn",
        "0": "Största ytvattenflöde (l/s/m)",
    },
    "attribution": "© Västerås stad",
    "visible": [],
}

# Västerås stad's background maps of its Origo maps (GeoServer bakgrundskartor, WMS in EPSG:3857), kept
# locally like Sundsvall's Kartan, as the user chose on 2026-10-28; internal use only. The map's name
# (topowebbkartan) suggests Lantmäteriet's Topografisk webbkarta under the city's own layers.
_BASEMAP_WMS = "https://kartserver.vasteras.se/geoserver/wms"
_BASEMAP_PERMISSION = "The user confirmed on 2026-10-28 that Techseed may use Västerås stad's data internally; no public showings."
MUNICIPAL_BASEMAPS = [
    {"id": "vasteraskarta", "url": _BASEMAP_WMS, "layer": "bakgrundskartor:topowebbkartan", "label": "Västerås stad (karta)",
     "attribution": "Karta © Västerås stad, Lantmäteriet", "dir": DATA / "municipal-basemap" / "karta",
     "permission": _BASEMAP_PERMISSION, "note": "Västerås stad's colour map (topowebbkartan) from its Origo maps."},
    {"id": "vasterasgra", "url": _BASEMAP_WMS, "layer": "bakgrundskartor:topowebbkartan_nedtonad", "label": "Västerås stad (grå karta)",
     "attribution": "Karta © Västerås stad, Lantmäteriet", "dir": DATA / "municipal-basemap" / "gra",
     "permission": _BASEMAP_PERMISSION, "note": "Västerås stad's grey map (topowebbkartan_nedtonad) from its Origo maps."},
    {"id": "vasterasflygfoto", "url": _BASEMAP_WMS, "layer": "bakgrundskartor:Ortofoto_016", "label": "Västerås stad (flygfoto)",
     "attribution": "Flygfoto © Västerås stad", "dir": DATA / "municipal-basemap" / "flygfoto", "names": False,
     "permission": _BASEMAP_PERMISSION, "note": "Västerås stad's aerial photo (Ortofoto_016, 0.16 m) from its Origo maps; not of September 2023."},
]

FORECAST_WEATHER_FILES: list = []
FORECAST_METHOD = ""
FORECAST_REPORT = ""
SPATIAL_SOURCE = "PostGIS (lokal databas): OSM-mål © OpenStreetMap contributors, översvämningsytor © MCF (tidigare MSB)"

ATTRIBUTION = {
    "osm": "© OpenStreetMap contributors (ODbL)",
    "lantmateriet": "© Lantmäteriet",
    "smhi": ("SMHI öppna data (CC BY 4.0 SE): nederbörd vid Eskilstuna A, Västerås, Skultuna och Hallstaberg, "
             "väderradar och vattenföring vid Åkesta kvarn, Berg och Gränvad"),
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2023",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land), CC BY 4.0",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "vasteras": "Skyfallskartering © Västerås stad",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
