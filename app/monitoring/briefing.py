"""The briefing for an alarm: a page for the incident commander that can be printed. It says what
is happening and where, its extent, the facts with their source and time, what is uncertain, the
context (warnings, rain, flows, fire ban, Krisinformation), whom to contact by role and what the
operator has done. Every claim names its source; nothing is added that the sources do not give.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from types import ModuleType
from typing import Any

STATE_WORDS = {"new": "Nytt – inte bekräftat", "confirmed": "Bekräftat av operatören", "dismissed": "Avfärdat av operatören"}


def build(alarm: dict[str, Any], context: dict[str, Any], area: ModuleType) -> dict[str, Any]:
    """The briefing's content."""
    candidate = alarm["candidate"]
    uncertain = [fact["text"] for fact in candidate["facts"] if fact["uncertain"]] + list(candidate["notes"])
    if candidate["single_source"]:
        uncertain.insert(0, "Larmet bygger på en enda källa.")
    if not alarm["current"]:
        uncertain.insert(0, "Larmet är inte längre aktuellt i källorna.")
    place = candidate["place"]
    if candidate["latitude"] is not None:
        place += f" ({candidate['latitude']:.4f} N, {candidate['longitude']:.4f} E, WGS 84)"
    return {
        "title": candidate["title"], "kind": candidate["kind_word"], "state": STATE_WORDS[alarm["state"]],
        "current": alarm["current"], "area": area.NAME, "place": place,
        "extent": candidate["extent"], "facts": candidate["facts"], "confirmations": candidate["confirmations"],
        "exposure": candidate.get("exposure"),
        "uncertain": uncertain, "context": context, "contacts": area.CONTACTS.get(candidate["kind"], []),
        "contacts_note": area.CONTACTS_NOTE, "gis_note": area.GIS_NOTE, "history": alarm["history"], "created_utc": alarm["created_utc"],
        "made_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>" if items else "<p>Inga.</p>"


def _context_lines(context: dict[str, Any]) -> list[str]:
    lines = []
    for item in context.get("warnings", []):
        lines.append(f"SMHI-varning {item['level']}: {item['description'] or item['event']} ({item['area']}) – SMHI")
    for item in context.get("rain", []):
        lines.append(f"Regn {item['mm_24h']} mm senaste 24 h vid {item['name']}, till {item['latest_utc']} – SMHI")
    for item in context.get("flows", []):
        lines.append(f"Vattenföring {item['value']} m³/s vid {item['name']}, {item['time_utc']} – SMHI")
    for item in context.get("fire_ban", []):
        lines.append(f"Eldningsförbud: {item['status']} – MCF/länsstyrelsen")
    radar = context.get("radar")
    if radar and radar.get("frames"):
        lines.append(f"Väderradar {radar['latest_utc']}: som mest {radar['max_mm_h']} mm/h i kommunen, {radar['hour_mm']} mm "
                     "den senaste timmen – SMHI, uppskattat ur radarn")
    for item in context.get("fire_risk", [])[:3]:
        lines.append(f"Brandrisk {item['day_utc']}: {item['fwi_word'] or 'utanför brandsäsongen'}"
                     + (f", gräsbrand {item['grass_word']}" if item.get("grass_word") else "") + " – SMHI")
    for item in context.get("forecast", []):
        lines.append(f"Prognos från {item['from_utc']}: {item['rain_24h_mm']} mm regn närmaste 24 h, {item['rain_48h_mm']} mm "
                     f"närmaste 48 h, {item['temp_min']}–{item['temp_max']} °C, byar upp till {item['gust_max']} m/s – SMHI")
    for item in context.get("news", []):
        lines.append(f"Krisinformation: {item['headline']} ({item['published_utc']})")
    return lines


def exposure_lines(exposure: dict[str, Any] | None) -> list[str]:
    """What the alarm may threaten, as the briefing lists it: the protected objects by name and kind,
    the buildings, roads and railways as counts and names."""
    if not exposure:
        return []
    lines = [f"{item['name']} ({item['category']}) – {item['source']}" for item in exposure["facilities"]]
    lines.append(f"{exposure['buildings']} byggnader {exposure['where']} – {exposure['attribution']}")
    if exposure["roads"]:
        lines.append(f"{exposure['roads']} vägavsnitt {exposure['where']}: {', '.join(exposure['road_kinds'])} – © OpenStreetMap contributors")
    if exposure["railways"]:
        lines.append(f"Järnväg {exposure['where']} – © OpenStreetMap contributors")
    return lines


def render(briefing: dict[str, Any]) -> str:
    """The briefing as a page of its own."""
    facts = "".join(
        f"<tr><td>{escape(fact['text'])}{' <b>(osäkert)</b>' if fact['uncertain'] else ''}</td>"
        f"<td>{escape(fact['source'])}</td><td>{escape(fact['time_utc'] or '–')}</td></tr>" for fact in briefing["facts"])
    history = "".join(f"<tr><td>{escape(item['time_utc'])}</td><td>{escape(item['action'])}</td>"
                      f"<td>{escape(item['note'] or '')}</td></tr>" for item in briefing["history"])
    return f"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Briefing – {escape(briefing['title'])}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 16px auto; max-width: 900px; padding: 0 16px; color: #111; background: #fff; }}
h1 {{ font-size: 1.4rem; margin-bottom: 0.2rem; }} h2 {{ font-size: 1.05rem; margin-top: 1.4rem; border-bottom: 1px solid #ccc; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.92rem; }} td, th {{ border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; text-align: left; }}
.meta {{ color: #444; font-size: 0.9rem; }}
.live {{ display: inline-block; background: #c62828; color: #fff; padding: 1px 6px; font-size: 0.8rem; }}
@media print {{ button {{ display: none; }} }}
</style></head><body>
<p class="meta"><span class="live">LIVE</span> Briefing gjord {escape(briefing['made_utc'])} (UTC) · Larm sedan {escape(briefing['created_utc'])}
· {escape(briefing['state'])} <button onclick="window.print()">Skriv ut</button></p>
<h1>{escape(briefing['title'])}</h1>
<p><b>Typ:</b> {escape(briefing['kind'])} · <b>Område:</b> {escape(briefing['area'])} · <b>Plats:</b> {escape(briefing['place'])}</p>
<p><b>Omfattning:</b> {escape(briefing['extent'] or 'Inte känd ur källorna')}</p>
<h2>Fakta och källor</h2>
<table><tr><th>Fakta</th><th>Källa</th><th>Tid (UTC)</th></tr>{facts}</table>
<h2>Skyddsvärda objekt och bebyggelse{(' ' + escape(briefing['exposure']['where'])) if briefing.get('exposure') else ''}</h2>
<p class="meta">{escape(briefing['gis_note'])}</p>{_list(exposure_lines(briefing.get('exposure')))}
<h2>Bekräftelser från andra källor</h2>{_list(briefing['confirmations'])}
<h2>Osäkert</h2>{_list(briefing['uncertain'])}
<h2>Läget i övrigt</h2>{_list(_context_lines(briefing['context']))}
<h2>Kontakter</h2><p class="meta">{escape(briefing['contacts_note'])}</p>{_list(briefing['contacts'])}
<h2>Operatörens åtgärder</h2>
<table><tr><th>Tid (UTC)</th><th>Åtgärd</th><th>Anteckning</th></tr>{history}</table>
<p class="meta">Inget skickas vidare automatiskt. Briefingen bygger enbart på källorna ovan.</p>
</body></html>
"""
