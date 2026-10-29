"""SWOT's water surface heights of the scenario's lakes and river at a pass, against the passes before
the playback (tools/fetch_swot.py).

The maps colour each lake and reach by how much its surface rose from the pass, the panel names the
uncertainties and the log has a line at the pass. Every measurement is kept: an uncertain one is
flagged and says why (each item's uncertainty_notes), and UNCERTAINTIES describes what holds for all.
"""

from __future__ import annotations

import json
import statistics
from functools import lru_cache
from typing import Any

from app.backend import scenario

LABEL = "Vattenhöjd (SWOT)"
QUALITY_NAMES = "SWOT:s kvalitetsflagga: god, osäker (suspect), försämrad (degraded) eller dålig (bad)."


@lru_cache(maxsize=1)
def data() -> dict[str, Any] | None:
    path = scenario.SWOT_DIR / "swot.json" if scenario.SWOT_DIR else None
    if path is None or not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if loaded.get("items") else None


def decimal(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def day(time_utc: str) -> str:
    months = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"]
    return f"{int(time_utc[8:10])} {months[int(time_utc[5:7]) - 1]}"


def span(times: list[str]) -> str:
    """"31 juli–3 augusti", or one day."""
    first, last = day(min(times)), day(max(times))
    if first == last:
        return first
    if first.split()[1] == last.split()[1]:
        return f"{first.split()[0]}–{last}"
    return f"{first}–{last}"


def count_word(count: int) -> str:
    return {1: "en", 2: "två", 3: "tre"}.get(count, str(count))


def uncertainties(loaded: dict[str, Any]) -> list[str]:
    """What holds for every measurement, from what was fetched."""
    rivers = [item for item in loaded["items"] if item["kind"] == "river"]
    lakes = [item for item in loaded["items"] if item["kind"] == "lake"]
    baseline = span([item["time_utc"] for item in loaded["baseline_passes"]])
    lines = [
        f"SWOT passerade bara {count_word(len({item['time_utc'] for item in loaded['passes']}))} gång under uppspelningen; "
        "den ser samma plats bara några gånger per 21-dagarscykel.",
        f"Jämförelsen är medelvärdet av SWOT:s mätningar {baseline}, före regnet – inte en normalnivå.",
        "Höjderna gäller över geoiden (EGM2008), inte RH 2000, så bara förändringen jämförs.",
        "±-värdet är SWOT:s skattade slumpfel; systematiska fel, till exempel vid branta stränder och nära kanten av "
        "radarns stråk, ingår inte.",
        "Produkten är version D från SWOT:s första år i drift; NASA och CNES validerar fortfarande mätningarna.",
        QUALITY_NAMES,
    ]
    if rivers:
        widths = [item["width_m"] for item in rivers if item.get("width_m")]
        uncertain = sum(item["uncertain"] for item in rivers)
        width = f" är {min(widths)}–{max(widths)} meter bred och" if widths else ""
        lines.append(f"{rivers[0]['name'].split(' vid ')[0]}{width.replace(' är', ' är i de mätta sträckorna')} har {uncertain} av {len(rivers)} mätta sträckor med osäker "
                     "kvalitet: smala älvsträckor ger få vattenpixlar, och träd, broar och branta stränder stör.")
    lines.extend(scenario.SWOT_NOTES)
    unnamed = sum(1 for item in lakes if not item.get("name"))
    if lakes:
        lines.append("Sjöarnas namn kommer från OpenStreetMap och är kopplade till SWOT:s sjöar efter läget"
                     + (f"; {unnamed} sjöar saknar namn." if unnamed else "."))
    return lines


def summary(loaded: dict[str, Any]) -> dict[str, Any]:
    lakes = [item for item in loaded["items"] if item["kind"] == "lake"]
    good = [item for item in lakes if not item["uncertain"]]
    rivers = [item for item in loaded["items"] if item["kind"] == "river"]
    return {
        "lakes": len(lakes), "lakes_good": len(good), "lakes_good_rose": sum(item["change_m"] > 0 for item in good),
        "lakes_good_median_m": round(statistics.median(item["change_m"] for item in good), 2) if good else None,
        "lakes_uncertain_rose": sum(item["change_m"] > 0 for item in lakes if item["uncertain"]),
        "lakes_uncertain": len(lakes) - len(good),
        "rivers": len(rivers), "rivers_uncertain": sum(item["uncertain"] for item in rivers),
        "river_name": rivers[0]["name"].split(" vid ")[0] if rivers else None,
        "river_min_m": min((item["change_m"] for item in rivers), default=None),
        "river_max_m": max((item["change_m"] for item in rivers), default=None),
        "baseline": span([item["time_utc"] for item in loaded["baseline_passes"]]),
    }


def event(loaded: dict[str, Any]) -> dict[str, Any]:
    """The log's line at the pass: the lakes of good quality, the uncertain ones and the river's range."""
    found = summary(loaded)
    parts, spoken = [], []
    if found["lakes"]:
        good = (f"{found['lakes_good_rose']} av {found['lakes_good']} sjöar med god kvalitet högre än {found['baseline']}"
                + (f", i mitten {decimal(found['lakes_good_median_m'])} meter" if found["lakes_good_median_m"] is not None else ""))
        parts.append(good)
        spoken.append(good.replace(decimal(found["lakes_good_median_m"]), decimal(found["lakes_good_median_m"], 1))
                      if found["lakes_good_median_m"] is not None else good)
        if found["lakes_uncertain"]:
            text = f"{found['lakes_uncertain_rose']} av {found['lakes_uncertain']} sjöar med osäker mätning högre"
            parts.append(text)
            spoken.append(text)
    if found["rivers"]:
        span_m = (decimal(found["river_max_m"]) if found["river_min_m"] == found["river_max_m"]
                  else f"{decimal(found['river_min_m'])} till {decimal(found['river_max_m'])}")
        text = (f"{found['river_name']} {span_m} meter högre, "
                f"{'alla' if found['rivers_uncertain'] == found['rivers'] else found['rivers_uncertain']} sträckor med osäker kvalitet")
        parts.append(text)
        spoken.append(text.replace(decimal(found["river_min_m"]), decimal(found["river_min_m"], 1))
                      .replace(decimal(found["river_max_m"]), decimal(found["river_max_m"], 1)))
    time_utc = min(item["time_utc"] for item in loaded["passes"])
    return {"time_utc": time_utc, "text": "SWOT mätte vattenhöjden: " + "; ".join(parts),
            "spoken": "SWOT mätte vattenhöjden: " + "; ".join(spoken)}


def layer() -> dict[str, Any] | None:
    """What /api/config gives the screens: the items, the pass, the summary, the log's line and the uncertainties."""
    loaded = data()
    if loaded is None:
        return None
    return {"label": LABEL, "attribution": loaded["source"], "items": loaded["items"],
            "pass_utc": min(item["time_utc"] for item in loaded["passes"]), "summary": summary(loaded),
            "event": event(loaded), "uncertainties": uncertainties(loaded)}
