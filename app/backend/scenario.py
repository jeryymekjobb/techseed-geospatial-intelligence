"""The scenario the demo runs: its data files, area, period, playback and texts.

The values come from one module in app/backend/scenarios/, chosen by the environment
variable TECHSEED_SCENARIO (default vastmanland2014). The modules that use them read
them when they are imported, so the scenario is chosen before the backend starts:
`server.py --scenario` restarts itself with the variable set.
"""

from __future__ import annotations

import importlib
import os

from app.backend.scenarios import AVAILABLE, DEFAULT, REPO_ROOT

NAME = os.environ.get("TECHSEED_SCENARIO") or DEFAULT
if NAME not in AVAILABLE:
    raise SystemExit(f"Unknown scenario {NAME!r} in TECHSEED_SCENARIO; available: {', '.join(AVAILABLE)}")
_module = importlib.import_module(f"app.backend.scenarios.{NAME}")

TITLE = _module.TITLE
DATA_LABEL = _module.DATA_LABEL
CONTROL_LABEL = _module.CONTROL_LABEL
SUMMARY = getattr(_module, "SUMMARY", [])
FIRMS_FILES = _module.FIRMS_FILES
TERRAIN_FILE = _module.TERRAIN_FILE
TARGETS_FILE = _module.TARGETS_FILE
WEATHER_DIR = _module.WEATHER_DIR
WIND_FILE = _module.WIND_FILE
DEM_DIR = _module.DEM_DIR
TERRAIN_DIR = _module.TERRAIN_DIR
LANDSAT_DIR = _module.LANDSAT_DIR
TLE_DIR = _module.TLE_DIR
TLE_FILE_NAME = _module.TLE_FILE_NAME
FIRE_CENTRE = _module.FIRE_CENTRE
FIRE_BBOX = _module.FIRE_BBOX
VIEW_BBOX = _module.VIEW_BBOX
MAP_BBOX = _module.MAP_BBOX
PERIOD_START = _module.PERIOD_START
PERIOD_END = _module.PERIOD_END
PLAYBACK_START = _module.PLAYBACK_START
PLAYBACK_END = _module.PLAYBACK_END
CHECK_START_UTC = _module.CHECK_START_UTC
# The satellite image tools/check_demo.py waits for in the fire's playback, by the start of its text.
CHECK_IMAGE = getattr(_module, "CHECK_IMAGE", "Under branden: Landsat 8")
# The fire assessment's outcome the check expects after the playback to 14:00 local time.
CHECK_OUTCOME = getattr(_module, "CHECK_OUTCOME", "Wildfire probable")
# The flood's demo check (tools/check_demo.py): the moment of its rain and sensor step and the
# sensors it expects to confirm then, and where its SATCOM outage starts.
CHECK_PEAK_UTC = getattr(_module, "CHECK_PEAK_UTC", None)
CHECK_SENSORS = getattr(_module, "CHECK_SENSORS", None)
CHECK_SATCOM_UTC = getattr(_module, "CHECK_SATCOM_UTC", None)
# MCF's layers for the flood's PostGIS questions (tools/fetch_mcf_flood_maps.py), its words for
# the area the questions ask about and for the models behind it.
MCF_LAYERS = getattr(_module, "MCF_LAYERS", None)
FLOOD_AREA_WORD = getattr(_module, "FLOOD_AREA_WORD", "100-årsflödet")
FLOOD_MODELS = getattr(_module, "FLOOD_MODELS", "Kommunens och MCF:s modeller")
# The river flood's synthetic level sensors (level_sensors.py): their points
# (tools/derive_level_sensor_points.py), MCF's watercourses with SMHI's stations that drive them,
# and the words the screens use for the flood's sensors.
LEVEL_SENSOR_FILE = getattr(_module, "LEVEL_SENSOR_FILE", None)
LEVEL_SENSOR_RIVERS = getattr(_module, "LEVEL_SENSOR_RIVERS", {})
# The cloudburst's synthetic overflow sensors at its reported damage, with the radar's rain at each
# (tools/derive_radar_sensor_points.py, flood_sensors.py).
RADAR_SENSOR_FILE = getattr(_module, "RADAR_SENSOR_FILE", None)
SENSOR_WORDS = getattr(_module, "SENSOR_WORDS", {"sensors": "bräddgivare", "the_sensors": "bräddgivarna",
                                                  "alarming": "bräddande"})
DATABASE = _module.DATABASE
TILES_FILE = _module.TILES_FILE
CAMERA_ROUTE = _module.CAMERA_ROUTE
TLE_SATELLITES = _module.TLE_SATELLITES
TLE_START = _module.TLE_START
TLE_END = _module.TLE_END
SATELLITE_ROLES = _module.SATELLITE_ROLES
SATELLITE_LABEL = _module.SATELLITE_LABEL
LANDSAT_SCENES = _module.LANDSAT_SCENES
LANDSAT_ROLES = _module.LANDSAT_ROLES
LANDSAT_FOCUS_AREA = _module.LANDSAT_FOCUS_AREA
LANDSAT_SIZE = _module.LANDSAT_SIZE
FORECAST_WEATHER_FILES = _module.FORECAST_WEATHER_FILES
FORECAST_METHOD = _module.FORECAST_METHOD
FORECAST_REPORT = _module.FORECAST_REPORT
SPATIAL_SOURCE = _module.SPATIAL_SOURCE
ATTRIBUTION = _module.ATTRIBUTION
INCIDENT = _module.INCIDENT
INCIDENT_PLACE = _module.INCIDENT_PLACE
INCIDENT_AREA = _module.INCIDENT_AREA
WILDFIRE = INCIDENT == "wildfire"
# Only some scenarios have these.
RAIN_STATIONS = getattr(_module, "RAIN_STATIONS", {})
SENTINEL2_DIR = getattr(_module, "SENTINEL2_DIR", None)
SENTINEL1_DIR = getattr(_module, "SENTINEL1_DIR", None)
# ERA5 wind where ERA5-Land has none (tools/fetch_era5_sea.py) and SMHI's radar (tools/fetch_smhi_radar.py).
WIND_SEA_FILE = getattr(_module, "WIND_SEA_FILE", None)
RADAR_DIR = getattr(_module, "RADAR_DIR", None)
# SMHI's measured flows and lake levels (tools/fetch_smhi_hydro.py) and their stations.
HYDRO_DIR = getattr(_module, "HYDRO_DIR", None)
HYDRO_STATIONS = getattr(_module, "HYDRO_STATIONS", {})
# The flood's words: the land the radar's water is counted on, and who runs the rain gauges.
FOCUS_LAND = getattr(_module, "FOCUS_LAND", "fokusområdets land")
RAIN_GAUGES = getattr(_module, "RAIN_GAUGES", "SMHI:s mätare")
# Copernicus EMS's mapped perimeters of a fire (tools/fetch_ems_perimeters.py).
EMS_AREA = getattr(_module, "EMS_AREA", None)
EMS_DIR = getattr(_module, "EMS_DIR", None)
# MET Norway's archived weather forecasts for the fire (met_forecast.py); only Kårböle 2018 so far.
MET_FORECAST_DIR = getattr(_module, "MET_FORECAST_DIR", None)
# SMHI's observed lightning over the weather chart's area (tools/fetch_smhi_lightning.py, lightning.py).
LIGHTNING_DIR = getattr(_module, "LIGHTNING_DIR", None)
# Meteosat's fire pixels over the map area from LSA SAF (tools/fetch_meteosat_frp.py, meteosat.py).
METEOSAT_FRP_FILE = getattr(_module, "METEOSAT_FRP_FILE", None)
# The fire's forecast weather station, for the screens' texts.
FORECAST_STATION = getattr(_module, "FORECAST_STATION", "")
SENTINEL2_SCENES = getattr(_module, "SENTINEL2_SCENES", {})
SENTINEL2_SIZE = getattr(_module, "SENTINEL2_SIZE", None)
RADAR_ANALYSIS_BBOX = getattr(_module, "RADAR_ANALYSIS_BBOX", None) or MAP_BBOX
FLOOD_HAZARD_WMS = getattr(_module, "FLOOD_HAZARD_WMS", None)
MUNICIPAL_WMS = getattr(_module, "MUNICIPAL_WMS", None)
MUNICIPAL_DIR = getattr(_module, "MUNICIPAL_DIR", None)
# The municipality's map as a locally kept base map (municipal_basemap.py); only Sundsvall 2026.
MUNICIPAL_BASEMAP = getattr(_module, "MUNICIPAL_BASEMAP", None)
# The offline map's road numbers and dashed railway tunnels as a layer of their own over the base map,
# the images and the flood maps (offline_tiles.py); every scenario has it, as the user asked on 2026-10-19.
ROAD_OVERLAY = getattr(_module, "ROAD_OVERLAY", True)
MUNICIPAL_BASEMAP_DIR = getattr(_module, "MUNICIPAL_BASEMAP_DIR", None)
MUNICIPAL_BASEMAP_BBOX = getattr(_module, "MUNICIPAL_BASEMAP_BBOX", None) or MAP_BBOX
MCF_DIR = getattr(_module, "MCF_DIR", None)
SENTINEL1_ACQUISITIONS = getattr(_module, "SENTINEL1_ACQUISITIONS", [])
# Roads and railways the incident damaged, as a report tells it, and those under heavy rain
# computed from SMHI's radar (routes.py, tools/derive_route_exposure.py); only Västernorrland 2025.
ROUTE_IMPACTS = getattr(_module, "ROUTE_IMPACTS", [])
ROUTE_REPORT = getattr(_module, "ROUTE_REPORT", "")
# The damage layer's name, the short source label the screens show and the map's attribution.
ROUTE_IMPACT_LABEL = getattr(_module, "ROUTE_IMPACT_LABEL", None)
ROUTE_SOURCE_LABEL = getattr(_module, "ROUTE_SOURCE_LABEL", "Länsstyrelsen, utredning 2026")
ROUTE_ATTRIBUTION = getattr(_module, "ROUTE_ATTRIBUTION", "Länsstyrelsen Västernorrland, utredning 2026")
ROUTE_EXPOSURE_FILE = getattr(_module, "ROUTE_EXPOSURE_FILE", None)
# The level sensors' alarm as a rise over the flow at the playback's start, instead of above the
# station's record (level_sensors.py); and SMHI's stations that report the rain by the day (daily_rain.py).
LEVEL_ALARM_RISE = getattr(_module, "LEVEL_ALARM_RISE", None)
DAILY_RAIN_STATIONS = getattr(_module, "DAILY_RAIN_STATIONS", {})
DAILY_RAIN_DIR = getattr(_module, "DAILY_RAIN_DIR", None)
