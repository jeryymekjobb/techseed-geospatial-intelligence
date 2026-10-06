"""Detection from space, phase 2: the satellite pass the operator's sequence is built on, and
a rule-based classification of what it saw.

Mission control's SATELLITE DETECTION starts a sequence anchored in the next real FIRMS
pass after the scenario clock: which satellite and instrument saw the fire, when, how
many detections and how strong. The steps "anomaly detected on board" and "downlink" are
the story's synthetic part - the satellites did not analyse on board in 2014 - and are
marked so on the screens.

The classification uses rules on the data, not invented probabilities. All 1 727
detections have FIRMS type 0 ("presumed vegetation fire"), so that field cannot tell a
fire from industry here; the rules therefore also look at the OSM land cover, OSM
industrial buildings, whether the front grows between passes and whether the same spot
keeps burning. Every rule says whether it holds and points at the map.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Sequence

from app.backend import scenario
from tools import fire_spread as fs

VEGETATION = {"skog", "myr", "hed", "buskmark", "öppen mark"}
INDUSTRIAL = {"industri", "täkt"}
INDUSTRY_DISTANCE_M = 1000.0
GROWTH_SHARE = 0.10        # the front grows when its area increases this much within 24 h
STATIC_DISTANCE_M = 500.0  # "the same spot": within this distance in earlier passes
STATIC_PASSES = 3
CATEGORIES = ("Vegetationsbrand", "Industri", "Okänd")


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def place(lat: float, lon: float) -> dict[str, float]:
    return {"latitude": round(lat, 5), "longitude": round(lon, 5)}


class Detections:
    """The FIRMS detections grouped into passes (one satellite at one acquisition time)."""

    def __init__(self, items: Sequence[dict[str, Any]]) -> None:
        self.items = sorted(items, key=lambda item: item["acq_datetime_utc"])
        passes: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in self.items:
            passes.setdefault((item["acq_datetime_utc"], item["satellite"]), []).append(item)
        self.passes = sorted(passes.items())
        self.projector = fs.Projector(*scenario.FIRE_CENTRE)

    def next_pass(self, clock: datetime) -> dict[str, Any] | None:
        """The first pass after the clock, summarised; None after the last one."""
        for (time_text, satellite), items in self.passes:
            if parse_utc(time_text) > clock:
                return self.summary(time_text, satellite, items)
        return None

    def pass_at(self, time_text: str) -> dict[str, Any] | None:
        for (moment, satellite), items in self.passes:
            if moment == time_text:
                return self.summary(moment, satellite, items)
        return None

    def summary(self, time_text: str, satellite: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        strongest = max(items, key=lambda item: item["frp"])
        lat = sum(item["latitude"] for item in items) / len(items)
        lon = sum(item["longitude"] for item in items) / len(items)
        return {
            "pass_utc": time_text, "satellite": satellite, "instrument": items[0]["instrument"],
            "detections": len(items), "max_frp_mw": strongest["frp"],
            "strongest": place(strongest["latitude"], strongest["longitude"]), "centre": place(lat, lon),
        }

    def points_until(self, moment: datetime) -> list[fs.Point]:
        return [self.projector.xy(item["latitude"], item["longitude"]) for item in self.items
                if parse_utc(item["acq_datetime_utc"]) <= moment]


@lru_cache(maxsize=1)
def land_cover() -> list[tuple[str, tuple[float, float, float, float], list[list[tuple[float, float]]]]]:
    """OSM land cover as (kind, bounding box, outer rings) for point-in-polygon tests."""
    collection = json.loads(scenario.TERRAIN_FILE.read_text(encoding="utf-8"))
    shapes = []
    for feature in collection["features"]:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        rings = [[(lon, lat) for lon, lat in polygon[0]] for polygon in polygons]
        lons = [lon for ring in rings for lon, _ in ring]
        lats = [lat for ring in rings for _, lat in ring]
        shapes.append((feature["properties"]["terrain"], (min(lons), min(lats), max(lons), max(lats)), rings))
    return shapes


def inside_ring(lon: float, lat: float, ring: Sequence[tuple[float, float]]) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, [*ring[1:], ring[0]]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def land_cover_at(lat: float, lon: float) -> str | None:
    for kind, (west, south, east, north), rings in land_cover():
        if west <= lon <= east and south <= lat <= north and any(inside_ring(lon, lat, ring) for ring in rings):
            return kind
    return None


@lru_cache(maxsize=1)
def industrial_buildings() -> list[tuple[float, float]]:
    targets = json.loads(scenario.TARGETS_FILE.read_text(encoding="utf-8"))
    return [(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]) for f in targets["features"]
            if f["properties"].get("kind") == "building" and f["properties"].get("type") == "industrial"]


def hull_area(points: Sequence[fs.Point]) -> float:
    hull = fs.convex_hull(points)
    return fs.polygon_area(hull) if len(hull) >= 3 else 0.0


def classify(detections: Detections, pass_summary: dict[str, Any]) -> dict[str, Any]:
    """Rules for vegetation fire and industry for one pass; the category where most hold wins."""
    moment = parse_utc(pass_summary["pass_utc"])
    items = [item for item in detections.items if item["acq_datetime_utc"] == pass_summary["pass_utc"]
             and item["satellite"] == pass_summary["satellite"]]
    centre = pass_summary["centre"]
    rules: list[dict[str, Any]] = []

    kinds = [land_cover_at(item["latitude"], item["longitude"]) for item in items]
    mapped = [kind for kind in kinds if kind]
    vegetation = sum(kind in VEGETATION for kind in mapped)
    industrial_cover = sum(kind in INDUSTRIAL for kind in mapped)
    share = vegetation / len(mapped) if mapped else 0.0
    rules.append({"category": "Vegetationsbrand", "holds": bool(mapped) and share >= 0.5, "ref": centre,
                  "text": (f"{round(100 * share)} % av detektionerna med kartlagt marktäcke ligger i skog, myr eller annan "
                           f"vegetation (OSM, {len(mapped)} av {len(items)} kartlagda)") if mapped
                  else "Marktäcket är inte kartlagt där detektionerna ligger (OSM)"})

    now_area = hull_area(detections.points_until(moment))
    before_area = hull_area(detections.points_until(moment - timedelta(hours=24)))
    growth = (now_area - before_area) / before_area if before_area > 0 else (1.0 if now_area > 0 else 0.0)
    rules.append({"category": "Vegetationsbrand", "holds": growth >= GROWTH_SHARE, "ref": centre,
                  "text": f"Brandfronten har vuxit {round(100 * growth)} % det senaste dygnet (alla detektioner hittills)"})

    rules.append({"category": "Vegetationsbrand", "holds": all(str(item["type"]) == "0" for item in items), "ref": centre,
                  "text": "FIRMS typ 0, antagen vegetationsbrand (gäller alla detektioner i datan och skiljer därför inte ut något här)"})

    nearest = None
    for lat, lon in industrial_buildings():
        for item in items:
            dx = (lon - item["longitude"]) * 111_320 * math.cos(math.radians(lat))
            dy = (lat - item["latitude"]) * 110_540
            distance = math.hypot(dx, dy)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, lat, lon)
    near_industry = nearest is not None and nearest[0] <= INDUSTRY_DISTANCE_M
    rules.append({"category": "Industri", "holds": near_industry or industrial_cover > 0,
                  "ref": place(nearest[1], nearest[2]) if nearest else None,
                  "text": (f"Närmaste industribyggnad (OSM) ligger {round(nearest[0] / 1000, 1)} km från detektionerna".replace(".", ",")
                           if nearest else "Ingen industribyggnad i kartdata")
                  + (f"; {industrial_cover} detektioner på industrimark" if industrial_cover else "")})

    earlier = [detections.projector.xy(item["latitude"], item["longitude"]) for item in detections.items
               if parse_utc(item["acq_datetime_utc"]) < moment]
    earlier_passes = {item["acq_datetime_utc"] for item in detections.items if parse_utc(item["acq_datetime_utc"]) < moment
                      and any(math.dist(detections.projector.xy(item["latitude"], item["longitude"]),
                                        detections.projector.xy(other["latitude"], other["longitude"])) <= STATIC_DISTANCE_M
                              for other in items)}
    static = len(earlier_passes) >= STATIC_PASSES and growth < GROWTH_SHARE
    rules.append({"category": "Industri", "holds": static, "ref": pass_summary["strongest"],
                  "text": f"Samma plats har brunnit i {len(earlier_passes)} tidigare passager"
                          + (" utan att fronten vuxit – som en fast värmekälla" if static else (" men fronten växer" if earlier else ""))})

    counts = {category: sum(rule["holds"] for rule in rules if rule["category"] == category) for category in CATEGORIES[:2]}
    best = max(counts.values())
    winners = [category for category, count in counts.items() if count == best]
    outcome = winners[0] if best > 0 and len(winners) == 1 else "Okänd"
    return {"outcome": outcome, "rules": rules, "counts": counts,
            "label": "Regelbaserad klassificering ur FIRMS och OSM – ingen sannolikhet"}
