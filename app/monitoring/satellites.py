"""The current orbital elements of the satellites whose data the monitoring uses, for the globe and
the satellite monitor, which compute where they are now with satellite.js (SGP4), as the demos do
for their scenario's clock (app/backend/satellites.py, app/frontend/orbits.js).

The latest element set of each satellite comes from Space-Track (class gp), with the user's account
in ~/.spacetrackrc (tools/fetch_tle_history.py reads it; the login is never printed or stored). It is
kept in data/monitoring/tle/current.json and asked for again only when older than MAX_AGE, well
inside Space-Track's guidance of one gp query an hour. A failed fetch keeps the elements already
kept, and says so. A satellite that Space-Track has no current elements for is left out.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from app.backend.scenarios import REPO_ROOT

CACHE_FILE = REPO_ROOT / "data" / "monitoring" / "tle" / "current.json"
MAX_AGE = timedelta(hours=24)
LABEL = "Läge nu, beräknat ur aktuella banelement (SGP4) – inte en observation"
ATTRIBUTION = "Banelement: USSPACECOM via Space-Track.org"

Fetch = Callable[[str], list[dict[str, Any]]]


def query_path(norads: list[str]) -> str:
    return f"/basicspacedata/query/class/gp/NORAD_CAT_ID/{','.join(norads)}/orderby/NORAD_CAT_ID/format/json"


def space_track(path: str) -> list[dict[str, Any]]:
    """One query to Space-Track with the user's account."""
    from tools import fetch_tle_history

    credentials = fetch_tle_history.read_credentials(fetch_tle_history.DEFAULT_CREDENTIALS)
    return fetch_tle_history.fetch(credentials, "", "", path=path)


def elements(records: list[dict[str, Any]], norads: set[str]) -> dict[str, list[dict[str, str]]]:
    """The element set of each wanted satellite, in the demo's form (epoch_utc, line1, line2)."""
    found: dict[str, list[dict[str, str]]] = {}
    for record in records:
        norad = str(record.get("NORAD_CAT_ID", ""))
        lines = (record.get("TLE_LINE1"), record.get("TLE_LINE2"))
        if norad in norads and all(isinstance(line, str) and len(line) == 69 for line in lines):
            found[norad] = [{"epoch_utc": str(record["EPOCH"]).replace(" ", "T") + "Z", "line1": lines[0], "line2": lines[1]}]
    return found


def satellites(area: ModuleType, fetch: Fetch = space_track, path: Path = CACHE_FILE,
               now: datetime | None = None) -> dict[str, Any]:
    """The satellites with their current elements, as the demo's /api/satellites gives them."""
    now = now or datetime.now(timezone.utc)
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cached = {}
    fetched = cached.get("fetched_utc")
    stale = (not fetched or now - datetime.fromisoformat(fetched.replace("Z", "+00:00")) >= MAX_AGE
             or not set(area.SATELLITES) <= set(cached.get("asked", [])))
    note = None
    if stale:
        try:
            found = elements(fetch(query_path(sorted(area.SATELLITES))), set(area.SATELLITES))
        except Exception as error:  # noqa: BLE001 - a failed fetch keeps the elements already kept
            note = f"Banelementen kunde inte hämtas nu ({error}); de senast hämtade används."
        else:
            fetched = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            cached = {"fetched_utc": fetched, "asked": sorted(area.SATELLITES), "elements": found,
                      "source": "Space-Track.org, class gp", "terms": "https://www.space-track.org/documentation#/user_agree"}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cached, indent=1), encoding="utf-8")
    kept = cached.get("elements") or {}
    items = [{"norad": norad, **role, "elements": kept[norad]} for norad, role in area.SATELLITES.items() if kept.get(norad)]
    if not items:
        return {"available": False, "label": LABEL, "satellites": [],
                "note": note or "Banelementen är inte hämtade; skärmarna visar inga satelliter."}
    missing = [role["name"] for norad, role in area.SATELLITES.items() if not kept.get(norad)]
    return {"available": True, "label": LABEL, "attribution": ATTRIBUTION,
            "source": f"USSPACECOM via Space-Track.org (banelement, gp), hämtade {fetched}",
            "note": " ".join(part for part in (note, f"Inga aktuella banelement för {', '.join(missing)}." if missing else None) if part) or None,
            "satellites": items}
