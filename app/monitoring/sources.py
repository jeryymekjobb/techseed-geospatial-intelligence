"""The live sources of the monitoring, each read through its documented open API:

- SMHI's hydrological observations, the flow every 15 minutes (hydroobs, parameter 2), and the
  statistics of each station's corrected archive of daily flows (parameter 1);
- SMHI's meteorological observations, the hourly rain (metobs, parameter 7);
- SMHI's impact-based weather warnings (ibww);
- SMHI's fire risk forecast (fwif1g, the Canadian FWI system) and point forecast (snow1g);
- SMHI's weather radar every 5 minutes (radar.py);
- Krisinformation.se's VMA and news (api.krisinformation.se/v3);
- MCF's fire bans by municipality (Eldningsforbud) and its municipal borders (Basdata/Kommuner);
- NASA FIRMS's near-real-time fire detections, with the user's MAP_KEY.

Each reader takes a fetch function (URL to bytes), so the tests run on recorded answers without
the network. A source that fails gives its error; the others go on.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.monitoring import geo

USER_AGENT = "techseed-geospatial-intelligence/0.1 (monitoring)"
HYDRO_API = "https://opendata-download-hydroobs.smhi.se/api/version/latest"
METOBS_API = "https://opendata-download-metobs.smhi.se/api/version/1.0"
WARNINGS_URL = "https://opendata-download-warnings.smhi.se/ibww/api/version/1/warning.json"
METFCST_API = "https://opendata-download-metfcst.smhi.se/api/category"
KRISINFO_API = "https://api.krisinformation.se/v3"
MCF_REST = "https://gis-tjanster.mcf.se/arcgis/rest/services"
FIRMS_API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_KEY_FILE = Path.home() / ".firms_map_key"

ATTRIBUTION = {
    "smhi_flow": "SMHI öppna data, hydrologiska observationer (CC BY 4.0 SE)",
    "smhi_rain": "SMHI öppna data, meteorologiska observationer (CC BY 4.0 SE)",
    "smhi_warnings": "SMHI:s vädervarningar, öppna data (CC BY 4.0 SE)",
    "smhi_fire_risk": "SMHI:s brandriskprognos (FWI), öppna data (CC BY 4.0 SE)",
    "smhi_forecast": "SMHI:s väderprognos, öppna data (CC BY 4.0 SE)",
    "landsat": "Landsat-data med tillstånd av U.S. Geological Survey (Microsoft Planetary Computer)",
    "meteosat_clm": "Contains modified EUMETSAT Meteosat product (MSG Cloud Mask, CC BY 4.0)",
    "sentinel1": "Innehåller bearbetade Copernicus Sentinel-data (Microsoft Planetary Computer)",
    "sentinel2": "Innehåller Copernicus Sentinel-data (Microsoft Planetary Computer)",
    "flen_gis": "Flens kommun (GIS) och OpenStreetMap – intern användning",
    "smhi_stations": "SMHI öppna data, meteorologiska observationer (CC BY 4.0 SE)",
    "smhi_grid": "SMHI:s väderprognos (snow1g), öppna data (CC BY 4.0 SE); prognos, inte observationer",
    "smhi_radar": "SMHI öppna data, väderradar (CC BY 4.0 SE); uppskattat ur radarn, inte mätt på marken",
    "krisinformation": "Krisinformation.se (MCF); villkor inte kontrollerade",
    "mcf_fire_ban": "Eldningsförbud, MCF:s spegling av länsstyrelsernas karttjänst; villkor inte kontrollerade",
    "mcf_border": "Kommungräns, MCF Basdata; villkor inte kontrollerade",
    "firms": "NASA FIRMS, nära realtid (NRT)",
}

Fetch = Callable[[str], bytes]


def fetch_url(url: str, timeout: float = 60.0) -> bytes:
    """The body of a GET; gzip is asked for and unpacked, as SMHI's forecast grid requires it."""
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}), timeout=timeout) as response:
        body = response.read()
        return gzip.decompress(body) if response.headers.get("Content-Encoding") == "gzip" else body


def _utc(milliseconds: float) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def utc_text(moment: datetime | None) -> str | None:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


@dataclass
class Result:
    """What one source gave at one poll."""
    source: str
    ok: bool
    fetched_utc: str
    items: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    note: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {"source": self.source, "ok": self.ok, "fetched_utc": self.fetched_utc, "count": len(self.items),
                "error": self.error, "note": self.note, "attribution": ATTRIBUTION.get(self.source)}


def guarded(source: str, read: Callable[[], list[dict[str, Any]]]) -> Result:
    """Run one source's reader; a failure becomes the source's error, not the monitoring's."""
    now = utc_text(datetime.now(timezone.utc))
    try:
        return Result(source, True, now, read())
    except MissingKey as error:
        return Result(source, False, now, error=str(error), note="nyckel saknas")
    except Exception as error:  # noqa: BLE001 - every failure of a source is reported the same way
        return Result(source, False, now, error=f"{type(error).__name__}: {error}")


# --- SMHI flows -------------------------------------------------------------------------------

def flow_url(station: str) -> str:
    return f"{HYDRO_API}/parameter/2/station/{station}/period/latest-day/data.json"


def read_flows(stations: dict[str, str], fetch: Fetch) -> list[dict[str, Any]]:
    """Each station's 15-minute flows of the latest day, oldest first."""
    items = []
    for station, name in stations.items():
        data = json.loads(fetch(flow_url(station)))
        position = (data.get("position") or [{}])[-1]
        readings = [{"time_utc": utc_text(_utc(row["date"])), "value": float(row["value"]), "quality": row.get("quality")}
                    for row in data.get("value") or [] if row.get("value") is not None]
        items.append({"station": station, "name": name, "latitude": position.get("latitude"),
                      "longitude": position.get("longitude"), "unit": "m³/s", "readings": readings})
    return items


def archive_url(station: str) -> str:
    return f"{HYDRO_API}/parameter/1/station/{station}/period/corrected-archive/data.csv"


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * share / 100
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def flow_statistics(station: str, text: str, high_percentile: float) -> dict[str, Any]:
    """The percentile and the highest of a station's daily flows in SMHI's corrected archive (CSV)."""
    lines = text.lstrip("﻿").splitlines()
    header = next(index for index, line in enumerate(lines) if line.startswith("Datum"))
    days = []
    for line in lines[header + 1:]:
        fields = line.split(";")
        if len(fields) >= 2 and fields[0] and fields[1]:
            days.append((fields[0][:10], float(fields[1])))
    if not days:
        raise ValueError(f"station {station}: the archive has no daily flows")
    values = [value for _, value in days]
    highest_day, highest = max(days, key=lambda item: item[1])
    return {"station": station, "high": round(percentile(values, high_percentile), 3), "high_percentile": high_percentile,
            "record": highest, "record_day": highest_day, "archive_from": days[0][0], "archive_to": days[-1][0],
            "days": len(days)}


def cached_statistics(stations: dict[str, str], high_percentile: float, path: Path, fetch: Fetch,
                      max_age: timedelta = timedelta(days=30)) -> dict[str, dict[str, Any]]:
    """The stations' statistics, fetched again when older than max_age or missing a station."""
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cached = {}
    fetched = _iso(cached.get("fetched_utc"))
    stats = cached.get("stations") or {}
    fresh = (fetched is not None and datetime.now(timezone.utc) - fetched < max_age and set(stations) <= set(stats)
             and all(item.get("high_percentile") == high_percentile for item in stats.values()))
    if fresh:
        return stats
    stats = {station: flow_statistics(station, fetch(archive_url(station)).decode("utf-8-sig"), high_percentile)
             for station in stations}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_utc": utc_text(datetime.now(timezone.utc)), "stations": stats},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    return stats


# --- SMHI rain --------------------------------------------------------------------------------

def rain_url(station: str) -> str:
    return f"{METOBS_API}/parameter/7/station/{station}/period/latest-day/data.json"


def read_rain(stations: dict[str, str], fetch: Fetch) -> list[dict[str, Any]]:
    """Each station's rain in the latest 24 hours."""
    items = []
    for station, name in stations.items():
        data = json.loads(fetch(rain_url(station)))
        position = (data.get("position") or [{}])[-1]
        rows = [row for row in data.get("value") or [] if row.get("value") not in (None, "")]
        latest = max((_utc(row["date"]) for row in rows), default=None)
        recent = [row for row in rows if latest and _utc(row["date"]) > latest - timedelta(hours=24)]
        last = max(rows, key=lambda row: row["date"]) if rows else None
        items.append({"station": station, "name": name, "latitude": position.get("latitude"),
                      "longitude": position.get("longitude"), "mm_24h": round(sum(float(row["value"]) for row in recent), 1),
                      "mm_last_hour": float(last["value"]) if last else None,
                      "series": [{"time_utc": utc_text(_utc(row["date"])), "mm": float(row["value"])}
                                 for row in sorted(recent, key=lambda row: row["date"])],
                      "hours": len(recent), "latest_utc": utc_text(latest),
                      "unchecked": any(row.get("quality") != "G" for row in recent)})
    return items


# --- SMHI's weather stations -----------------------------------------------------------------

# metobs parameters: air temperature, wind direction, wind speed, rain in the hour, rain by the day (06-06).
STATION_PARAMETERS = {1: ("temp_c", "latest-hour"), 3: ("wind_from_deg", "latest-hour"), 4: ("wind_ms", "latest-hour"),
                      7: ("rain_1h_mm", "latest-hour"), 5: ("rain_day_mm", "latest-day")}


def station_url(parameter: int, station: str, period: str) -> str:
    return f"{METOBS_API}/parameter/{parameter}/station/{station}/period/{period}/data.json"


def read_weather_stations(stations: dict[str, dict[str, Any]], fetch: Fetch) -> list[dict[str, Any]]:
    """The latest values of SMHI's weather stations: for each its parameters, the last value and its time.
    A parameter that does not answer is left out; the others go on."""
    items = []
    for station, settings in stations.items():
        item = {"station": station, "name": settings["name"], "latitude": None, "longitude": None, "values": {}, "times": {}}
        for parameter in settings["parameters"]:
            key, period = STATION_PARAMETERS[parameter]
            try:
                data = json.loads(fetch(station_url(parameter, station, period)))
            except Exception:  # noqa: BLE001 - one parameter missing leaves the others
                continue
            rows = [row for row in data.get("value") or [] if row.get("value") not in (None, "")]
            if not rows:
                continue
            # Hourly values carry their time as "date"; the rain by the day its period's end as "to".
            moment = lambda row: row.get("date") or row.get("to")  # noqa: E731
            last = max(rows, key=moment)
            item["values"][key] = float(last["value"])
            item["times"][key] = utc_text(_utc(moment(last)))
            position = (data.get("position") or [{}])[-1]
            item["latitude"], item["longitude"] = position.get("latitude"), position.get("longitude")
        if item["latitude"] is not None:
            items.append(item)
    return items


# --- SMHI warnings ----------------------------------------------------------------------------

def warning_kind(warning: dict[str, Any]) -> str:
    """The kind of event a warning concerns: flood, fire or other. Mapped from SMHI's
    classification and event codes as seen on 2026-11-03; a code not seen then counts as other."""
    event = warning.get("event") or {}
    code = (event.get("code") or "").upper()
    group = ((event.get("mhoClassification") or {}).get("code") or "").upper()
    if "FIRE" in code or "FIRE" in group:
        return "fire"
    if code == "WATER_SHORTAGE":
        return "other"
    if group == "HYD" or "FLOOD" in code or "FLOW" in code or "RAIN" in code:
        return "flood"
    return "other"


def read_warnings(county_id: int, border: dict[str, Any] | None, fetch: Fetch) -> list[dict[str, Any]]:
    """SMHI's warnings whose area is the county or overlaps the municipality's border."""
    items = []
    for warning in json.loads(fetch(WARNINGS_URL)):
        for area in warning.get("warningAreas") or []:
            in_county = any(item.get("id") == county_id for item in area.get("affectedAreas") or [])
            geometry = (area.get("area") or {}).get("geometry")
            if not (in_county or (border and geometry and geo.overlaps(geometry, border))):
                continue
            texts = [item.get("text", {}).get("sv") for item in area.get("descriptions") or [] if item.get("text")]
            items.append({"id": f"{warning.get('id')}-{area.get('id')}", "kind": warning_kind(warning),
                          "event": (warning.get("event") or {}).get("sv"),
                          "description": (area.get("eventDescription") or {}).get("sv"),
                          "level": (area.get("warningLevel") or {}).get("sv"),
                          "level_code": (area.get("warningLevel") or {}).get("code"),
                          "area": (area.get("areaName") or {}).get("sv"),
                          "start_utc": utc_text(_iso(area.get("approximateStart"))),
                          "published_utc": utc_text(_iso(area.get("published"))),
                          "text": " ".join(text for text in texts if text)})
    return items


# --- SMHI's fire risk and forecast ------------------------------------------------------------

# SMHI's classes of fire risk (fwiindex, and grassfire), 1-6; -1 outside the fire season.
FIRE_RISK_WORDS = {1: "mycket liten", 2: "liten", 3: "måttlig", 4: "stor", 5: "mycket stor", 6: "extremt stor"}


def fire_risk_url(lat: float, lon: float) -> str:
    return f"{METFCST_API}/fwif1g/version/1/daily/geotype/point/lon/{lon:.4f}/lat/{lat:.4f}/data.json"


def read_fire_risk(lat: float, lon: float, fetch: Fetch) -> list[dict[str, Any]]:
    """SMHI's fire risk by the day for the point, from today on."""
    data = json.loads(fetch(fire_risk_url(lat, lon)))
    items = []
    for step in data.get("timeSeries") or []:
        values = {item["name"]: item["values"][0] for item in step.get("parameters") or []}
        index, grass = int(values.get("fwiindex", -1)), int(values.get("grassfire", -1))
        items.append({"day_utc": step["validTime"][:10], "fwi_class": index, "fwi_word": FIRE_RISK_WORDS.get(index),
                      "grass_class": grass, "grass_word": FIRE_RISK_WORDS.get(grass), "fwi": values.get("fwi"),
                      "season": index > 0, "approved_utc": data.get("approvedTime")})
    return items


def forecast_url(lat: float, lon: float) -> str:
    return f"{METFCST_API}/snow1g/version/1/geotype/point/lon/{lon:.4f}/lat/{lat:.4f}/data.json"


def read_forecast(lat: float, lon: float, fetch: Fetch, hours: int = 48) -> list[dict[str, Any]]:
    """SMHI's forecast for the point: the rain in the next 24 and 48 hours, the most in one forecast
    step (an hour at first, longer later), the temperature's range and the strongest gust."""
    data = json.loads(fetch(forecast_url(lat, lon)))
    steps = data.get("timeSeries") or []
    if not steps:
        return []
    start = _iso(steps[0]["time"])
    def within(limit: int) -> list[dict[str, Any]]:
        return [step["data"] for step in steps if _iso(step["time"]) <= start + timedelta(hours=limit)]
    rain = lambda limit: round(sum(item.get("precipitation_amount_mean") or 0.0 for item in within(limit)), 1)  # noqa: E731
    near = within(hours)
    return [{"from_utc": utc_text(start), "rain_24h_mm": rain(24), "rain_48h_mm": rain(48),
             "max_step_mm": round(max((item.get("precipitation_amount_mean") or 0.0) for item in near), 1),
             "temp_min": min(item.get("air_temperature") for item in near), "temp_max": max(item.get("air_temperature") for item in near),
             "gust_max": max(item.get("wind_speed_of_gust") or 0.0 for item in near), "created_utc": data.get("createdTime")}]


# --- Krisinformation --------------------------------------------------------------------------

def _krisinfo_in_area(item: dict[str, Any], words: tuple[str, ...]) -> bool:
    return any(any(word.lower() in (area.get("description") or "").lower() for word in words)
               for area in item.get("area") or [])


def read_krisinformation(words: tuple[str, ...], fetch: Fetch) -> list[dict[str, Any]]:
    """VMA, and news of the last three days, whose area names the county or the municipality."""
    items = []
    for kind, url in (("vma", f"{KRISINFO_API}/vmas"), ("news", f"{KRISINFO_API}/news?days=3")):
        for item in json.loads(fetch(url)):
            if _krisinfo_in_area(item, words):
                items.append({"id": f"{kind}-{item.get('identifier')}", "kind": kind, "headline": item.get("headline"),
                              "preamble": item.get("preamble"), "published_utc": utc_text(_iso(item.get("published"))),
                              "web": item.get("web"),
                              "areas": [area.get("description") for area in item.get("area") or []]})
    return items


# --- MCF --------------------------------------------------------------------------------------

def fire_ban_url(code: str) -> str:
    query = urlencode({"where": f"KKOD='{code}'", "outFields": "KOMMUNNAMN,STATUS,STARTDATUM,BESKRIVNIN,BESL_MYND,URL,REVDATUM",
                       "returnGeometry": "false", "f": "json"})
    return f"{MCF_REST}/Eldningsforbud/Eldningsforbud/FeatureServer/0/query?{query}"


def read_fire_ban(code: str, fetch: Fetch) -> list[dict[str, Any]]:
    """The municipality's fire ban as MCF mirrors it."""
    items = []
    for feature in json.loads(fetch(fire_ban_url(code))).get("features") or []:
        values = feature.get("attributes") or {}
        items.append({"municipality": values.get("KOMMUNNAMN"), "status": values.get("STATUS"),
                      "start_utc": utc_text(_utc(values["STARTDATUM"])) if values.get("STARTDATUM") else None,
                      "description": values.get("BESKRIVNIN"), "decided_by": values.get("BESL_MYND"), "url": values.get("URL"),
                      "revised_utc": utc_text(_utc(values["REVDATUM"])) if values.get("REVDATUM") else None})
    return items


def border_url(code: str) -> str:
    query = urlencode({"where": f"kommunkod='{code}'", "outFields": "kommunkod,namnkortform", "outSR": "4326", "f": "geojson"})
    return f"{MCF_REST}/Basdata/Kommuner/FeatureServer/0/query?{query}"


def cached_border(code: str, path: Path, fetch: Fetch) -> dict[str, Any]:
    """The municipality's border (GeoJSON geometry in WGS 84), fetched once and kept."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    features = json.loads(fetch(border_url(code))).get("features") or []
    if not features:
        raise ValueError(f"MCF has no municipality {code}")
    geometry = features[0]["geometry"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(geometry), encoding="utf-8")
    return geometry


# --- NASA FIRMS -------------------------------------------------------------------------------

class MissingKey(RuntimeError):
    pass


def firms_key(environ: dict[str, str] | None = None, path: Path = FIRMS_KEY_FILE) -> str:
    """The FIRMS MAP_KEY: FIRMS_MAP_KEY, else ~/.firms_map_key. Never logged or shown."""
    key = (environ if environ is not None else os.environ).get("FIRMS_MAP_KEY", "").strip()
    if not key:
        try:
            key = path.read_text(encoding="utf-8").strip()
        except OSError:
            key = ""
    if not key:
        raise MissingKey("FIRMS MAP_KEY saknas: lägg den i ~/.firms_map_key (chmod 600) eller i FIRMS_MAP_KEY")
    return key


def firms_url(key: str, source: str, bbox: tuple[float, float, float, float], days: int) -> str:
    return f"{FIRMS_API}/{quote(key)}/{source}/{','.join(str(value) for value in bbox)}/{days}"


def _firms_rows(text: str, source: str) -> list[dict[str, Any]]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        if not row.get("latitude"):
            continue
        clock = (row.get("acq_time") or "0").zfill(4)
        moment = datetime.fromisoformat(f"{row['acq_date']}T{clock[:2]}:{clock[2:]}:00").replace(tzinfo=timezone.utc)
        rows.append({"latitude": float(row["latitude"]), "longitude": float(row["longitude"]), "time_utc": utc_text(moment),
                     "satellite": row.get("satellite"), "instrument": row.get("instrument"), "confidence": row.get("confidence"),
                     "frp": float(row["frp"]) if row.get("frp") else None, "daynight": row.get("daynight"), "source": source})
    return rows


def read_firms(key: str, sources: tuple[str, ...], bbox: tuple[float, float, float, float], days: int,
               fetch: Fetch) -> list[dict[str, Any]]:
    """FIRMS's detections over the box from each source. An answer that is not CSV (a wrong key, the
    limit reached) is an error; the key is kept out of it."""
    items = []
    for source in sources:
        text = fetch(firms_url(key, source, bbox, days)).decode("utf-8", errors="replace")
        if not text.startswith("latitude"):
            raise RuntimeError(f"FIRMS {source}: {text.replace(key, '<key>').strip()[:120]}")
        items.extend(_firms_rows(text, source))
    return items
