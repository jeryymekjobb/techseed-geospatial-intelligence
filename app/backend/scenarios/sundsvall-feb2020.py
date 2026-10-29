"""High sea and rain on snow at Sundsvall on 20-23 February 2020.

Decided 2026-10-29 from the study reports/2026-10-28-forstudie-sundsvall-2020-2021-claude-opus-5-5.md,
whose targeted searches of the press found this event: Sundsvalls Tidning wrote on 22 February 2020 of
"spöregn följt av snöväder" in Medelpad and of SMHI's class 1 warning for a high sea level in the northern
Bothnian Sea, 80-100 cm above the year's mean, updated that morning, with pictures of the Selånger river.
No damage is documented. In SMHI's data the sea stood 97.7 cm RH2000 at Spikarna at 15 UTC on 22 February,
the highest of 2020, and Sidsjö D had 5.0 mm on 20 February and 12.9 mm on 22 February at 3-6 °C. The
flows stayed low. The scenario replays these data; it is not live.
It shares sundsvall2026's map area, so its offline map, DEM, terrain, OSM layers, municipal
base map and flood areas are those in data/sundsvall2026/; its own data live in the unversioned
data/sundsvall-feb2020/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "sundsvall-feb2020"
# The map, terrain and OSM layers of sundsvall2026, over the same MAP_BBOX.
SHARED = REPO_ROOT / "data" / "sundsvall2026"

INCIDENT = "flood"
INCIDENT_PLACE = "Sundsvall"
INCIDENT_AREA = "Sundsvall"
TITLE = "Högt hav och regn på snö i Sundsvall, februari 2020"
DATA_LABEL = "Historiska data februari 2020 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Sundsvall februari 2020, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Högt hav och regn på snö i Sundsvall i februari 2020. Det här är uppmätta data, inte i realtid.",
    "Havet vid Spikarna nådde 98 centimeter den 22 februari, årets högsta. SMHI varnade för högt vattenstånd.",
    "Det regnade på snön i plusgrader, men flödena i åarna förblev låga.",
    "Regn och flöden från SMHI, SMHI:s väderradar och havsvattenståndet vid Spikarna. Flödena i Selångersån och Sidsjöbäcken är beräknade i SMHI:s modell, inte uppmätta.",
    "Radarbilder från Sentinel-1, som ser genom moln, och bilder från Sentinel-2 och Landsat 8 efter ovädret.",
    "Nivågivarna vid hamnen är simulerade. De följer havet vid Spikarna och larmar vid 81 centimeter, den nedre gränsen i SMHI:s varning.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = SHARED / "osm" / "terrain-sundsvall.geojson"
TARGETS_FILE = SHARED / "osm" / "targets-sundsvall.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-sundsvall-feb2020.csv"
# ERA5 over the sea, where ERA5-Land has no values (tools/fetch_era5_sea.py).
WIND_SEA_FILE = DATA / "era5-land" / "era5-sea-sundsvall-feb2020.csv"
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
# The municipality's critical stormwater points and flood areas, and MCF's (shared). The municipality's
# rain gauges started in March-April 2020, so there is no rain by the town to fill the overflow sensors
# DV1-DV8 with, and the scenario has none (OVERFLOW_SENSORS).
MUNICIPAL_DIR = SHARED / "municipal"
MCF_DIR = SHARED / "mcf"
OVERFLOW_SENSORS = False
# Meteosat's cloud top height every 15 minutes and cloud mask every hour (MSG).
METEOSAT_CTH_FILE = DATA / "meteosat-cth" / "cth.json"
METEOSAT_CLM_FILE = DATA / "meteosat-clm" / "clm.json"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2020.json"
# Each image's satellite where it was when it took the image (tools/fetch_scene_elements.py).
SCENE_ELEMENTS_FILE = TLE_DIR / "scene-elements.json"

# SMHI's sea level at Spikarna (2061) outside Sundsvall, hourly in RH2000 (tools/fetch_smhi_sea_level.py).
SEA_LEVEL_DIR = DATA / "sea-level"
SEA_LEVEL_STATIONS = {"2061": "Spikarna"}
# The log's line for the sea and the harbour's sensors' alarm, as the user chose on 2026-10-29: 81 cm RH2000, the
# lower bound of SMHI's warning of 22 February 2020 (80-100 cm above the year's mean, as Sundsvalls Tidning reported)
# over the mean sea level at Spikarna in 2020, +1.4 cm RH2000 by SMHI's equation (16.2 - 0.74 x (year - 2000) cm,
# mwreg_MWekvationer). The sea passed it briefly on the morning of 21 February and from 08 UTC on 22 February.
SEA_LEVEL_STORM_CM = 81.0
# Eight days: the sea level by the hour, and, as in ljungan-aug2023, the 72 hours after the clock marked
# as measured afterwards, not a forecast (no forecast as issued in 2020 is archived).
SEA_LEVEL_HOURLY = True
SEA_LEVEL_AHEAD_HOURS = 72

# Sundsvall's centre, where the Selånger river meets the sea.
FIRE_CENTRE = (62.391, 17.307)
FIRE_BBOX = (62.28, 62.47, 17.0, 17.55)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town, the Selånger valley and the harbour.
VIEW_BBOX = (62.28, 62.47, 16.9, 17.55)
# sundsvall2026's map area (lon/lat, west, south, east, north), which reaches Skallböle in the west.
MAP_BBOX = (16.9, 62.15, 17.8, 62.62)

PERIOD_START = date(2020, 2, 16)
PERIOD_END = date(2020, 3, 1)
# From before the rain to after Landsat 8's clear image of 26 February.
PLAYBACK_START = datetime(2020, 2, 19, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2020, 2, 27, 0, 0, tzinfo=timezone.utc)
# Eight days at half an hour a second, slowing at the satellites' passes.
PLAYBACK_SPEED = 1800.0
# The sea's highest at Spikarna, 97.7 cm at 15 UTC on 22 February.
CHECK_START_UTC = "2020-02-22T12:00:00Z"
DATABASE = "sundsvall-feb2020"
TILES_FILE = "sundsvall.mbtiles"
CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 18.5, "lat": 62.0, "height": 900_000, "pitch": -75, "seconds": 2.0},  # The Bothnian Sea
    {"lon": 17.2, "lat": 62.2, "height": 160_000, "pitch": -60, "seconds": 2.2},  # Medelpad
]
FOCUS_LAND = "stans land"
RAIN_GAUGES = "SMHI:s mätare"
# The rain by the hour (SMHI parameter 7): only SMHI's Brämön A out at sea; the municipality's gauges
# started in March-April 2020 (checked 2026-10-29). SMHI's radar gives the hourly rain over the town.
RAIN_STATIONS = {"127130": "Brämön A"}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC) by the town. Sidsjö D lies by the dam.
DAILY_RAIN_STATIONS = {"127220": "Sidsjö D", "127320": "Stordalen-Midlanda D"}
DAILY_RAIN_DIR = DATA / "smhi-daily"
# SMHI's flow station on Ljungan by Sundsvall ("station:parameter", every 15 minutes); Ljungan was low.
HYDRO_STATIONS = {"1650:2": "Skallböle"}
# SMHI's modelled daily flows (S-HYPE) by SUBID, from Vattenwebb's files downloaded by hand into
# MODEL_FLOW_DIR/raw/ (tools/read_vattenwebb.py; the files of ljungan-aug2023 cover 2010-2024): the
# Selånger river at its outlet in the sea (449 km²) and Sidsjöbäcken (27 km²), which have no SMHI station.
MODEL_FLOW_DIR = DATA / "s-hype"
MODEL_FLOW_STATIONS = {"12849": "Selångersån", "12794": "Sidsjöbäcken"}
# Sentinel-1's wind over the sea (OCN; tools/fetch_sentinel1_wind.py), as in ljungan-aug2023. Sentinel-1A and 1B
# passed the Sundsvall bay eleven times in the playback, but the products flag the wind over the bay poor on all but
# two (checked 2026-10-29), the storm's passes of 22 and 23 February among them, and poor wind is left out: only
# 20 February at 16:21 UTC (Sentinel-1B, about 11 m/s from the south) and 26 February at 05:06 UTC remain.
# Needs a Copernicus Data Space account.
SENTINEL1_WIND_DIR = DATA / "sentinel1-wind"
# The names of the rivers and streams (tools/fetch_osm_waterways.py).
WATERWAY_LABELS_FILE = DATA / "osm" / "waterway-labels.geojson"

# What Sundsvalls Tidning reported on 22 February 2020. It says SMHI's warning was updated in the
# morning but gives no time, so the time is approximate; no place is named but the Selånger river.
ROUTE_REPORT = "Sundsvalls Tidning 22 februari 2020"
ROUTE_IMPACT_LABEL = "Enligt medierna"
ROUTE_SOURCE_LABEL = "Sundsvalls Tidning"
ROUTE_ATTRIBUTION = "Sundsvalls Tidning"
ROUTE_IMPACTS = [
    {"time_utc": "2020-02-22T07:00:00Z", "kind": "alert", "approximate_time": True, "source_label": "SMHI, via Sundsvalls Tidning",
     "text": "SMHI varnar för högt vattenstånd i norra Bottenhavet, 80–100 centimeter över medelvattenståndet (klass 1)"},
    {"time_utc": "2020-02-22T09:00:00Z", "kind": "alert", "approximate_time": True, "source_label": "Sundsvalls Tidning",
     "text": "Spöregn följt av snöväder i Medelpad, och ovanligt högt vattenstånd"},
]
# Three synthetic level sensors by the harbour (tools/derive_impact_sensor_points.py, level_sensors.py), at places
# by the quays in OSM: the inner harbour at Hamnplan, the Selånger river's mouth (S-HYPE's outlet point) and
# Rosenborgskajen. They measure nothing but follow Spikarna's sea level (`station`) and alarm at SEA_LEVEL_STORM_CM;
# the DEM's 30 m surface cannot tell the quays' height, so they are not said to be low points.
LEVEL_SENSOR_SITES = [
    {"site": "Inre hamnen", "latitude": 62.3911, "longitude": 17.3140, "station": "sea-2061", "source_label": "Syntetisk plats vid kajen"},
    {"site": "Selångersåns mynning", "latitude": 62.39309, "longitude": 17.3151, "station": "sea-2061", "source_label": "Syntetisk plats vid mynningen"},
    {"site": "Rosenborgskajen", "latitude": 62.3889, "longitude": 17.3206, "station": "sea-2061", "source_label": "Syntetisk plats vid kajen"},
]
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
LEVEL_ALARM_LEVEL = SEA_LEVEL_STORM_CM
SENSOR_WORDS = {"sensors": "nivågivare", "the_sensors": "nivågivarna", "alarming": "larmande"}

# The satellites that imaged Sundsvall in the period (Planetary Computer catalogue, checked
# 2026-10-29; both Sentinel-1A and 1B flew) and the ISS, by NORAD number; element sets a few days
# around the playback.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "41456": "Sentinel-1B", "40697": "Sentinel-2A", "42063": "Sentinel-2B",
    "25682": "Landsat 7", "39084": "Landsat 8", "25544": "ISS", "40732": "Meteosat-11",
}
TLE_START, TLE_END = "2020-02-15", "2020-03-01"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "41456": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": None},
    "40697": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "25682": {"firms": None, "instrument": "ETM+", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "39084": {"firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
    # The MSG satellite at 0 degrees in 2020, whose cloud mask and cloud tops the demo shows.
    "40732": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
}
SATELLITE_LABEL = "Position 2020, beräknad ur banelement (SGP4) – inte en observation"

# Landsat 8 after the storm (tools/fetch_landsat_scene.py): scene cloud 2.5 % on 26 February, collection
# tier 2 (less exact geometry than tier 1); 19 February is 43 %, and Landsat 7's clear 27 February is striped.
LANDSAT_SCENES = {"after": "LC08_L2SP_194016_20200226_02_T2"}
LANDSAT_ROLES = {"before": "Före ovädret", "during": "Under ovädret", "after": "Efter ovädret"}
# The town and the lower Selånger valley, for the coverage and cloud of each scene.
LANDSAT_FOCUS_AREA = (17.15, 62.33, 17.45, 62.45)
# About 30 m over MAP_BBOX: 0.9 degrees of longitude and 0.47 of latitude at 62.4 N.
LANDSAT_SIZE = (1546, 1742)
# Sentinel-1's passes over the town (Planetary Computer catalogue, sentinel-1-grd, checked 2026-10-29;
# the start of each pass's first product): Sentinel-1A before the storm, Sentinel-1B the morning after the
# sea's peak (extra-wide mode, HH), and Sentinel-1A after it. Sentinel-1B's pass an hour after the peak, at
# 16:04 UTC on 22 February, covers only 20 % of the town and is left out. After the storm neither image
# tells water from land (wet snow), which the panel says.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2020-02-19T16:30:14Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2020-02-23T05:29:45Z", "satellite": "Sentinel-1B", "norad": "41456"},
    {"time_utc": "2020-02-24T05:22:35Z", "satellite": "Sentinel-1A", "norad": "39634"},
]
# Sentinel-2 (tools/fetch_sentinel2_scene.py), by product name up to the relative orbit: before the
# storm (scene cloud 37 %) and after it (13 %); 21 February is 66-69 %.
SENTINEL2_SCENES = {
    "before": "S2B_MSIL2A_20200219T102949_R108",
    "after": "S2A_MSIL2A_20200224T103021_R108",
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
    # White outside the municipality: kept transparent, so OSM shows there (fetch_municipal_basemap.py).
    "white_outside": True,
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
    "smhi": ("SMHI öppna data (CC BY 4.0 SE): nederbörd vid Brämön A, Sidsjö D och Stordalen-Midlanda D, väderradar, "
             "vattenföring vid Skallböle och havsvattenstånd vid Spikarna; modellerad vattenföring (S-HYPE) i Vattenwebb"),
    "sentinel": "Innehåller bearbetade Copernicus Sentinel-data 2020",
    "era5_land": "Innehåller bearbetad information från Copernicus Climate Change Service (ERA5-Land och ERA5 över havet), CC BY 4.0",
    "mcf": "Översvämningskartering © MCF (tidigare MSB)",
    "sundsvall": "Skyfallsmodeller och kartlager © Sundsvalls kommun",
    "copernicus_dem": (
        "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 "
        "provided under COPERNICUS by the European Union and ESA; all rights reserved"
    ),
}
