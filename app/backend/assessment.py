"""Traceable fire assessment at the scenario clock: an evidence list and a rule-based score.

Every evidence line says what it rests on and points at an object on the map, so
"Why do you believe there is a fire?" is answered by the list itself. The score
combines the lines that hold with fixed weights, 1 - prod(1 - weight); the weights
are invented for the demo, so the score is a rule-based score, not a calibrated
probability, and the GUI says so.

Evidence (status ok, warn, miss or info):
- satellite: FIRMS detections in the last 24 hours (real 2014 archive data);
- repeat: detections within REPEAT_DISTANCE_M of each other in different passes;
- high confidence: a MODIS confidence of at least 80 or a VIIRS "h";
- IoT: each synthetic sensor that confirms the fire (sensor_sim.py), warn when failed;
- wind and forecast: context from ERA5-Land and forecast.py, weight 0;
- camera: no camera in the demo, always warn, weight 0.
"""

from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Sequence

from tools import fire_spread as fs

WINDOW = timedelta(hours=24)
REPEAT_DISTANCE_M = 1000.0
WEIGHTS = {"satellite": 0.50, "repeat": 0.30, "high_confidence": 0.20, "iot": 0.25}
OUTCOMES = ((0.75, "Wildfire probable"), (0.40, "Possible fire"), (0.0, "No fire indicated"))
SCORE_LABEL = "Regelbaserad poäng med fasta vikter – inte en kalibrerad sannolikhet"
COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSV", "SV", "VSV", "V", "VNV", "NV", "NNV"]


def sv(value: float) -> str:
    """A number with a decimal comma, as in the rest of the GUI."""
    return str(value).replace(".", ",")


def high_confidence(item: dict[str, Any]) -> bool:
    value = str(item["confidence"])
    return value == "h" if item["instrument"] == "VIIRS" else value.isdigit() and int(value) >= 80


def place(lat: float, lon: float) -> dict[str, float]:
    return {"latitude": round(lat, 5), "longitude": round(lon, 5)}


def line(key: str, status: str, text: str, ref: dict[str, float] | None, weight: float = 0.0) -> dict[str, Any]:
    return {"key": key, "status": status, "text": text, "ref": ref, "weight": weight if status == "ok" else 0.0}


class Assessor:
    def __init__(self, detections: Sequence[dict[str, Any]], wind: dict[str, Any], forecast_states: Sequence[dict[str, Any]],
                 centre: tuple[float, float]) -> None:
        self.items = sorted(detections, key=lambda item: item["acq_datetime_utc"])
        self.times = [parse_utc(item["acq_datetime_utc"]) for item in self.items]
        self.projector = fs.Projector(*centre)
        self.points = [self.projector.xy(item["latitude"], item["longitude"]) for item in self.items]
        self.centre = centre
        self.wind = wind
        self.wind_times = [parse_utc(text) for text in wind["times_utc"]]
        self.forecast_states = list(forecast_states)
        self.forecast_times = [parse_utc(state["pass_utc"]) for state in self.forecast_states]
        self.satellite = lru_cache(maxsize=64)(self._satellite)

    def _satellite(self, low: int, high: int) -> list[dict[str, Any]]:
        """Satellite evidence for the detections low..high-1 (the last 24 hours)."""
        if high == low:
            if high:
                last = self.items[high - 1]
                return [line("satellite", "warn", f"Inga FIRMS-detektioner senaste 24 h (senaste {last['acq_datetime_utc']})",
                             place(last["latitude"], last["longitude"]))]
            return [line("satellite", "miss", "Ingen FIRMS-detektion ännu", None)]
        recent = range(low, high)
        last = self.items[high - 1]
        passes = {self.items[index]["acq_datetime_utc"] for index in recent}
        lines = [line("satellite", "ok", f"Satellite anomaly: {high - low} FIRMS-detektioner i {len(passes)} passager senaste 24 h "
                      f"(senaste {last['instrument']} {last['satellite']} {last['acq_datetime_utc']})",
                      place(last["latitude"], last["longitude"]), WEIGHTS["satellite"])]
        repeat = self._repeat(recent)
        lines.append(line("repeat", "ok", f"Upprepad detektion inom {REPEAT_DISTANCE_M / 1000:.0f} km i olika passager",
                          place(*repeat), WEIGHTS["repeat"]) if repeat else
                     line("repeat", "miss", "Ingen upprepad detektion på samma plats", None))
        strong = [self.items[index] for index in recent if high_confidence(self.items[index])]
        if strong:
            best = max(strong, key=lambda item: item["frp"])
            lines.append(line("high_confidence", "ok", f"Hög FIRMS-konfidens: {len(strong)} detektioner, högst {sv(best['frp'])} MW FRP",
                              place(best["latitude"], best["longitude"]), WEIGHTS["high_confidence"]))
        else:
            lines.append(line("high_confidence", "miss", "Ingen detektion med hög FIRMS-konfidens", None))
        return lines

    def _repeat(self, recent: range) -> tuple[float, float] | None:
        """Latitude and longitude of the latest detection that repeats an earlier pass nearby."""
        for index in reversed(recent):
            for other in recent:
                if self.times[other] >= self.times[index]:
                    break
                if math.dist(self.points[index], self.points[other]) <= REPEAT_DISTANCE_M:
                    return self.items[index]["latitude"], self.items[index]["longitude"]
        return None

    def _context(self, clock: datetime, hull_centre: tuple[float, float]) -> list[dict[str, Any]]:
        lines = []
        hour = bisect.bisect_right(self.wind_times, clock) - 1
        if hour >= 0:
            centre_xy = self.projector.xy(*hull_centre)
            nearest = min(range(len(self.wind["points"])),
                          key=lambda index: math.dist(centre_xy, self.projector.xy(*self.wind["points"][index])))
            speed, blows_from, _ = self.wind["values"][hour][nearest]
            lines.append(line("wind", "info", f"Vind {sv(round(speed, 1))} m/s från {COMPASS[round(blows_from / 22.5) % 16]} (ERA5-Land, modell) – "
                              "kontext, påverkar inte poängen", place(*self.wind["points"][nearest])))
        index = bisect.bisect_right(self.forecast_times, clock) - 1
        if index >= 0:
            state = self.forecast_states[index]
            lines.append(line("forecast", "info", f"Prognos: spridning mot {state['model']['towards']}, "
                              f"{sv(state['model']['head_km_per_h']['central'])} km/h (modell, stor osäkerhet) – kontext",
                              place(*state["front_centre"])))
        return lines

    def at(self, clock: datetime, synthetic: dict[str, Any]) -> dict[str, Any]:
        high = bisect.bisect_right(self.times, clock)
        low = bisect.bisect_right(self.times, clock - WINDOW)
        evidence = list(self.satellite(low, high))
        for sensor in synthetic["sensors"]:
            ref = place(sensor["latitude"], sensor["longitude"])
            if sensor["status"] == "failed":
                evidence.append(line(f"iot:{sensor['id']}", "warn", f"{sensor['name']}: sensorbortfall (syntetisk)", ref))
            elif sensor["confirms"]:
                reason = "rök" if sensor["smoke"] == "DETECTED" else "förhöjd temperatur"
                evidence.append(line(f"iot:{sensor['id']}", "ok", f"IoT {sensor['name']}: {reason}, {sv(sensor['temp_c'])} °C (syntetisk)",
                                     ref, WEIGHTS["iot"]))
            else:
                evidence.append(line(f"iot:{sensor['id']}", "miss", f"IoT {sensor['name']}: inget tecken på brand (syntetisk)", ref))
        hull_centre = self.centre
        if high >= 3:
            x, y = fs.centroid(fs.convex_hull(self.points[:high]))
            hull_centre = self.projector.latlon(x, y)
        evidence += self._context(clock, hull_centre)
        evidence.append(line("camera", "warn", "Camera unavailable – ingen kamera i demon", None))
        score = 1.0 - math.prod(1.0 - item["weight"] for item in evidence)
        outcome = next(text for limit, text in OUTCOMES if score >= limit)
        return {"outcome": outcome, "score_pct": round(score * 100), "score_label": SCORE_LABEL, "evidence": evidence}


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))
