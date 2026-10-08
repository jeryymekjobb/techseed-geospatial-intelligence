"""The flood's evidence-based assessment and detection sequence, in the fire's formats.

The assessment (as assessment.py for the fire) adds up rule-based evidence with fixed
weights: the real rain of the gauges, the synthetic overflow sensors (flood_sensors.py)
and, as context, the municipality's cloudburst model and the satellite images. The
detection sequence (as detection.py) is anchored in a real Sentinel-1 radar acquisition
over the scenario's place from the Copernicus catalogue; its image's water is a simple computed
mask (tools/fetch_sentinel1_scene.py), which the rules call so and leave out where the
image cannot tell water from land.

A river and lake flood (a scenario with SMHI's flows and levels, hydro.py) rises over days, not
in an hour: there the rain counts over five days, and SMHI's measured flows and lake levels
above the highest measured before take the place of the hour's rain and the municipality's model.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Sequence

from app.backend.assessment import SCORE_LABEL, line, place, sv

WEIGHTS = {"rain_hour": 0.30, "rain_day": 0.25, "iot": 0.25, "rain_days": 0.25, "flow": 0.30, "level": 0.30}
OUTCOMES = ((0.75, "Flood probable"), (0.40, "Possible flood"), (0.0, "No flood indicated"))
RAIN_HOUR_MM = 7.0     # demo rules, not SMHI's warning classes
RADAR_WATER_PCT = 1.0  # the radar's computed water outside lakes and sea, of the town's land
RAIN_DAY_MM = 20.0
DEEP_MODEL_M = 0.3
RAIN_DAYS = 5          # the river flood's rain: the sum over these days (demo rule)
RAIN_DAYS_MM = 30.0
HYDRO_WORDS = {"flow": ("Vattenföring", "m³/s"), "level": ("Vattenstånd", "m")}
CATEGORY = "Översvämning"
HOUR = timedelta(hours=1)


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def format_utc(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def rain_since(observations: Sequence[dict[str, Any]], clock: datetime, span: timedelta) -> float:
    """Millimetres in the span up to the clock; a missing hour is dry."""
    return round(sum(item.get("precip_mm") or 0.0 for item in observations
                     if clock - span < parse_utc(item["time_utc"]) <= clock), 1)


def hydro_value(kind: str, value: float) -> str:
    """As hydro.js: a flow in m³/s with one decimal, a level in cm shown in metres."""
    text = f"{value / 100:.2f}" if kind == "level" else f"{value:.1f}"
    return f"{text.replace('.', ',')} {HYDRO_WORDS[kind][1]}"


def level_text(sensor: dict[str, Any]) -> str:
    """A level sensor's alarm and its station's value against the record (level_sensors.py)."""
    state = "larmar" if sensor["confirms"] else "inget larm"
    if sensor["value"] is None:
        return f"{state}, inga värden från {sensor['station']} ännu"
    if sensor["station_kind"] == "flow":
        return f"{state}, {sensor['station']} {sensor['percent']} % av tidigare högsta flöde"
    return f"{state}, {sensor['station']} {abs(sensor['from_record_cm'])} cm {'över' if sensor['from_record_cm'] > 0 else 'under'} tidigare högsta nivå"


def rain_sums(observations: Sequence[dict[str, Any]], clock: datetime) -> tuple[float, float]:
    """Millimetres in the hour and the 24 hours up to the clock (as rain.js); a missing hour is dry."""
    hour = day = 0.0
    for observation in observations:
        moment = parse_utc(observation["time_utc"])
        if moment > clock:
            break
        value = observation.get("precip_mm") or 0.0
        if moment > clock - 24 * HOUR:
            day += value
        if moment > clock - HOUR:
            hour += value
    return round(hour, 1), round(day, 1)


class FloodAssessor:
    def __init__(self, stations: Sequence[dict[str, Any]], acquisitions: Sequence[dict[str, str]],
                 scenes: Sequence[dict[str, Any]], centre: tuple[float, float], *, place_name: str = "Sundsvall",
                 focus_land: str = "stans land", gauges: str = "kommunens mätare",
                 hydro: Sequence[dict[str, Any]] = ()) -> None:
        # The scenario's words: its place, the land the radar's water is counted on and its rain gauges.
        self.place_name, self.focus_land, self.gauges = place_name, focus_land, gauges
        self.stations = list(stations)
        self.acquisitions = sorted(acquisitions, key=lambda item: item["time_utc"])
        self.scenes = [scene for scene in scenes if "water" in scene["images"]]
        self.radar = [scene for scene in scenes if "radarwater" in scene["images"]]
        self.centre = centre
        # SMHI's flows and levels (hydro.py): with them the rules are the river flood's.
        self.hydro = [station for station in hydro if station.get("earlier_max")]

    def _wettest(self, clock: datetime, day: bool) -> tuple[float, dict[str, Any] | None]:
        best = (0.0, None)
        for station in self.stations:
            value = rain_sums(station["observations"], clock)[1 if day else 0]
            if value > best[0]:
                best = (value, station)
        return best

    def _wettest_since(self, clock: datetime) -> tuple[float, dict[str, Any] | None]:
        best = (0.0, None)
        for station in self.stations:
            value = rain_since(station["observations"], clock, RAIN_DAYS * 24 * HOUR)
            if value > best[0]:
                best = (value, station)
        return best

    def _rain_days_text(self, value: float, station: dict[str, Any] | None, span: str = f"de senaste {RAIN_DAYS} dygnen") -> str:
        return (f"{sv(value)} mm regn {span}" + (f" vid {station['name']}" if station else "")
                + f" (SMHI, {self.gauges}; regel ≥ {sv(RAIN_DAYS_MM)} mm)")

    def _above(self, kind: str, clock: datetime) -> tuple[list[tuple[dict[str, Any], float]], dict[str, Any] | None]:
        """The stations of the kind whose latest value is above their highest measured before, with it,
        and the station nearest its record (the highest share of it) for a line when none is."""
        above, nearest, share = [], None, -math.inf
        for station in self.hydro:
            if station["kind"] != kind:
                continue
            latest = next((item for item in reversed(station["observations"]) if parse_utc(item["time_utc"]) <= clock), None)
            if latest is None:
                continue
            if latest["value"] > station["earlier_max"]["value"]:
                above.append((station, latest["value"]))
            if latest["value"] / station["earlier_max"]["value"] > share:
                nearest, share = {**station, "latest": latest["value"]}, latest["value"] / station["earlier_max"]["value"]
        return above, nearest

    def _hydro_line(self, kind: str, clock: datetime) -> tuple[bool, str, dict[str, Any] | None]:
        """Whether a station of the kind is above its highest measured before, the text and its place."""
        above, nearest = self._above(kind, clock)
        word = HYDRO_WORDS[kind][0]
        if above:
            stations = ", ".join(f"{station['name']} {hydro_value(kind, value)} (tidigare högsta {hydro_value(kind, station['earlier_max']['value'])}, "
                                 f"{station['earlier_max']['time_utc'][:4]})" for station, value in above)
            first = above[0][0]
            return True, f"{word} över tidigare högsta: {stations} (SMHI)", place(first["latitude"], first["longitude"])
        if nearest:
            return False, (f"{word} under tidigare högsta: närmast {nearest['name']} {hydro_value(kind, nearest['latest'])} av "
                           f"{hydro_value(kind, nearest['earlier_max']['value'])} (SMHI)"), place(nearest["latitude"], nearest["longitude"])
        return False, f"{word}: inga värden ännu (SMHI)", None

    def _river(self, clock: datetime) -> list[dict[str, Any]]:
        value, station = self._wettest_since(clock)
        ref = place(station["latitude"], station["longitude"]) if station else None
        evidence = [line("rain_days", "ok" if value >= RAIN_DAYS_MM else "miss", self._rain_days_text(value, station),
                         ref, WEIGHTS["rain_days"])]
        for kind in ("flow", "level"):
            if any(item["kind"] == kind for item in self.hydro):
                holds, text, where = self._hydro_line(kind, clock)
                evidence.append(line(kind, "ok" if holds else "miss", text, where, WEIGHTS[kind]))
        return evidence

    def _rain(self, clock: datetime) -> list[dict[str, Any]]:
        if self.hydro:
            return self._river(clock)
        evidence = []
        for key, day, limit, span in (("rain_hour", False, RAIN_HOUR_MM, "senaste timmen"), ("rain_day", True, RAIN_DAY_MM, "senaste dygnet")):
            value, station = self._wettest(clock, day)
            ref = place(station["latitude"], station["longitude"]) if station else None
            where = f" vid {station['name']}" if station else ""
            text = f"Regn {span}: högst {sv(value)} mm{where} (SMHI, {self.gauges}; regel ≥ {sv(limit)} mm)"
            evidence.append(line(key, "ok" if value >= limit else "miss", text, ref, WEIGHTS[key]))
        return evidence

    def _satellite(self, until: datetime) -> list[dict[str, Any]]:
        evidence = []
        taken = [item for item in self.acquisitions if parse_utc(item["time_utc"]) <= until]
        if taken:
            last = taken[-1]
            scene = self.radar_scene(last["time_utc"])
            evidence.append(line("radar", "info", f"Senaste radarbild: {last['satellite']} {last['time_utc'][5:16].replace('T', ' ')} UTC – "
                                 + self.radar_text(scene), None))
        images = [scene for scene in self.scenes if parse_utc(scene["acquired_utc"]) <= until]
        if images:
            scene = images[-1]
            evidence.append(line("image", "info", f"Senaste optiska bild med vatten: {scene['label']}, {sv(scene['cloud_pct'])} % moln över "
                                 f"{self.place_name} (NDWI)", None))
        else:
            evidence.append(line("image", "info", "Ingen klar optisk satellitbild under regnet", None))
        return evidence

    def radar_scene(self, moment: str) -> dict[str, Any] | None:
        return next((scene for scene in self.radar if scene["acquired_utc"] == moment), None)

    def radar_text(self, scene: dict[str, Any] | None) -> str:
        if scene is None:
            return "bilden är inte hämtad (tools/fetch_sentinel1_scene.py)"
        if not scene["separable"]:
            return "vatten och land skiljs dåligt åt i bilden (vind eller regn), vattenmasken är osäker"
        return f"vatten utanför sjöar och hav på {sv(scene['new_water_pct'])} % av {self.focus_land} (beräknat, enkel tröskel)"

    def at(self, clock: datetime, synthetic: dict[str, Any], satellite_until: datetime | None = None) -> dict[str, Any]:
        """The assessment at the clock; `satellite_until` is the start of a SATCOM outage."""
        until = clock if satellite_until is None else min(clock, satellite_until)
        evidence = self._rain(clock)
        if until < clock:
            evidence.insert(0, line("satcom", "warn", f"Satellitdata otillgänglig sedan {format_utc(until)} (simulerat avbrott)", None))
        if synthetic.get("disabled"):
            evidence.append(line("iot", "warn", "IoT avstängt från mission control – inga sensorer i bedömningen", None))
        for sensor in synthetic["sensors"]:
            ref = place(sensor["latitude"], sensor["longitude"])
            if sensor["status"] == "failed":
                evidence.append(line(f"iot:{sensor['id']}", "warn", f"{sensor['name']}: sensorbortfall (syntetisk)", ref))
            elif sensor.get("kind") == "level":
                evidence.append(line(f"iot:{sensor['id']}", "ok" if sensor["confirms"] else "miss",
                                     f"IoT {sensor['name']}: {level_text(sensor)} (syntetisk)", ref, WEIGHTS["iot"] if sensor["confirms"] else 0.0))
            elif sensor["confirms"]:
                evidence.append(line(f"iot:{sensor['id']}", "ok", f"IoT {sensor['name']}: bräddning, {sensor['percent']} % fyllt (syntetisk)",
                                     ref, WEIGHTS["iot"]))
                if (sensor.get("model_depth_m") or 0) >= DEEP_MODEL_M:
                    evidence.append(line(f"model:{sensor['id']}", "info", f"Kommunens skyfallsmodell: {sv(round(sensor['model_depth_m'], 2))} m vatten vid "
                                         f"{sensor['name']} vid 100-årsregn (modell)", ref))
            else:
                evidence.append(line(f"iot:{sensor['id']}", "miss", f"IoT {sensor['name']}: {sensor['percent']} % fyllt, ingen bräddning (syntetisk)", ref))
        evidence += self._satellite(until)
        evidence.append(line("camera", "warn", "Camera unavailable – ingen kamera i demon", None))
        score = 1.0 - math.prod(1.0 - item["weight"] for item in evidence)
        outcome = next(text for limit, text in OUTCOMES if score >= limit)
        return {"outcome": outcome, "score_pct": round(score * 100), "score_label": SCORE_LABEL, "evidence": evidence}

    def outage(self, start: datetime, end: datetime) -> dict[str, Any]:
        """The radar acquisitions and optical images between start and end (the SYNC after a SATCOM outage)."""
        passes = [{"time_utc": item["time_utc"], "text": f"{item['satellite']} radarbild – {self.radar_text(self.radar_scene(item['time_utc']))}"}
                  for item in self.acquisitions if start < parse_utc(item["time_utc"]) <= end]
        passes += [{"time_utc": scene["acquired_utc"], "text": f"{scene['label']} (optisk bild)"}
                   for scene in self.scenes if start < parse_utc(scene["acquired_utc"]) <= end]
        return {"from_utc": format_utc(start), "to_utc": format_utc(end), "passes": sorted(passes, key=lambda item: item["time_utc"]),
                "detections": 0, "area_increase_pct": None}

    # The detection sequence.

    def next_pass(self, clock: datetime) -> dict[str, Any] | None:
        upcoming = [item for item in self.acquisitions if parse_utc(item["time_utc"]) > clock]
        return self.pass_at(upcoming[0]["time_utc"]) if upcoming else None

    def pass_at(self, moment: str) -> dict[str, Any] | None:
        item = next((entry for entry in self.acquisitions if entry["time_utc"] == moment), None)
        if item is None:
            return None
        return {"pass_utc": item["time_utc"], "satellite": item["satellite"], "norad": item["norad"], "instrument": "SAR",
                "kind": "flood", "centre": place(*self.centre), "strongest": place(*self.centre)}

    def _radar_rule(self, summary: dict[str, Any]) -> dict[str, Any]:
        """The radar image itself: water outside lakes and sea on at least RADAR_WATER_PCT of the town's land."""
        scene = self.radar_scene(summary["pass_utc"])
        holds = bool(scene) and scene["separable"] and scene["new_water_pct"] >= RADAR_WATER_PCT
        return {"category": CATEGORY, "holds": holds, "ref": summary["centre"],
                "text": f"Radarbilden: {self.radar_text(scene)}; regeln kräver minst {sv(RADAR_WATER_PCT)} %"}

    def _river_rules(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        """The river flood's rules at the acquisition: the rain of the days before it and SMHI's flows and levels."""
        moment = parse_utc(summary["pass_utc"])
        value, station = self._wettest_since(moment)
        rules = [{"category": CATEGORY, "holds": value >= RAIN_DAYS_MM, "ref": place(station["latitude"], station["longitude"]) if station else None,
                  "text": self._rain_days_text(value, station, f"de {RAIN_DAYS} dygnen före bilden")}]
        for kind in ("flow", "level"):
            holds, text, where = self._hydro_line(kind, moment)
            rules.append({"category": CATEGORY, "holds": holds, "ref": where, "text": text})
        return rules

    def classify(self, summary: dict[str, Any], synthetic: dict[str, Any]) -> dict[str, Any]:
        """Rules for a flood at the acquisition: the rain before it, the synthetic sensors and the model;
        for a river flood the rain of the days before, SMHI's flows and levels and the radar image."""
        if self.hydro:
            rules = [*self._river_rules(summary), self._radar_rule(summary)]
            count = sum(rule["holds"] for rule in rules)
            return {"outcome": "Översvämning trolig" if count >= 2 else "Okänd", "rules": rules, "counts": {CATEGORY: count},
                    "label": "Regelbaserad klassificering ur regn, SMHI:s uppmätta flöden och nivåer och radarbilden – ingen sannolikhet"}
        moment = parse_utc(summary["pass_utc"])
        rain, station = self._wettest(moment, day=True)
        overflowing = [sensor for sensor in synthetic["sensors"] if sensor["status"] == "ok" and sensor["confirms"]]
        deep = [sensor for sensor in overflowing if (sensor.get("model_depth_m") or 0) >= DEEP_MODEL_M]
        rules = [
            {"category": CATEGORY, "holds": rain >= RAIN_DAY_MM, "ref": place(station["latitude"], station["longitude"]) if station else None,
             "text": f"{sv(rain)} mm regn det senaste dygnet före bilden" + (f" vid {station['name']}" if station else "") + " (SMHI)"},
            {"category": CATEGORY, "holds": bool(overflowing), "ref": place(overflowing[0]["latitude"], overflowing[0]["longitude"]) if overflowing else None,
             "text": f"{len(overflowing)} av {len(synthetic['sensors'])} bräddgivare bräddar (syntetiska)"},
            {"category": CATEGORY, "holds": bool(deep), "ref": place(deep[0]["latitude"], deep[0]["longitude"]) if deep else None,
             "text": (f"Kommunens skyfallsmodell ger minst {sv(DEEP_MODEL_M)} m vatten vid {len(deep)} av de bräddande punkterna"
                      if overflowing else "Ingen bräddande punkt att jämföra med kommunens skyfallsmodell")},
            self._radar_rule(summary),
        ]
        count = sum(rule["holds"] for rule in rules)
        return {"outcome": "Översvämning trolig" if count >= 2 else "Okänd", "rules": rules, "counts": {CATEGORY: count},
                "label": "Regelbaserad klassificering ur regn, syntetiska bräddgivare, kommunens modell och radarbilden – ingen sannolikhet"}
