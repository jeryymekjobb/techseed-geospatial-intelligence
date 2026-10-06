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
