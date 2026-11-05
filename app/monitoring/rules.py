"""Detection: the rules that turn one poll's sources and the recent events into alarm candidates,
and the checks that keep alarms that are not needed away (the one-pager's "Minskade falsklarm").

A candidate holds its facts, each with its source and time, and marks what is uncertain. A
candidate that rests on a single source says so. Detections that a rule leaves out (a known heat
source, an event outside the municipality) are kept as filtered, with the reason, so the operator
can see them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import ModuleType
from typing import Any

from app.monitoring import geo
from app.monitoring.events import KIND_WORDS
from app.monitoring.sources import ATTRIBUTION, FIRE_RISK_WORDS

ALARM_LEVELS = ("YELLOW", "ORANGE", "RED")
SEVERITY = {"info": 0, "event": 1, "single": 1, "high": 2, "warning": 2, "confirmed": 3, "record": 3, "vma": 4}
EVENT_HOURS = 24


@dataclass
class Candidate:
    key: str
    kind: str
    severity: str
    title: str
    place: str
    latitude: float | None
    longitude: float | None
    facts: list[dict[str, Any]] = field(default_factory=list)
    confirmations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    extent: str | None = None
    exposure: dict[str, Any] | None = None

    def fact(self, text: str, source: str, time_utc: str | None = None, uncertain: bool = False) -> None:
        self.facts.append({"text": text, "source": source, "time_utc": time_utc, "uncertain": uncertain})

    def as_json(self) -> dict[str, Any]:
        return {"key": self.key, "kind": self.kind, "kind_word": KIND_WORDS.get(self.kind, self.kind.upper()),
                "severity": self.severity, "title": self.title, "place": self.place, "latitude": self.latitude,
                "longitude": self.longitude, "facts": self.facts, "confirmations": self.confirmations,
                "single_source": not self.confirmations, "notes": self.notes,
                "extent": self.extent, "exposure": self.exposure}


def _number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _flood_support(rain: list[dict[str, Any]], warnings: list[dict[str, Any]], area: ModuleType) -> list[str]:
    support = [f"Regn {_number(item['mm_24h'])} mm senaste 24 h vid {item['name']} (SMHI)"
               for item in rain if item["mm_24h"] >= area.RAIN_CONFIRM_MM]
    support += [f"SMHI-varning: {item['description'] or item['event']} ({item['level']}, {item['area']})"
                for item in warnings if item["kind"] == "flood" and item["level_code"] in ALARM_LEVELS]
    return support


def flow_candidates(flows: list[dict[str, Any]], stats: dict[str, dict[str, Any]], rain: list[dict[str, Any]],
                    warnings: list[dict[str, Any]], area: ModuleType) -> list[Candidate]:
    """A high flow at two readings in a row, a record at the latest."""
    found = []
    for station in flows:
        limits = stats.get(station["station"])
        limits = None if limits and limits.get("missing") else limits
        readings = station["readings"]
        if not limits or len(readings) < 2:
            continue
        last, before = readings[-1], readings[-2]
        if not (last["value"] > limits["high"] and before["value"] > limits["high"]):
            continue
        record = last["value"] > limits["record"]
        item = Candidate(f"flow-{station['station']}", "flood", "record" if record else "high",
                         f"{'Rekordflöde' if record else 'Högt flöde'} vid {station['name']}", station["name"],
                         station["latitude"], station["longitude"])
        source = ATTRIBUTION["smhi_flow"]
        item.fact(f"Vattenföring {_number(last['value'])} m³/s", source, last["time_utc"], uncertain=last["quality"] != "G")
        item.fact(f"Föregående avläsning {_number(before['value'])} m³/s", source, before["time_utc"],
                  uncertain=before["quality"] != "G")
        item.fact(f"Gräns för högt flöde {_number(limits['high'])} m³/s: {_number(limits['high_percentile'])}:e "
                  f"percentilen av dygnsflödena {limits['archive_from']}–{limits['archive_to']}", source)
        item.fact(f"Högsta dygnsflöde i arkivet {_number(limits['record'])} m³/s ({limits['record_day']})", source)
        if any(reading["quality"] != "G" for reading in (last, before)):
            item.notes.append("Flödena är preliminära och inte granskade av SMHI.")
        item.notes.append("Gränserna jämför 15-minutersvärden med dygnsmedelvärden och är ett förslag, inte överenskomna.")
        item.extent = f"{_number(last['value'] / limits['high'])} gånger gränsen för högt flöde"
        item.confirmations = _flood_support(rain, warnings, area)
        found.append(item)
    return found


def station_rain_candidates(stations: list[dict[str, Any]], area: ModuleType) -> list[Candidate]:
    """Heavy rain at a weather station: at least CLOUDBURST_GAUGE_MM in its latest hour."""
    found = []
    for station in stations:
        rain = station["values"].get("rain_1h_mm")
        if rain is None or rain < area.CLOUDBURST_GAUGE_MM:
            continue
        item = Candidate(f"rain-{station['station']}", "flood", "high", f"Kraftigt regn vid {station['name']}: {_number(rain)} mm på en timme",
                         station["name"], station["latitude"], station["longitude"])
        item.fact(f"Regn {_number(rain)} mm senaste timmen", ATTRIBUTION["smhi_stations"], station["times"].get("rain_1h_mm"),
                  uncertain=True)
        item.fact(f"Gräns i övervakningen: {_number(area.CLOUDBURST_GAUGE_MM)} mm på en timme", "Förslag, inte överenskommet")
        item.notes.append("Senaste timmens värde är inte kvalitetsgranskat av SMHI.")
        found.append(item)
    return found


def sea_level_candidates(stations: list[dict[str, Any]], area: ModuleType) -> list[Candidate]:
    """A high sea level: the latest hour at or above the area's SEA_LEVEL_HIGH_CM (a proposal)."""
    found = []
    limit = getattr(area, "SEA_LEVEL_HIGH_CM", None)
    for station in stations:
        value = station.get("value_cm")
        if limit is None or value is None or value < limit:
            continue
        item = Candidate(f"sea-{station['station']}", "flood", "high", f"Högt vattenstånd vid {station['name']}: {_number(value)} cm",
                         station["name"], station["latitude"], station["longitude"])
        item.fact(f"Havsvattenstånd {_number(value)} cm i RH2000", ATTRIBUTION["smhi_sea_level"], station["time_utc"],
                  uncertain=station["unchecked"])
        item.fact(f"Gräns i övervakningen: {_number(limit)} cm i RH2000", "Förslag, som Falsterbo-scenariot, inte överenskommet")
        item.extent = f"{_number(value - limit)} cm över gränsen"
        found.append(item)
    return found


def water_level_candidates(stations: list[dict[str, Any]]) -> list[Candidate]:
    """A water level above the highest in SMHI's archive (one value a day; the height system not named)."""
    found = []
    for station in stations:
        value, record = station.get("value_cm"), station.get("record_cm")
        if station.get("silent") or value is None or record is None or value <= record:
            continue
        item = Candidate(f"level-{station['station']}", "flood", "record", f"Rekordhögt vattenstånd vid {station['name']}: {_number(value / 100)} m",
                         station["name"], station["latitude"], station["longitude"])
        item.fact(f"Vattenstånd {_number(value / 100)} m (ett värde per dygn)", ATTRIBUTION["smhi_water_level"], station["time_utc"],
                  uncertain=station["unchecked"])
        item.fact(f"Högsta i arkivet {_number(record / 100)} m ({station['record_day']}, sedan {station['archive_from']})", ATTRIBUTION["smhi_water_level"])
        item.extent = f"{_number(value - record)} cm över arkivets högsta"
        found.append(item)
    return found


def warning_candidates(warnings: list[dict[str, Any]]) -> list[Candidate]:
    """SMHI's yellow, orange and red warnings for flood and fire in the area."""
    found = []
    for warning in warnings:
        if warning["kind"] not in ("flood", "fire") or warning["level_code"] not in ALARM_LEVELS:
            continue
        item = Candidate(f"warning-{warning['id']}", warning["kind"], "warning",
                         f"SMHI-varning: {warning['description'] or warning['event']}", warning["area"] or "", None, None)
        item.fact(f"{warning['level']} varning: {warning['description'] or warning['event']}", ATTRIBUTION["smhi_warnings"],
                  warning["published_utc"])
        if warning["text"]:
            item.fact(warning["text"], ATTRIBUTION["smhi_warnings"], warning["published_utc"])
        item.confirmations = ["SMHI:s varning är en bedömning, inte en mätning"]
        found.append(item)
    return found


def vma_candidates(krisinfo: list[dict[str, Any]], area: ModuleType) -> list[Candidate]:
    found = []
    for item in krisinfo:
        if item["kind"] != "vma":
            continue
        candidate = Candidate(item["id"], "vma", "vma", f"VMA: {item['headline']}", ", ".join(a for a in item["areas"] if a),
                              None, None)
        candidate.fact(item["headline"] or "", ATTRIBUTION["krisinformation"], item["published_utc"])
        if item["preamble"]:
            candidate.fact(item["preamble"], ATTRIBUTION["krisinformation"], item["published_utc"])
        candidate.confirmations = ["Utfärdat VMA"]
        found.append(candidate)
    return found


def cloudburst_candidates(radar: dict[str, Any] | None, rain: list[dict[str, Any]], warnings: list[dict[str, Any]],
                          area: ModuleType) -> list[Candidate]:
    """A cloudburst when SMHI's radar estimates at least CLOUDBURST_MM_H in the municipality."""
    if not radar or not radar.get("frames") or radar["max_mm_h"] < area.CLOUDBURST_MM_H:
        return []
    lat, lon = radar["max_at"]
    item = Candidate("radar-cloudburst", "flood", "high", f"Skyfall enligt radarn: {_number(radar['max_mm_h'])} mm/h", area.NAME, lat, lon)
    source = ATTRIBUTION["smhi_radar"]
    item.fact(f"Regnintensitet {_number(radar['max_mm_h'])} mm/h vid {lat:.3f} N, {lon:.3f} E", source, radar["latest_utc"], uncertain=True)
    item.fact(f"Som mest {_number(radar['hour_mm'])} mm den senaste timmen ({radar['frames']} radarbilder)", source,
              radar["latest_utc"], uncertain=True)
    item.fact(f"Gräns för skyfall i övervakningen: {_number(area.CLOUDBURST_MM_H)} mm/h", "Förslag, inte överenskommet")
    item.extent = f"{_number(radar['hour_mm'])} mm den senaste timmen där det regnat mest"
    item.confirmations = [f"{station['name']}: {_number(station['mm_last_hour'])} mm senaste timmen (SMHI)" for station in rain
                          if station.get("mm_last_hour") is not None and station["mm_last_hour"] >= area.CLOUDBURST_GAUGE_MM]
    item.confirmations += [f"SMHI-varning: {warning['description'] or warning['event']} ({warning['level']})" for warning in warnings
                           if warning["kind"] == "flood" and warning["level_code"] in ALARM_LEVELS]
    item.notes.append("Radarn uppskattar regnet ur reflektiviteten; hagel och smältande snö kan ge för höga värden.")
    return [item]


def fire_risk_candidates(fire_risk: list[dict[str, Any]], area: ModuleType, now: datetime) -> list[Candidate]:
    """Raised fire risk when SMHI's class is at least FIRE_RISK_CLASS today or tomorrow (UTC)."""
    found = []
    days = {now.date().isoformat(), (now + timedelta(days=1)).date().isoformat()}
    for day in (entry for entry in fire_risk if entry["day_utc"] in days):
        worst = max(day["fwi_class"], day["grass_class"])
        if worst < area.FIRE_RISK_CLASS:
            continue
        word = FIRE_RISK_WORDS[worst]
        lat, lon = area.FIRE_RISK_POINT
        item = Candidate(f"fire-risk-{day['day_utc']}", "fire", "warning", f"Förhöjd brandrisk {day['day_utc']}: {word}", area.NAME,
                         lat, lon)
        if day["fwi_word"]:
            item.fact(f"Brandrisk i skog (FWI) {day['day_utc']}: {day['fwi_word']} (klass {day['fwi_class']})",
                      ATTRIBUTION["smhi_fire_risk"], day["approved_utc"])
        if day["grass_word"]:
            item.fact(f"Gräsbrandsrisk {day['day_utc']}: {day['grass_word']} (klass {day['grass_class']})",
                      ATTRIBUTION["smhi_fire_risk"], day["approved_utc"])
        item.confirmations = ["SMHI:s brandriskprognos är en prognos, inte en observation"]
        item.notes.append(f"Prognosen gäller en punkt i kommunen ({lat:.2f} N, {lon:.2f} E).")
        found.append(item)
    return found


def _clusters(points: list[dict[str, Any]], km: float) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for point in sorted(points, key=lambda item: item["time_utc"]):
        for group in groups:
            if any(geo.distance_km(point["latitude"], point["longitude"], other["latitude"], other["longitude"]) <= km
                   for other in group):
                group.append(point)
                break
        else:
            groups.append([point])
    return groups


def fire_candidates(firms: list[dict[str, Any]], events: list[dict[str, Any]], border: dict[str, Any] | None,
                    fire_ban: list[dict[str, Any]], area: ModuleType, filtered: list[dict[str, Any]],
                    fire_risk: list[dict[str, Any]] | None = None) -> list[Candidate]:
    """Fires from FIRMS in the municipality, a cluster per fire. Known heat sources are left out;
    the calendar and the fire ban are given as context."""
    points = []
    for point in firms:
        if border and not geo.contains(border, point["latitude"], point["longitude"]):
            continue
        heat = next((name for name, lat, lon, radius in area.KNOWN_HEAT_SOURCES
                     if geo.distance_km(point["latitude"], point["longitude"], lat, lon) <= radius), None)
        if heat:
            filtered.append({"what": f"FIRMS {point['satellite']} {point['time_utc']}", "reason": f"känd värmekälla: {heat}",
                             "latitude": point["latitude"], "longitude": point["longitude"]})
            continue
        points.append(point)
    found = []
    for group in _clusters(points, area.FIRE_CLUSTER_KM):
        first = group[0]
        lat = sum(point["latitude"] for point in group) / len(group)
        lon = sum(point["longitude"] for point in group) / len(group)
        item = Candidate(f"fire-{first['latitude']:.3f}-{first['longitude']:.3f}-{first['time_utc'][:10]}", "fire", "single",
                         f"Möjlig brand ({len(group)} detektion{'er' if len(group) > 1 else ''})", area.NAME, lat, lon)
        for point in group:
            confidence = str(point.get("confidence") or "").lower()
            # VIIRS gives l, n or h; MODIS a number from 0 to 100, low below 30.
            low = confidence in ("l", "low") or (confidence.isdigit() and int(confidence) < 30)
            item.fact(f"Värmedetektion {point['instrument']} ({point['satellite']}), konfidens {point['confidence']}"
                      + (f", {_number(point['frp'])} MW" if point.get("frp") is not None else ""),
                      ATTRIBUTION["firms"], point["time_utc"], uncertain=low)
        passes = {point["time_utc"] for point in group}
        satellites = {point["satellite"] for point in group}
        if len(passes) > 1:
            item.confirmations.append(f"Samma plats vid {len(passes)} passager")
        if len(satellites) > 1:
            item.confirmations.append(f"Sett av {len(satellites)} satelliter")
        for event in events:
            if event["kind"] == "fire" and geo.distance_km(event["latitude"], event["longitude"], lat, lon) <= area.FIRE_CLUSTER_KM:
                item.confirmations.append(f"Rapport: {event['source']}")
        if item.confirmations:
            item.severity = "confirmed"
        item.extent = f"{len(group)} detektioner inom {_number(area.FIRE_CLUSTER_KM)} km"
        _fire_context(item, first["time_utc"], fire_ban, area, fire_risk)
        found.append(item)
    return found


def _fire_context(item: Candidate, time_utc: str, fire_ban: list[dict[str, Any]], area: ModuleType,
                  fire_risk: list[dict[str, Any]] | None = None) -> None:
    moment = datetime.fromisoformat(time_utc.replace("Z", "+00:00"))
    day = next((entry for entry in fire_risk or [] if entry["day_utc"] == time_utc[:10]), None)
    if day:
        item.fact(f"Brandrisk {day['day_utc']}: {day['fwi_word'] or 'utanför brandsäsongen'}", ATTRIBUTION["smhi_fire_risk"],
                  day["approved_utc"])
    for month, day, name in area.FIRE_CALENDAR:
        if (moment.month, moment.day) == (month, day):
            item.notes.append(f"Det är {name}: kan vara en planerad brasa.")
    for ban in fire_ban:
        item.fact(f"Eldningsförbud: {ban['status']}" + (f" – {ban['description']}" if ban.get("description") else ""),
                  ATTRIBUTION["mcf_fire_ban"], ban.get("revised_utc"))
    item.notes.append("Satelliternas värmedetektioner kan komma från annat än bränder i naturen.")


def event_candidates(events: list[dict[str, Any]], border: dict[str, Any] | None, firms: list[dict[str, Any]],
                     fire_ban: list[dict[str, Any]], flood_items: list[Candidate], area: ModuleType, now: datetime,
                     filtered: list[dict[str, Any]], fire_risk: list[dict[str, Any]] | None = None) -> list[Candidate]:
    """The events of the last EVENT_HOURS from the inbox that lie in the municipality."""
    found = []
    for event in events:
        moment = datetime.fromisoformat(event["time_utc"].replace("Z", "+00:00"))
        if now - moment > timedelta(hours=EVENT_HOURS):
            continue
        if border and not geo.contains(border, event["latitude"], event["longitude"]):
            filtered.append({"what": f"Händelse {event['origin']}", "reason": f"utanför {area.NAME}",
                             "latitude": event["latitude"], "longitude": event["longitude"]})
            continue
        word = KIND_WORDS[event["kind"]]
        item = Candidate(f"event-{event['origin']}", event["kind"], "event", f"Rapporterad {word}", area.NAME,
                         event["latitude"], event["longitude"])
        coordinates = ", ".join(str(value) for value in event["coordinates"])
        item.fact(f"{word.capitalize()} rapporterad vid {coordinates} ({event['crs']})", event["source"], event["time_utc"])
        if event["kind"] == "fire":
            _fire_context(item, event["time_utc"], fire_ban, area, fire_risk)
            near = [point for point in firms
                    if geo.distance_km(point["latitude"], point["longitude"], event["latitude"], event["longitude"]) <= area.FIRE_CLUSTER_KM]
            if near:
                item.confirmations.append(f"{len(near)} värmedetektioner från FIRMS inom {_number(area.FIRE_CLUSTER_KM)} km")
        if event["kind"] == "flood":
            item.confirmations += [f"{flow.title}" for flow in flood_items]
        found.append(item)
    return found


def detect(poll: dict[str, Any], events: list[dict[str, Any]], area: ModuleType,
           now: datetime | None = None) -> tuple[list[Candidate], list[dict[str, Any]]]:
    """All candidates of one poll, and what the rules left out."""
    now = now or datetime.now(timezone.utc)
    filtered: list[dict[str, Any]] = []
    border = poll.get("border")
    flows = flow_candidates(poll.get("flows", []), poll.get("flow_stats", {}), poll.get("rain", []),
                            poll.get("warnings", []), area)
    fire_risk = poll.get("fire_risk", [])
    bursts = cloudburst_candidates(poll.get("radar"), poll.get("rain", []), poll.get("warnings", []), area)
    bursts += station_rain_candidates(poll.get("weather_stations", []), area)
    bursts += sea_level_candidates([item for item in poll.get("sea_level", []) if not item.get("silent")], area)
    bursts += water_level_candidates(poll.get("water_levels", []))
    candidates = (flows + bursts + warning_candidates(poll.get("warnings", [])) + vma_candidates(poll.get("krisinfo", []), area)
                  + fire_risk_candidates(fire_risk, area, now)
                  + fire_candidates(poll.get("firms", []), events, border, poll.get("fire_ban", []), area, filtered, fire_risk)
                  + event_candidates(events, border, poll.get("firms", []), poll.get("fire_ban", []), flows + bursts, area, now,
                                     filtered, fire_risk))
    return candidates, filtered
