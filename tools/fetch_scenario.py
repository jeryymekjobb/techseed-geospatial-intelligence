#!/usr/bin/env python3
"""Fetch and build one scenario's data from its sources, for installing the demo from Git.

    .venv/bin/python -m tools.fetch_scenario flen2019 --list     # the plan, nothing fetched
    .venv/bin/python -m tools.fetch_scenario flen2019            # fetch what is missing, after a question
    .venv/bin/python -m tools.fetch_scenario flen2019 --tools native --with-optional

The steps are the existing tools/fetch_*, build_*, load_postgis and derive_* tools, in the
order their inputs need (the inventory in reports/2026-10-22-datahamtning-per-scenario-claude-opus-5-5.md),
with their arguments taken from the scenario module. --list shows each step, the account and
Python packages it needs and whether they are there, a rough size and whether its output is
already there; nothing is fetched. A run shows the same plan and asks before fetching (--yes
answers it, and without a terminal it is needed). It checks the accounts, packages and, with
--tools native, the programs (GDAL, osmium, tilemaker) first, skips each
step whose output is already there (so an interrupted run goes on where it stopped; --force
redoes them), stops at the first failing step and ends with tools/startup_check.

Accounts are the user's own and stay outside the repository: their files are only checked
to exist, never read or shown. MET Norway's forecasts are optional (--with-optional); every
other step makes data the scenario's screens need. The database step needs PostgreSQL with
PostGIS running (docker compose, or TECHSEED_DB_MODE=native) and always runs, as it replaces
the scenario's tables. Sizes are estimates from earlier fetches, not measured for every scenario.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from app.backend.scenarios import AVAILABLE, REPO_ROOT
from tools import geo_tools

PYTHON = sys.executable
DATA = REPO_ROOT / "data"
OSM_EXTRACT = DATA / "osm" / "sweden-latest.osm.pbf"
OSM_EXTRACT_URL = "https://download.openstreetmap.fr/extracts/europe/sweden-latest.osm.pbf"
USER_AGENT = "techseed-geospatial-intelligence/0.1 (demo installation)"

# The users' own accounts, by the files the tools read (never read here, only found).
ACCOUNTS = {
    "space-track": (Path.home() / ".spacetrackrc", "Space-Track (satellite orbits), guide section 2"),
    "copernicus-cds": (Path.home() / ".cdsapirc", "Copernicus CDS (ERA5-Land and ERA5), guide section 2"),
    "eumetsat": (Path.home() / ".eumdac" / "credentials", "EUMETSAT Data Store (Meteosat), guide section 2"),
    "lsa-saf": (Path.home() / ".netrc", "LSA SAF (Meteosat fire products, ~/.netrc), guide section 2"),
}
# Python packages beyond the demo's own, by the requirements file that installs them.
PACKAGES = {
    "tools/requirements-era5.txt": ("cdsapi", "netCDF4"),
    "tools/requirements-meteosat.txt": ("h5py", "eumdac", "eccodes"),
    "tools/requirements-terrain.txt": ("pydelatin", "quantized_mesh_encoder"),
    "tools/requirements-data.txt": ("PIL", "numpy"),
    "netCDF4": ("netCDF4",),
}
# The fire scenarios' SMHI stations are not in their modules (the guide's sections 4 and 23).
FIRE_WEATHER = {
    "ljusdal2018": {"stations": ["114410", "124030"], "spinup": ("114410", "2018-05-01", "2018-07-11")},
}


@dataclass
class Step:
    key: str
    title: str
    command: list[str] | None  # None: a step run here (the OSM extract), or one that cannot run (see note)
    marker: Path | None  # its output; None: always run
    account: str | None = None
    packages: tuple[str, ...] = ()
    optional: bool = False
    programs: tuple[str, ...] = ()  # needed on PATH (--tools native)
    size_mb: float | None = None
    note: str = ""
    env: dict[str, str] = field(default_factory=dict)

    def done(self) -> bool:
        return self.marker is not None and self.marker.is_file() and self.marker.stat().st_size > 0


GDAL = ("gdalwarp", "gdal_translate", "gdalbuildvrt")
IMAGES = PACKAGES["tools/requirements-data.txt"]  # the steps that write images with Pillow


def native(tools: str, *programs: str) -> tuple[str, ...]:
    """The programs a step needs on PATH: none in Docker, which brings its own."""
    return programs if tools == "native" else ()


def module(name: str):
    return importlib.import_module(f"app.backend.scenarios.{name}")


def tool(name: str, *args: str) -> list[str]:
    return [PYTHON, "-m", f"tools.{name}", *args]


def smhi_period(end: date, today: date | None = None) -> str:
    """SMHI's corrected archive lags some months behind; recent data come from the latest months."""
    today = today or datetime.now(timezone.utc).date()
    return "latest-months" if (today - end).days < 120 else "corrected-archive"


def radar_dates(settings) -> tuple[str, str, str]:
    """The radar over the playback, every 10 minutes, or every 30 for a playback over two weeks."""
    first, last = settings.PLAYBACK_START.date(), (settings.PLAYBACK_END - timedelta(days=1)).date()
    return first.isoformat(), last.isoformat(), "30" if (last - first).days > 14 else "10"


def steps(name: str, tools: str = "docker") -> list[Step]:
    """The scenario's steps in order; only those that apply to it."""
    s = module(name)
    get = lambda attribute, default=None: getattr(s, attribute, default)  # noqa: E731
    west, south, east, north = s.MAP_BBOX
    period = (s.PERIOD_START.isoformat(), s.PERIOD_END.isoformat())
    terrain_packages = PACKAGES["tools/requirements-terrain.txt"] if tools == "native" else ()
    tiles = DATA / "tiles" / s.TILES_FILE
    plan = [
        Step("web-vendor", "Webbibliotek (Cesium, satellite.js)", tool("fetch_web_vendor"),
             REPO_ROOT / "app/frontend/vendor/cesium-1.146.0/Cesium.js", size_mb=40),
        Step("voices", "Röster för uppläsningen (Piper)", tool("fetch_piper_voices"),
             DATA / "voices" / "sv_SE-alma-medium.onnx", size_mb=121),
    ]
    if not (tiles.is_file() and tiles.stat().st_size > 0):
        plan.append(Step("osm-extract", "OpenStreetMap-utdrag för Sverige", None, OSM_EXTRACT, size_mb=930,
                         note="behövs bara för att bygga offlinekartan"))
    plan += [
        Step("dem", "Höjddata (Copernicus DEM GLO-30)", tool("fetch_copernicus_dem"), Path(s.DEM_DIR) / "SOURCE.json", size_mb=100),
        Step("terrain", "3D-terräng", tool("build_terrain", "--tools", tools), Path(s.TERRAIN_DIR) / "layer.json",
             packages=terrain_packages, programs=native(tools, "gdalbuildvrt", "gdal_translate"), size_mb=12),
        Step("tiles", "Offlinekarta", tool("build_offline_tiles", "--tools", tools), tiles, size_mb=15,
             programs=native(tools, "osmium", "tilemaker"),
             note="--tools native kräver tilemaker; på Windows tas kartan ur datapaketet" if tools == "native" else ""),
        Step("tle", "Satellitbanor (Space-Track)", tool("fetch_tle_history"), Path(s.TLE_DIR) / s.TLE_FILE_NAME,
             account="space-track", size_mb=1),
    ]
    weather = Path(s.WEATHER_DIR)
    stations = list((get("RAIN_STATIONS") or {}).keys())
    if stations:
        plan.append(Step("smhi-weather", "SMHI:s regnmätare", tool(
            "fetch_smhi_weather", *stations, "--period", smhi_period(s.PERIOD_END), "--parameters", "7",
            "--start", period[0], "--end", period[1], "--out", str(weather)), weather / "stations.json", size_mb=1))
    elif name in FIRE_WEATHER:
        fire = FIRE_WEATHER[name]
        plan.append(Step("smhi-weather", "SMHI:s väderstationer", tool(
            "fetch_smhi_weather", *fire["stations"], "--start", period[0], "--end", period[1], "--out", str(weather)),
            weather / "stations.json", size_mb=1))
        station, first, last = fire["spinup"]
        plan.append(Step("smhi-spinup", "SMHI:s väder före branden (brandrisk)", tool(
            "fetch_smhi_weather", station, "--start", first, "--end", last, "--out", str(weather / "spinup")),
            weather / "spinup" / "stations.json", size_mb=1))
    else:
        plan.append(Step("smhi-weather", "SMHI:s väderstationer", None, weather / "stations.json",
                         note="spåras i git (weather_data/smhi/README.md)"))
    if get("DAILY_RAIN_STATIONS") and get("DAILY_RAIN_DIR"):
        plan.append(Step("smhi-daily", "SMHI:s dygnsnederbörd", tool("fetch_smhi_daily", "--period", smhi_period(s.PERIOD_END)),
                         Path(s.DAILY_RAIN_DIR) / "stations.json", size_mb=1))
    if get("HYDRO_STATIONS") and get("HYDRO_DIR"):
        plan.append(Step("smhi-hydro", "SMHI:s vattenföring", tool("fetch_smhi_hydro"), Path(s.HYDRO_DIR) / "stations.json", size_mb=2))
    if get("RADAR_DIR"):
        first, last, step = radar_dates(s)
        plan.append(Step("smhi-radar", "SMHI:s väderradar", tool(
            "fetch_smhi_radar", "--start", first, "--end", last, "--step", step, "--out", str(s.RADAR_DIR)),
            Path(s.RADAR_DIR) / "SOURCE.json", packages=IMAGES, size_mb=60))
    if get("LIGHTNING_DIR"):
        plan.append(Step("lightning", "SMHI:s blixtar", tool("fetch_smhi_lightning"), Path(s.LIGHTNING_DIR) / "SOURCE.json", size_mb=5))
    area = f"{north},{west},{south},{east}"
    era5_raw = Path(s.WIND_FILE).parent / "raw"
    if str(s.WIND_FILE).startswith(str(DATA)):
        plan.append(Step("era5-land", "Vind (ERA5-Land)", tool(
            "fetch_era5_land", "--area", area, "--start", period[0], "--end", period[1],
            "--raw-dir", str(era5_raw), "--out", str(s.WIND_FILE)),
            Path(s.WIND_FILE), account="copernicus-cds", packages=PACKAGES["tools/requirements-era5.txt"], size_mb=20))
    else:
        plan.append(Step("era5-land", "Vind (ERA5-Land)", None, Path(s.WIND_FILE), note="spåras i git (weather_data/era5-land/README.md)"))
    if get("WIND_SEA_FILE"):
        plan.append(Step("era5-sea", "Vind över havet (ERA5)", tool(
            "fetch_era5_sea", "--area", area, "--start", period[0], "--end", period[1], "--land", str(s.WIND_FILE),
            "--raw-dir", str(Path(s.WIND_SEA_FILE).parent / "raw"), "--out", str(s.WIND_SEA_FILE)),
            Path(s.WIND_SEA_FILE), account="copernicus-cds", packages=PACKAGES["tools/requirements-era5.txt"], size_mb=10))
    osm_box = f"{south},{west},{north},{east}"
    for key, title, attribute, tool_name in (("osm-terrain", "Marktäcke (OpenStreetMap)", "TERRAIN_FILE", "fetch_osm_terrain"),
                                              ("osm-targets", "Byggnader och vägar (OpenStreetMap)", "TARGETS_FILE", "fetch_osm_targets")):
        target = Path(getattr(s, attribute))
        if str(target).startswith(str(DATA)):
            plan.append(Step(key, title, tool(tool_name, "--bbox", osm_box, "--out", str(target)), target, size_mb=10))
        else:
            plan.append(Step(key, title, None, target, note="spåras i git (osm_data/README.md)"))
    if get("LANDSAT_SCENES"):
        plan.append(Step("landsat", "Landsat-bilder", tool("fetch_landsat_scene", "--tools", tools),
                         Path(s.LANDSAT_DIR) / "SOURCE.json", programs=native(tools, *GDAL), packages=IMAGES, size_mb=100))
    if get("SENTINEL2_SCENES"):
        plan.append(Step("sentinel2", "Sentinel-2-bilder", tool("fetch_sentinel2_scene", "--tools", tools),
                         Path(s.SENTINEL2_DIR) / "SOURCE.json", programs=native(tools, *GDAL), packages=IMAGES, size_mb=60, note="det långsammaste steget"))
    if get("EMS_AREA") and get("EMS_DIR"):
        plan.append(Step("ems", "Copernicus EMS-ytor", tool("fetch_ems_perimeters", "--tools", tools),
                         Path(s.EMS_DIR) / "perimeters.geojson", programs=native(tools, "ogr2ogr"), size_mb=5))
    if get("MUNICIPAL_WMS") and get("MUNICIPAL_DIR"):
        plan.append(Step("municipal-features", "Kommunens skyfallsytor", tool("fetch_municipal_features"),
                         Path(s.MUNICIPAL_DIR) / "critical-stormwater.geojson", size_mb=5))
    if get("FLOOD_HAZARD_WMS") and get("MCF_DIR"):
        plan.append(Step("mcf", "MCF:s översvämningskarteringar", tool("fetch_mcf_flood_maps"),
                         Path(s.MCF_DIR) / "mcf-100ar.geojson", size_mb=5))
    if get("SENTINEL1_ACQUISITIONS"):
        plan.append(Step("sentinel1", "Sentinel-1-radarbilder (efter OSM och höjddata)", tool("fetch_sentinel1_scene", "--tools", tools),
                         Path(s.SENTINEL1_DIR) / "SOURCE.json", programs=native(tools, *GDAL), packages=IMAGES, size_mb=50))
    if get("MUNICIPAL_BASEMAP") and get("MUNICIPAL_BASEMAP_DIR"):
        plan.append(Step("municipal-basemap", "Kommunens karta (Kartan)", tool("fetch_municipal_basemap"),
                         Path(s.MUNICIPAL_BASEMAP_DIR) / "SOURCE.json", packages=IMAGES, size_mb=1100, note="2–3 timmar; fortsätter där den stannade"))
    if get("MET_FORECAST_DIR"):
        plan.append(Step("met-forecasts", "MET Norways prognoser", tool("fetch_met_forecasts"), Path(s.MET_FORECAST_DIR) / "SOURCE.json",
                         packages=PACKAGES["netCDF4"], optional=True, size_mb=30, note="20–120 minuter"))
    for key, title, attribute, account in (
            ("meteosat-frp", "Meteosats brandpixlar (LSA SAF)", "METEOSAT_FRP_FILE", "lsa-saf"),
            ("meteosat-frm", "Brandrisk (LSA SAF)", "METEOSAT_FRM_FILE", "lsa-saf"),
            ("meteosat-cth", "Meteosats molntoppar", "METEOSAT_CTH_FILE", "eumetsat"),
            ("meteosat-clm", "Meteosats molnmask (efter satellitbilderna)", "METEOSAT_CLM_FILE", "eumetsat"),
            ("meteosat-li", "Meteosats blixtar (MTG)", "METEOSAT_LI_FILE", "eumetsat"),
            ("meteosat-gii", "Meteosats instabilitet (MTG)", "METEOSAT_GII_FILE", "eumetsat")):
        if get(attribute):
            plan.append(Step(key, title, tool(f"fetch_{key.replace('-', '_')}"), Path(getattr(s, attribute)), account=account,
                             packages=PACKAGES["tools/requirements-meteosat.txt"], size_mb=50))
    plan.append(Step("postgis", "Databasen (PostGIS)", tool("load_postgis"), None,
                     note="kräver PostgreSQL med PostGIS igång; ersätter scenariots tabeller"))
    if get("ROUTE_EXPOSURE_FILE"):
        plan.append(Step("route-exposure", "Vägar och järnvägar under radarregnet", tool("derive_route_exposure"),
                         Path(s.ROUTE_EXPOSURE_FILE), packages=IMAGES, size_mb=5))
    if get("RADAR_SENSOR_FILE"):
        plan.append(Step("radar-sensors", "Givare fyllda med radarregn", tool("derive_radar_sensor_points"), Path(s.RADAR_SENSOR_FILE), size_mb=1))
    if get("LEVEL_SENSOR_FILE"):
        # Two tools write the same file: by the rivers where the scenario names them, else at the reported damage.
        derive = "derive_level_sensor_points" if get("LEVEL_SENSOR_RIVERS") else "derive_impact_sensor_points"
        plan.append(Step("level-sensors", "Syntetiska nivågivare (efter databasen)", tool(derive), Path(s.LEVEL_SENSOR_FILE), size_mb=1))
    for item in plan:
        item.env = {"TECHSEED_SCENARIO": name, "TECHSEED_TOOLS": tools}
    return plan


def missing_packages(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if importlib.util.find_spec(name) is None]


def requirements_for(names: tuple[str, ...]) -> str:
    for path, packages in PACKAGES.items():
        if path.endswith(".txt") and set(names) <= set(packages):
            return f"pip install -r {path}"
    return "pip install " + " ".join(names)


def selected(plan: list[Step], with_optional: bool) -> list[Step]:
    return [step for step in plan if with_optional or not step.optional]


def problems(plan: list[Step], force: bool = False) -> list[str]:
    """What stops the steps that still have to run: a missing account or Python package, or a step that cannot run here."""
    found = []
    for step in plan:
        if step.done() and not force:
            continue
        if step.account and not ACCOUNTS[step.account][0].is_file():
            found.append(f"{step.key}: kontot {ACCOUNTS[step.account][1]} saknas ({ACCOUNTS[step.account][0]})")
        missing = missing_packages(step.packages)
        if missing:
            found.append(f"{step.key}: Python-paketen {', '.join(missing)} saknas ({requirements_for(step.packages)})")
        absent = [program for program in step.programs if shutil.which(program) is None]
        if absent:
            hint = "ta kartan ur scenariots datapaket (guiden C och G6)" if "tilemaker" in absent else \
                "installera GDAL/osmium, till exempel från conda-forge (guiden G6), eller kör med --tools docker"
            found.append(f"{step.key}: programmen {', '.join(absent)} saknas på PATH; {hint}")
        if step.command is None and step.key != "osm-extract":
            found.append(f"{step.key}: {step.marker} saknas och hämtas inte av verktyget ({step.note})")
    return found


def describe(plan: list[Step], with_optional: bool) -> list[str]:
    lines = []
    for number, step in enumerate(plan, 1):
        state = "klart" if step.done() else "valfritt, hoppas över" if step.optional and not with_optional else "att göra"
        needs = []
        if step.account:
            needs.append(f"konto {step.account}{'' if ACCOUNTS[step.account][0].is_file() else ' (SAKNAS)'}")
        missing = missing_packages(step.packages)
        if missing:
            needs.append(f"paket {', '.join(missing)} saknas")
        size = f"~{step.size_mb:g} MB" if step.size_mb else ""
        extra = "; ".join(item for item in (", ".join(needs), size, step.note) if item)
        lines.append(f"{number:2}. [{state}] {step.title} ({step.key}){': ' + extra if extra else ''}")
    to_do = [step for step in selected(plan, with_optional) if not step.done()]
    total = sum(step.size_mb or 0 for step in to_do)
    lines.append(f"Att göra: {len(to_do)} steg, uppskattningsvis {total:g} MB att hämta och skriva (uppskattning).")
    return lines


def download(url: str, target: Path) -> None:
    """A large file, continued from where an earlier attempt stopped (HTTP Range), then renamed into place."""
    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    start = part.stat().st_size if part.is_file() else 0
    headers = {"User-Agent": USER_AGENT, **({"Range": f"bytes={start}-"} if start else {})}
    with urlopen(Request(url, headers=headers), timeout=120) as response:
        mode = "ab" if start and response.status == 206 else "wb"
        with part.open(mode) as stream:
            while block := response.read(1 << 20):
                stream.write(block)
    part.replace(target)


def run(plan: list[Step], force: bool = False, runner=subprocess.run) -> int:
    for step in plan:
        if step.done() and not force:
            print(f"– {step.title}: klart, hoppas över", flush=True)
            continue
        print(f"→ {step.title} …", flush=True)
        if step.key == "osm-extract":
            download(OSM_EXTRACT_URL, OSM_EXTRACT)
            continue
        result = runner(step.command, cwd=REPO_ROOT, env={**os.environ, **step.env})
        if result.returncode != 0:
            print(f"fetch_scenario: steget {step.key} misslyckades (kod {result.returncode}); rätta felet och kör samma kommando "
                  "igen, så fortsätter det härifrån", flush=True)
            return result.returncode or 1
        if step.marker is not None and not step.done():
            print(f"fetch_scenario: steget {step.key} skrev inte {step.marker}", flush=True)
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("scenario", choices=AVAILABLE)
    parser.add_argument("--list", action="store_true", help="show the plan; fetch nothing")
    parser.add_argument("--with-optional", action="store_true", help="also MET Norway's forecasts")
    parser.add_argument("--force", action="store_true", help="redo steps whose output is already there")
    parser.add_argument("--yes", action="store_true", help="fetch without asking first")
    geo_tools.add_argument(parser)
    args = parser.parse_args(argv)
    tools = geo_tools.choice(args.tools)
    plan = steps(args.scenario, tools)
    print(f"{args.scenario} ({'utan Docker' if tools == 'native' else 'med Docker'}):")
    for line in describe(plan, args.with_optional):
        print(line)
    stops = problems(selected(plan, args.with_optional), args.force)
    for line in stops:
        print(f"Saknas: {line}")
    if args.list:
        return 0
    if stops:
        print("fetch_scenario: inget hämtades; ordna det som saknas ovan och kör igen", flush=True)
        return 1
    if not args.yes:
        if not sys.stdin.isatty():
            print("fetch_scenario: inget hämtades; svara på frågan i en terminal eller lägg till --yes", flush=True)
            return 1
        if input("Hämta och bygga enligt planen ovan? [j/N] ").strip().lower() not in ("j", "ja", "y", "yes"):
            print("fetch_scenario: inget hämtades", flush=True)
            return 1
    code = run(selected(plan, args.with_optional), args.force)
    if code == 0:
        code = subprocess.run(tool("startup_check", args.scenario), cwd=REPO_ROOT, check=False).returncode
    return code


if __name__ == "__main__":
    raise SystemExit(main())
