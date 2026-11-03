"""Flens kommun: the first area of the continuous monitoring.

The stations are those of the Flen scenarios (app/backend/scenarios/flenkommun2024.py), checked
there on 2026-10-21; the municipality's border is MCF's (Basdata/Kommuner, kommunkod 0482). Flens
kommun's own maps are not used until the municipality allows it (CONTEXT.md), so the operator page
shows OpenStreetMap as the fallback the one-pager names.

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
