"""Rain and a storm from the sea at Sundsvall on 27-30 December 2020.

Decided 2026-10-29 from the study reports/2026-10-28-forstudie-sundsvall-2020-2021-claude-opus-5-5.md,
where this was the best candidate in SMHI's data for the floods the user had heard of in 2020: Sidsjö D had
30.0 mm on 28 December and 25.0 mm on 29 December at 3-4 °C, Brämön had a southeasterly wind of 12-15 m/s
from the sea, the sea stood 58.7 cm RH2000 at Spikarna, and in SMHI's model S-HYPE the Selånger river and
Sidsjöbäcken had their highest flows of 2020 on 30 December, above their mean annual highest. No flooding
was reported: the study found nothing in the press, SMHI's summary of the sea level in 2020 says December
had no extreme levels, and SVT's December review names floods only in southern Sweden. The screens say so.
Sidsjödammen is not shown as a marked "if" here, as the user chose on 2026-10-29: no threat to it was
reported, and Sidsjöbäcken's flow, 3.0 m³/s or 111 % of its mean annual highest (SMHI's MHQ for 1991-2020 in
Vattenwebb's file; the study's 121 % was wrong), was not exceptional.
The scenario replays these data; it is not live.
It shares sundsvall2026's map area, so its offline map, DEM, terrain, OSM layers, municipal
base map and flood areas are those in data/sundsvall2026/; its own data live in the unversioned
data/sundsvall-dec2020/.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.backend.scenarios import REPO_ROOT

DATA = REPO_ROOT / "data" / "sundsvall-dec2020"
# The map, terrain and OSM layers of sundsvall2026, over the same MAP_BBOX.
SHARED = REPO_ROOT / "data" / "sundsvall2026"

INCIDENT = "flood"
INCIDENT_PLACE = "Sundsvall"
INCIDENT_AREA = "Sundsvall"
TITLE = "Regn och storm från havet i Sundsvall, december 2020"
# The county the menu groups it under (tools/start_demo.py).
REGION = "Västernorrlands län"
DATA_LABEL = "Historiska data december 2020 – uppspelning, inte live"
CONTROL_LABEL = "Scenario: FLOOD – Sundsvall december 2020, historiska data"
# The summary the main screen shows, and the satellite monitor reads aloud, when the scenario
# comes to its start (satlog.js summaryState): what the demo shows and what is real.
SUMMARY = [
    "Regn och storm från havet i Sundsvall i december 2020. Det här är uppmätta data, inte i realtid.",
    "Vid Sidsjön föll 55 millimeter regn på två dygn i plusgrader, och vinden kom från havet. Inga översvämningar rapporterades.",
    "Selångersån och Sidsjöbäcken fick årets högsta flöde den 30 december, beräknat i SMHI:s modell.",
    "Regn och flöden från SMHI, SMHI:s väderradar och havsvattenståndet vid Spikarna. Flödena i Selångersån och Sidsjöbäcken är beräknade, inte uppmätta.",
    "Radarbilder från Sentinel-1, som ser genom moln och mörker. Det var för mörkt för bilder i synligt ljus.",
    "Bräddgivarna DV1–DV8 är simulerade och beräknade ur det verkliga regnet. Nivågivarna vid Himlabadet och Selångersåns mynning är simulerade och följer de beräknade flödena.",
]

FIRMS_FILES: list = []
TERRAIN_FILE = SHARED / "osm" / "terrain-sundsvall.geojson"
TARGETS_FILE = SHARED / "osm" / "targets-sundsvall.geojson"
WEATHER_DIR = DATA / "smhi"
WIND_FILE = DATA / "era5-land" / "era5-land-sundsvall-dec2020.csv"
# ERA5 over the sea, where ERA5-Land has no values (tools/fetch_era5_sea.py).
WIND_SEA_FILE = DATA / "era5-land" / "era5-sea-sundsvall-dec2020.csv"
# SMHI's measured flows (tools/fetch_smhi_hydro.py).
HYDRO_DIR = DATA / "hydro"
# SMHI's weather radar as rain images (tools/fetch_smhi_radar.py).
RADAR_DIR = DATA / "radar"
DEM_DIR = SHARED / "dem"
TERRAIN_DIR = SHARED / "terrain"
# MET Norway's archived weather forecasts, as issued (tools/fetch_met_forecasts.py, met_forecast.py).
MET_FORECAST_DIR = DATA / "met-forecast"
# SMHI's observed lightning (tools/fetch_smhi_lightning.py).
LIGHTNING_DIR = DATA / "lightning"
# The Sentinel-1 radar images of the acquisitions (tools/fetch_sentinel1_scene.py).
SENTINEL1_DIR = DATA / "sentinel1"
# The municipality's critical stormwater points and flood areas, and MCF's (shared). The synthetic
# overflow sensors DV1-DV8 of sundsvall2026 stand at the same points (flood_sensors.py), filled by 2020's rain.
MUNICIPAL_DIR = SHARED / "municipal"
MCF_DIR = SHARED / "mcf"
# Meteosat's cloud top height every 15 minutes and cloud mask every hour (MSG).
METEOSAT_CTH_FILE = DATA / "meteosat-cth" / "cth.json"
METEOSAT_CLM_FILE = DATA / "meteosat-clm" / "clm.json"
TLE_DIR = DATA / "tle"
TLE_FILE_NAME = "tle-2020.json"

# SMHI's sea level at Spikarna (2061) outside Sundsvall, hourly in RH2000 (tools/fetch_smhi_sea_level.py).
SEA_LEVEL_DIR = DATA / "sea-level"
SEA_LEVEL_STATIONS = {"2061": "Spikarna"}
# The sea stood at most 58.7 cm RH2000, below any warning, so no storm lines.
SEA_LEVEL_STORM_CM = 100.0
# Seven days: the sea level by the hour, and, as in ljungan-aug2023, the 72 hours after the clock marked
# as measured afterwards, not a forecast (no forecast as issued in 2020 is archived).
SEA_LEVEL_HOURLY = True
SEA_LEVEL_AHEAD_HOURS = 72

# Sundsvall's centre, between Sidsjöbäcken and the Selånger river's outlet.
FIRE_CENTRE = (62.391, 17.307)
FIRE_BBOX = (62.28, 62.47, 17.0, 17.55)  # min_lat, max_lat, min_lon, max_lon
# Map view: the town, the Selånger valley and lower Ljungan with Skallböle.
VIEW_BBOX = (62.28, 62.47, 16.9, 17.55)
# sundsvall2026's map area (lon/lat, west, south, east, north), which reaches Skallböle in the west.
MAP_BBOX = (16.9, 62.15, 17.8, 62.62)

PERIOD_START = date(2020, 12, 22)
PERIOD_END = date(2021, 1, 3)
# From before the rain to after the computed flows' peak on 30 December.
PLAYBACK_START = datetime(2020, 12, 25, 0, 0, tzinfo=timezone.utc)
PLAYBACK_END = datetime(2021, 1, 1, 0, 0, tzinfo=timezone.utc)
# Seven days at half an hour a second, slowing at the satellites' passes.
PLAYBACK_SPEED = 1800.0
# The demo check (tools/check_demo.py), as in every scenario: it starts on 28 December, before Sentinel-1B's
# last pass over the town at 16:21 UTC (none passed on 29-31 December), and its SATCOM outage starts before that
# pass. On 29 December, the day of the heaviest rain, the two level sensors alarm, but the overflow sensors stay
# almost empty and no flow or level passes its record, so the assessment says "Possible flood", as no flood was
# reported; the radar's new water (0.04 %) keeps the detection sequence at "Okänd".
CHECK_START_UTC = "2020-12-28T12:00:00Z"
CHECK_PEAK_UTC = "2020-12-29T12:00:00Z"
CHECK_SENSORS = "2/10"
CHECK_OUTCOME = "Possible flood"
CHECK_SATCOM_UTC = "2020-12-28T13:00:00Z"
CHECK_DETECTION_OUTCOME = "Okänd"
DATABASE = "sundsvall-dec2020"
TILES_FILE = "sundsvall.mbtiles"
CAMERA_ROUTE = [
    {"lon": 12, "lat": 52, "height": 16_000_000, "pitch": -90, "seconds": 1.8},  # Earth over Europe
    {"lon": 15, "lat": 60, "height": 3_500_000, "pitch": -90, "seconds": 2.0},   # Europe
    {"lon": 18.5, "lat": 62.0, "height": 900_000, "pitch": -75, "seconds": 2.0},  # The Bothnian Sea
    {"lon": 17.2, "lat": 62.2, "height": 160_000, "pitch": -60, "seconds": 2.2},  # Medelpad
]
FOCUS_LAND = "stans land"
RAIN_GAUGES = "kommunens mätare"
# The rain gauges (SMHI parameter 7, hourly precipitation): the municipality's own that measured in December
# 2020 (Fillan, Heffners, Essvik and Bällsta from March-April 2020; Bredsand and Stångom came later; checked
# 2026-10-29), which run an hour behind SMHI's own (see the backlog), and SMHI's Brämön A.
RAIN_STATIONS = {"2222813": "Fillan", "2222814": "Heffners", "2222811": "Essvik", "2222812": "Bällsta", "127130": "Brämön A"}
# SMHI's stations that report the rain by the day (parameter 5, 06-06 UTC) by the town. Sidsjö D lies by the dam.
DAILY_RAIN_STATIONS = {"127220": "Sidsjö D", "127320": "Stordalen-Midlanda D"}
DAILY_RAIN_DIR = DATA / "smhi-daily"
# SMHI's flow station on Ljungan by Sundsvall ("station:parameter", every 15 minutes); Ljungan was not high.
HYDRO_STATIONS = {"1650:2": "Skallböle"}
# SMHI's modelled daily flows (S-HYPE) by SUBID, from Vattenwebb's files downloaded by hand into
# MODEL_FLOW_DIR/raw/ (tools/read_vattenwebb.py; the files of ljungan-aug2023 cover 2010-2024): the
# Selånger river at its outlet in the sea (449 km²) and Sidsjöbäcken (27 km²), which have no SMHI station.
MODEL_FLOW_DIR = DATA / "s-hype"
MODEL_FLOW_STATIONS = {"12849": "Selångersån", "12794": "Sidsjöbäcken"}
# Sentinel-1's wind over the sea (OCN; tools/fetch_sentinel1_wind.py), as in ljungan-aug2023 and sundsvall-feb2020.
# Of nine passes over the bay on 26-31 December the products flag the wind poor on all but Sentinel-1B's at 16:21 UTC
# on 28 December (checked 2026-10-29), which shows the storm from the sea: about 14 m/s from the southeast.
# Needs a Copernicus Data Space account.
SENTINEL1_WIND_DIR = DATA / "sentinel1-wind"
# The names of the rivers and streams (tools/fetch_osm_waterways.py).
WATERWAY_LABELS_FILE = DATA / "osm" / "waterway-labels.geojson"

# Two synthetic level sensors (level_sensors.py; tools/derive_impact_sensor_points.py, the `level-sensors` step
# of fetch_scenario), as in ljungan-aug2023: Himlabadet by Sidsjöbäcken (OSM's building) and the Selånger river's
# outlet (S-HYPE's outlet point), each following its nearest flow, both computed. They alarm when that flow is
# twice its flow at the playback's start.
LEVEL_SENSOR_SITES = [
    {"site": "Himlabadet, Sidsjöbäcken", "latitude": 62.39404, "longitude": 17.28916, "source_label": "Syntetisk plats vid Sidsjöbäcken"},
    {"site": "Selångersåns utlopp", "latitude": 62.39309, "longitude": 17.3151, "source_label": "Syntetisk plats vid S-HYPE:s utloppspunkt"},
]
LEVEL_SENSOR_FILE = DATA / "sensors" / "level-points.geojson"
LEVEL_ALARM_RISE = 2.0
# The overflow sensors DV1-DV8 stay beside the level sensors (level_sensors.BothSensors).
OVERFLOW_WITH_LEVEL_SENSORS = True
SENSOR_WORDS = {"sensors": "givare", "the_sensors": "givarna", "alarming": "larmande"}

# The satellites over Sundsvall in the period (both Sentinel-1A and 1B flew) and the ISS, by NORAD number;
# element sets a few days around the playback. It was too dark for the optical satellites' images.
TLE_SATELLITES = {
    "39634": "Sentinel-1A", "41456": "Sentinel-1B", "25544": "ISS", "40732": "Meteosat-11",
}
TLE_START, TLE_END = "2020-12-21", "2021-01-04"
SATELLITE_ROLES = {
    "39634": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln och mörker", "half_swath_km": None},
    "41456": {"firms": None, "instrument": "SAR", "role": "Radar, ser genom moln och mörker", "half_swath_km": None},
    "25544": {"firms": None, "instrument": None, "role": "Rymdstationen", "half_swath_km": None},
    # The MSG satellite at 0 degrees in 2020, whose cloud mask and cloud tops the demo shows.
    "40732": {"firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden", "half_swath_km": None, "geostationary": True},
}
SATELLITE_LABEL = "Position 2020, beräknad ur banelement (SGP4) – inte en observation"
# No optical images: Landsat and Sentinel-2 had none in the dark round Christmas 2020 (the study).
LANDSAT_DIR = DATA / "landsat"
LANDSAT_SCENES: dict = {}
LANDSAT_ROLES = {"before": "Före regnet", "during": "Under regnet", "after": "Efter regnet"}
# The town and the lower Selånger valley, for the coverage of each scene.
LANDSAT_FOCUS_AREA = (17.15, 62.33, 17.45, 62.45)
# About 30 m over MAP_BBOX: 0.9 degrees of longitude and 0.47 of latitude at 62.4 N.
LANDSAT_SIZE = (1546, 1742)
# The radar images' grid, about 20 m over MAP_BBOX, as the Sentinel-2 images of the other Sundsvall scenarios.
SENTINEL2_SIZE = (2320, 2613)
# Sentinel-1's passes over the town (Planetary Computer catalogue, sentinel-1-grd, checked 2026-10-29;
# the start of each pass's first product): Sentinel-1A on the morning before the heaviest rain and
# Sentinel-1B (extra-wide mode, HH) on 28 December; none passed over the town on 29-31 December.
SENTINEL1_ACQUISITIONS = [
    {"time_utc": "2020-12-27T05:14:34Z", "satellite": "Sentinel-1A", "norad": "39634"},
    {"time_utc": "2020-12-28T05:05:40Z", "satellite": "Sentinel-1B", "norad": "41456"},
    {"time_utc": "2020-12-28T16:21:09Z", "satellite": "Sentinel-1B", "norad": "41456"},
]

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
    "smhi": ("SMHI öppna data (CC BY 4.0 SE): nederbörd vid kommunens mätare, Brämön A, Sidsjö D och Stordalen-Midlanda D, väderradar, "
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
