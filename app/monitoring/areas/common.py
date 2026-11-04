"""What every area of the continuous monitoring shares, with Flens kommun as the template: the
satellites, the proposed limits, NASA FIRMS, Meteosat, the OpenStreetMap additions and the example
contacts. An area module takes these with `from app.monitoring.areas.common import *` and sets its
own name, municipality, county, stations, maps and data files.

An area without the municipality's own GIS (GIS_FACILITIES empty, GIS_BUILDINGS None) takes the
protected objects and the buildings from its scenarios' OpenStreetMap targets (gis.py), as the
check of laws and rules on 2026-11-03 covered Flens kommun's GIS only.
"""

from __future__ import annotations

from pathlib import Path

from app.backend.scenarios import REPO_ROOT

POLL_SECONDS = 300

# The satellites whose data the monitoring uses, as the demos show only those that send data: NASA
# FIRMS's VIIRS and MODIS satellites, and the Sentinel-1, Sentinel-2 and Landsat satellites of the
# latest images (sentinel1.py, sentinel2.py), by NORAD number (Space-Track's catalogue, checked
# 2026-11-04). Their current element sets come from Space-Track (satellites.py).
SATELLITES = {
    "37849": {"name": "Suomi NPP", "firms": "SNPP", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "43013": {"name": "NOAA-20", "firms": "N20", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "54234": {"name": "NOAA-21", "firms": "N21", "instrument": "VIIRS", "role": "FIRMS-detektioner (VIIRS)", "half_swath_km": 1520.0},
    "25994": {"name": "Terra", "firms": "Terra", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "27424": {"name": "Aqua", "firms": "Aqua", "instrument": "MODIS", "role": "FIRMS-detektioner (MODIS)", "half_swath_km": 1165.0},
    "62261": {"name": "Sentinel-1C", "firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": 125.0},
    "66315": {"name": "Sentinel-1D", "firms": None, "instrument": "SAR", "role": "Radar, ser genom moln", "half_swath_km": 125.0},
    "40697": {"name": "Sentinel-2A", "firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "42063": {"name": "Sentinel-2B", "firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "60989": {"name": "Sentinel-2C", "firms": None, "instrument": "MSI", "role": "Optisk jordobservation", "half_swath_km": 145.0},
    "39084": {"name": "Landsat 8", "firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    "49260": {"name": "Landsat 9", "firms": None, "instrument": "OLI", "role": "Optisk jordobservation", "half_swath_km": 92.5},
    # Meteosat-10 (MSG-3) at 0 degrees, whose cloud mask the monitoring shows (meteosat.py), as in the scenarios.
    "38552": {"name": "Meteosat-10", "firms": None, "instrument": "SEVIRI", "role": "Geostationär, ser området hela tiden",
              "half_swath_km": None, "geostationary": True},
}

# Proposals, to be tuned with each municipality: a flow is high above the 99th percentile of the
# station's daily flows in SMHI's corrected archive, at two readings in a row, and a record above
# the archive's highest daily flow. Rain of at least RAIN_CONFIRM_MM in 24 hours at a rain station
# confirms a high flow as a second source.
FLOW_HIGH_PERCENTILE = 99.0
RAIN_CONFIRM_MM = 10.0
# Proposals, as the flow limits: a cloudburst when SMHI's radar estimates at least CLOUDBURST_MM_H
# somewhere in the municipality, confirmed by CLOUDBURST_GAUGE_MM in the last hour at a rain station
# or a warning; raised fire risk when SMHI's fire risk class (FWI, or grass fire) is at least
# FIRE_RISK_CLASS today or tomorrow, at the area's FIRE_RISK_POINT.
CLOUDBURST_MM_H = 20.0
CLOUDBURST_GAUGE_MM = 10.0
FIRE_RISK_CLASS = 5
# The satellite monitor logs Sentinel-1's water outside the lakes from this share of the land (%), a proposal.
S1_WATER_LOG_PCT = 0.5
# Meteosat's cloud mask over the area (meteosat.py), with the EUMETSAT key in ~/.eumdac/credentials.
METEOSAT_CLM = True

# NASA FIRMS's near-real-time fire detections over BBOX (needs ~/.firms_map_key or FIRMS_MAP_KEY).
FIRMS_SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT")
FIRMS_DAYS = 2
# Detections within this distance belong to the same fire.
FIRE_CLUSTER_KM = 1.0
# Known heat sources that are not fires in the open (industry, power plants), as
# (name, latitude, longitude, radius in km). None is entered yet.
KNOWN_HEAT_SOURCES: list[tuple[str, float, float, float]] = []
# Days with planned fires, as (month, day, name): a fire then is not dismissed, but marked as
# possibly planned.
FIRE_CALENDAR = ((4, 30, "valborgsmässoafton"),)

# What an alarm may threaten without the municipality's GIS: the scenarios' OpenStreetMap targets.
GIS_FACILITIES: list[dict] = []
GIS_BUILDINGS: dict | None = None
GIS_ATTRIBUTION = "© OpenStreetMap contributors"
GIS_NOTE = ("Bygger på OpenStreetMap – kommunens GIS ingår inte förrän lagar, regler och säkerhet är "
            "genomgångna för kommunen.")
OSM_ADDITIONS = {"train_station": "Järnvägsstation", "church": "Kyrka", "chapel": "Kapell"}
OSM_ROAD_TYPES = {"primary": "större väg", "secondary": "större väg", "tertiary": "mindre väg", "unclassified": "mindre väg"}
PLACE_TYPES = ("town", "village", "hamlet")

# MCF's (formerly MSB's) flood mappings, by WMS layer, as the scenarios show them.
MCF_FLOOD_WMS = "https://gis-tjanster.mcf.se/arcgis/services/Oversvamningskarteringar/karteringar/MapServer/WMSServer"
MCF_ATTRIBUTION = "Översvämningskartering © MCF (tidigare MSB)"


# MCF's 100-year flow as polygons for what a high flow may threaten (gis.py); none without a mapping.
FLOOD_ZONE_FILES: list = []


def mcf_layer(layer: str, label: str) -> dict[str, str]:
    return {"url": MCF_FLOOD_WMS, "layers": layer, "label": label, "attribution": MCF_ATTRIBUTION}


# Who is to be contacted by kind of event, by role only: names and numbers stay out of the
# repository. AN EXAMPLE, not agreed with any municipality or rescue service.
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


def data_dir(name: str):
    """The area's unversioned state, caches and inbox."""
    return REPO_ROOT / "data" / "monitoring" / name


def built_terrain(name: str, scenarios: Path) -> Path:
    """The area's own 3D terrain over the whole municipality (tools/build_terrain.py --area) once built,
    else its scenarios' over their map area."""
    own = data_dir(name) / "terrain"
    return own if (own / "layer.json").is_file() else scenarios


def built_tiles(name: str, scenarios: tuple[str, tuple[float, ...]], bbox: tuple[float, ...]) -> tuple[str, tuple[float, ...]]:
    """The area's own offline map over the whole municipality (tools/build_offline_tiles.py --area) and
    its box once built, else its scenarios' map and their map area."""
    own = f"{name}.mbtiles"
    return (own, bbox) if (REPO_ROOT / "data" / "tiles" / own).is_file() else scenarios


def scenario_data(name: str):
    """A scenario's unversioned data, whose files an area takes (OSM targets, terrain, MCF, sensors)."""
    return REPO_ROOT / "data" / name
