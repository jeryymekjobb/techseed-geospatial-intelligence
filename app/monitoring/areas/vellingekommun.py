"""Vellinge kommun, with the beach erosion on Falsterbonäset 2012-2026 as its scenario; Flens
kommun's monitoring is the template (common.py). No SMHI flow station lies in the municipality
(Svedala on Sege å flows to Malmö), so there are no flows; the sea level, which the scenario follows
at Skanör, is read live at Klagshamn, since Skanör's gauge gives SMHI's archive only (checked
2026-11-04). The base map is the municipality's own in full colour (Bakgrundskarta_Infracontrol), for
internal use (D-2026-11-04b). Its state and inbox live in the unversioned data/monitoring/vellingekommun/.
"""

from __future__ import annotations

from app.monitoring.areas.common import *  # noqa: F403 - the template's shared satellites, limits and contacts
from app.monitoring.areas.common import built_terrain, built_tiles, data_dir, scenario_data

NAME = "Vellinge kommun"
MUNICIPALITY_CODE = "1233"
COUNTY = "Skåne län"
# SMHI's id of the county in its warnings (affectedAreas, metadata/area.json), checked 2026-11-04.
SMHI_COUNTY_ID = 12
KRISINFO_WORDS = ("Skåne", "Vellinge", "Falsterbo")
# west, south, east, north: the municipality (MCF's border, 12.61-13.18 E, 55.15-55.52 N) with a margin.
BBOX = (12.55, 55.12, 13.25, 55.56)
CENTRE = (55.47, 13.02)
DATA_DIR = data_dir("vellingekommun")

# Vellinge kommun's background map in full colour (karta.vellinge.se, Bakgrundskarta_Infracontrol,
# ArcGIS Server 11.3, no token; checked 2026-11-04). It states no copyright or terms and holds property
# boundaries, so Lantmäteriet's data are likely in it; internal use (D-2026-11-04b). Fetched by ArcGIS
# REST export in Web Mercator; it is 253, 253, 253 outside the municipality, a colour it lacks inside,
# which is made transparent (tools/fetch_municipal_basemap.py). The greyed KommunKartaNedtonad, which
# the user found too pale, is shown until it is fetched (service.Monitor.map_dir).
MUNICIPAL_BASEMAPS = [{
    "id": "vellinge", "kind": "arcgis",
    "url": "https://karta.vellinge.se/arcgis/rest/services/Bakgrundskarta/Bakgrundskarta_Infracontrol/MapServer",
    "label": "Vellinge kommun (Bakgrundskarta)",
    "attribution": "Karta © Vellinge kommun – intern användning",
    "white_outside": True, "outside_colour": (253, 253, 253),
    "permission": "Internal use in the development department (D-2026-11-04b); the service states no terms.",
    "note": "Vellinge kommun's Bakgrundskarta_Infracontrol in full colour, white outside the municipality.",
    "dir": DATA_DIR / "municipal-basemap" / "vellinge-farg",
    "fallback_dir": DATA_DIR / "municipal-basemap" / "vellinge",
}]
# The municipality (MCF's border, 12.61-13.18 E, 55.15-55.52 N) with a small margin.
MUNICIPAL_BASEMAP_BBOX = (12.58, 55.13, 13.2, 55.54)
_SCENARIO = scenario_data("falsterbo")
OSM_TARGETS_FILE = _SCENARIO / "osm" / "targets-falsterbo.geojson"
TERRAIN_FILE = _SCENARIO / "osm" / "terrain-falsterbo.geojson"
TERRAIN_DIR = built_terrain("vellingekommun", _SCENARIO / "terrain")
# The offline map over the whole municipality once built (tools/build_offline_tiles.py --area), else the scenario's.
TILES_FILE, MAP_BBOX = built_tiles("vellingekommun", ("falsterbo.mbtiles", (12.76, 55.36, 13.02, 55.46)), BBOX)

# Svedala on Sege å, 4 km outside, which drains towards Malmö, not through the municipality (taken in 2026-11-04).
FLOW_STATIONS = {"1879": "Svedala (Sege å)"}
# SMHI's sea level by the hour (ocobs parameter 6, cm in RH2000), live at Klagshamn on the Öresund,
# just north of the municipality; Skanör's gauge (30488), which Falsterbo's scenario follows, gave no
# value since 2026-10-22 and offers the corrected archive only (checked 2026-11-04).
SEA_LEVEL_STATIONS = {"2095": "Klagshamn", "30488": "Skanör"}
# A proposal, as Falsterbo's scenario at Skanör (SEA_LEVEL_STORM_CM): a high sea level from 100 cm in RH2000.
SEA_LEVEL_HIGH_CM = 100.0
RAIN_STATIONS = {"52240": "Falsterbo A", "52350": "Malmö A"}
# SMHI's weather stations giving values on 2026-11-04, with the parameters each reports.
WEATHER_STATIONS = {
    "52240": {"name": "Falsterbo A", "parameters": [1, 3, 4, 5]},
    "52350": {"name": "Malmö A", "parameters": [1, 3, 4, 7, 5]},
    # Added 2026-11-04 when every station SMHI lists as active in or within 5 km of the municipality was taken
    # in, as the user asked, even silent ones: a silent station is shown grey as a hint it may be out of order.
    "22128058": {"name": "Oxie PST", "parameters": [], "rain_gauge": True},
}
FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE
