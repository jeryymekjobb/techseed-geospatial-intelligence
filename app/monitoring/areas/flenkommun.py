"""Flens kommun: the first area of the continuous monitoring.

The stations are those of the Flen scenarios (app/backend/scenarios/flenkommun2024.py), checked
there on 2026-10-21; the municipality's border is MCF's (Basdata/Kommuner, kommunkod 0482). The base
map is the municipality's own, as the one-pager makes GIS the default: the user decided on
2026-11-03 to use it the same way as Sundsvall's and Västerås's, fetched once and kept locally
(tools/fetch_municipal_basemap.py --area flenkommun), for internal use. OpenStreetMap lies under it,
where the municipal map is white, and its road numbers and railway tunnels over it (the demo's
offline map flenkommun.mbtiles).

Its state, cached border and statistics and the inbox live in the unversioned
data/monitoring/flenkommun/.
"""

from __future__ import annotations

from app.backend.scenarios import REPO_ROOT

NAME = "Flens kommun"
MUNICIPALITY_CODE = "0482"
COUNTY = "Södermanlands län"
# SMHI's id of the county in its warnings (affectedAreas), checked 2026-11-03.
SMHI_COUNTY_ID = 4
# Krisinformation's VMA and news count when an area of theirs names one of these.
KRISINFO_WORDS = ("Södermanland", "Flen")
# west, south, east, north: the municipality (16.42-17.04 E, 58.87-59.24 N) with a margin, as the
# Flen scenarios' MAP_BBOX.
BBOX = (16.3, 58.8, 17.1, 59.28)
CENTRE = (59.06, 16.73)

DATA_DIR = REPO_ROOT / "data" / "monitoring" / "flenkommun"
POLL_SECONDS = 300

# Flens kommun's background map (the folder Flenkartan of gis.flen.se, ArcGIS Server 11.3; copyright
# "Lantmäteriet/GIS"): it covers the whole municipality and is white outside it, and it has no WMS, so
# it is fetched by ArcGIS REST export (checked 2026-11-03). Internal use, as the user decided.
MUNICIPAL_BASEMAPS = [{
    "id": "flen",
    "kind": "arcgis",
    "url": "https://gis.flen.se/arcgis/rest/services/Flenkartan/Bakgrundskarta_AGOL/MapServer",
    "label": "Flens kommun (Bakgrundskarta)",
    "attribution": "Karta © Flens kommun, Lantmäteriet – intern användning",
    "white_outside": True,
    # Not pure white outside the municipality but 253, 253, 253, at every zoom; its roads are pure
    # white and stay (checked 2026-11-03).
    "outside_colour": (253, 253, 253),
    "permission": "The user decided on 2026-11-03 that Techseed may use Flens kommun's map internally and keep it locally.",
    "note": "Flens kommun's Bakgrundskarta_AGOL (Lantmäteriet/GIS), white outside the municipality.",
    "dir": DATA_DIR / "municipal-basemap" / "flen",
}]
# The municipality (16.42-17.04 E, 58.87-59.24 N in OpenStreetMap) with a small margin.
MUNICIPAL_BASEMAP_BBOX = (16.4, 58.85, 17.06, 59.25)
# The demo's offline OpenStreetMap of the Flen scenarios (data/tiles/), served by the tiles service.
TILES_FILE = "flenkommun.mbtiles"
MAP_BBOX = (16.3, 58.8, 17.1, 59.28)

# The satellites whose data the monitoring uses, as the demos show only those that send data: NASA
# FIRMS's VIIRS and MODIS satellites, by NORAD number. Their current element sets come from
# Space-Track (sources.read_satellites).
SATELLITES = {
    "37849": {"name": "Suomi NPP", "firms": "SNPP", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "43013": {"name": "NOAA-20", "firms": "N20", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "54234": {"name": "NOAA-21", "firms": "N21", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "25994": {"name": "Terra", "firms": "Terra", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "27424": {"name": "Aqua", "firms": "Aqua", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
}

# SMHI's stations with the flow every 15 minutes (hydroobs parameter 2), all in Nyköpingsån's
# catchment; Hallbosjön lies just south of the municipality.
FLOW_STATIONS = {
    "2614": "Hebylund Kvarnsjön",
    "2587": "Sibro 2",
    "1273": "Hallbosjön",
}
# SMHI's hourly rain (metobs parameter 7): only Floda A, 11 km west of Flen.
RAIN_STATIONS = {"96040": "Floda A"}

# Proposals, to be tuned with the municipality: a flow is high above the 99th percentile of the
# station's daily flows in SMHI's corrected archive, at two readings in a row, and a record above
# the archive's highest daily flow. Rain of at least RAIN_CONFIRM_MM in 24 hours at a rain station
# confirms a high flow as a second source.
FLOW_HIGH_PERCENTILE = 99.0
RAIN_CONFIRM_MM = 10.0

# NASA FIRMS's near-real-time fire detections over BBOX (needs ~/.firms_map_key or FIRMS_MAP_KEY).
# Proposals, as the flow limits: a cloudburst when SMHI's radar estimates at least CLOUDBURST_MM_H
# somewhere in the municipality, confirmed by CLOUDBURST_GAUGE_MM in the last hour at a rain station
# or a warning; raised fire risk when SMHI's fire risk class (FWI, or grass fire) is at least
# FIRE_RISK_CLASS today or tomorrow, at FIRE_RISK_POINT.
CLOUDBURST_MM_H = 20.0
CLOUDBURST_GAUGE_MM = 10.0
FIRE_RISK_CLASS = 5
FIRE_RISK_POINT = CENTRE
FORECAST_POINT = CENTRE
# MCF's (formerly MSB's) flood maps of Nyköpingsån, as in the Flen scenarios
# (app/backend/scenarios/flenkommun2024.py): the climate-adapted 100-year flow.
FLOOD_HAZARD_WMS = {
    "url": "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer",
    "layers": "12",
    "label": "100-årsflöde, klimatanpassat (MCF)",
    "attribution": "Översvämningskartering © MCF (tidigare MSB)",
}

FIRMS_SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT")
FIRMS_DAYS = 2
# Detections within this distance belong to the same fire.
FIRE_CLUSTER_KM = 1.0
# Known heat sources that are not fires in the open (industry, power plants), as
# (name, latitude, longitude, radius in km). None is entered for Flens kommun yet.
KNOWN_HEAT_SOURCES: list[tuple[str, float, float, float]] = []
# Days with planned fires, as (month, day, name): a fire then is not dismissed, but marked as
# possibly planned.
FIRE_CALENDAR = ((4, 30, "valborgsmässoafton"),)

# Who is to be contacted by kind of event, by role only: names and numbers stay out of the
# repository. AN EXAMPLE, not agreed with the municipality or the rescue service.
CONTACTS_NOTE = "Exempel – inte överenskommet med kommunen eller räddningstjänsten"
CONTACTS = {
    "flood": ["Räddningstjänstens inre befäl i beredskap", "Kommunens tjänsteperson i beredskap (TiB)",
              "Kommunens VA-ansvarige i beredskap", "Länsstyrelsens tjänsteperson i beredskap"],
    "fire": ["Räddningstjänstens inre befäl i beredskap", "Kommunens tjänsteperson i beredskap (TiB)",
             "Länsstyrelsens tjänsteperson i beredskap"],
    "erosion": ["Kommunens tjänsteperson i beredskap (TiB)", "SGI:s tjänsteperson i beredskap"],
    "landslide": ["Räddningstjänstens inre befäl i beredskap", "Kommunens tjänsteperson i beredskap (TiB)",
                  "SGI:s tjänsteperson i beredskap"],
    "vma": ["Kommunens tjänsteperson i beredskap (TiB)", "Räddningstjänstens inre befäl i beredskap"],
}
