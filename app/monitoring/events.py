"""Events in, in the one-pager's format (docs/mvp/onepager-mvp.md, "Händelser in"):

    <datum> <klockslag> <händelse> <koordinat 1> <koordinat 2> <koordinatsystem> <källa> [<simulerad>]

as TSV, CSV or JSON. The date and time are in UTC (YYYY-MM-DD, HH:MM or HH:MM:SS); the event is
brand, översvämning, erosion or skred (or fire, flood, erosion, landslide); the coordinate system is
EPSG:4326, where coordinate 1 is the latitude and coordinate 2 the longitude, or EPSG:3006, where
coordinate 1 is northing and coordinate 2 easting in metres. The source is required. The eighth
field says whether the data are simulated (ja/nej, true/false). The monitoring builds on real data
only, as the user decided on 2026-11-05: an event is taken in only when it says it is not simulated
(nej, false); one that is simulated or does not say is refused.

A JSON file holds a list of objects with the keys date, time, event, coord1, coord2, crs, source
and simulated.

Every line that is refused is logged before it is refused, with the file, the line number, the
line as written and the reason, and kept in the list of refused lines the operator page shows.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.monitoring.geo import sweref99tm_to_wgs84

log = logging.getLogger("app.monitoring.events")

EVENT_KINDS = {
    "brand": "fire", "fire": "fire",
    "översvämning": "flood", "oversvamning": "flood", "flood": "flood",
    "erosion": "erosion",
    "skred": "landslide", "landslide": "landslide",
}
KIND_WORDS = {"fire": "brand", "flood": "översvämning", "erosion": "erosion", "landslide": "skred"}
CRS_CODES = {"epsg:4326": "EPSG:4326", "4326": "EPSG:4326", "epsg:3006": "EPSG:3006", "3006": "EPSG:3006"}
YES = {"ja", "j", "true", "yes", "1"}
NO = {"nej", "n", "false", "no", "0"}
JSON_KEYS = ("date", "time", "event", "coord1", "coord2", "crs", "source")
# SWEREF 99 TM over Sweden, with a margin (Lantmäteriet's extent: N 6 100 000-7 700 000, E 180 000-1 000 000).
SWEREF_NORTHING = (6_100_000.0, 7_700_000.0)
SWEREF_EASTING = (180_000.0, 1_000_000.0)


@dataclass
class Event:
    time: datetime
    kind: str
    latitude: float
    longitude: float
    crs: str
    coordinates: tuple[float, float]
    source: str
    origin: str

    def as_json(self) -> dict[str, Any]:
        return {"time_utc": self.time.strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": self.kind, "kind_word": KIND_WORDS[self.kind],
                "latitude": round(self.latitude, 6), "longitude": round(self.longitude, 6), "crs": self.crs,
                "coordinates": list(self.coordinates), "source": self.source, "origin": self.origin}


@dataclass
class Refusal:
    origin: str
    line: str
    reason: str
    logged_utc: str

    def as_json(self) -> dict[str, Any]:
        return {"origin": self.origin, "line": self.line, "reason": self.reason, "logged_utc": self.logged_utc}


@dataclass
class Batch:
    events: list[Event] = field(default_factory=list)
    refused: list[Refusal] = field(default_factory=list)


class Refused(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _time(day: str, clock: str) -> datetime:
    clock = clock.strip()
    if len(clock) == 5:
        clock += ":00"
    try:
        return datetime.fromisoformat(f"{day.strip()}T{clock}").replace(tzinfo=timezone.utc)
    except ValueError:
        raise Refused(f"ogiltig tid: {day.strip()} {clock}") from None


def _number(text: Any, name: str) -> float:
    try:
        return float(str(text).strip().replace(",", ".") if isinstance(text, str) else text)
    except (TypeError, ValueError):
        raise Refused(f"ogiltig {name}: {text}") from None


def event_from_fields(fields: list[Any], origin: str) -> Event:
    """One event from its fields, or Refused with the reason."""
    if len(fields) not in (7, 8):
        raise Refused(f"fel antal fält: {len(fields)} (7 eller 8 väntas)")
    day, clock, kind_text, first, second, crs_text, source = (str(value).strip() if value is not None else "" for value in fields[:7])
    if not source:
        raise Refused("källa saknas")
    kind = EVENT_KINDS.get(kind_text.lower())
    if kind is None:
        raise Refused(f"okänd händelse: {kind_text}")
    crs = CRS_CODES.get(crs_text.lower())
    if crs is None:
        raise Refused(f"okänt koordinatsystem: {crs_text} (EPSG:4326 eller EPSG:3006)")
    moment = _time(day, clock)
    c1, c2 = _number(first, "koordinat 1"), _number(second, "koordinat 2")
    if crs == "EPSG:4326":
        if not (-90 <= c1 <= 90 and -180 <= c2 <= 180):
            raise Refused(f"koordinaten ligger utanför WGS 84: {c1}, {c2}")
        latitude, longitude = c1, c2
    else:
        if not (SWEREF_NORTHING[0] <= c1 <= SWEREF_NORTHING[1] and SWEREF_EASTING[0] <= c2 <= SWEREF_EASTING[1]):
            raise Refused(f"koordinaten ligger utanför SWEREF 99 TM i Sverige: N {c1}, E {c2}")
        latitude, longitude = sweref99tm_to_wgs84(c1, c2)
    flag = str(fields[7]).strip().lower() if len(fields) == 8 and fields[7] is not None else ""
    if flag in YES:
        raise Refused("simulerad händelse: övervakningen tar bara in verkliga data")
    if not flag:
        raise Refused("det är inte angivet att händelsen är verklig (simulerad: nej); övervakningen tar bara in verkliga data")
    if flag not in NO:
        raise Refused(f"okänt värde för simulerad: {fields[7]}")
    return Event(moment, kind, latitude, longitude, crs, (c1, c2), source, origin)


def _refuse(batch: Batch, origin: str, line: str, reason: str) -> None:
    # Logged first, then refused: the operator can see every line that did not come in, and why.
    log.warning("Händelse avvisad: %s: %s (%s)", origin, reason, line)
    batch.refused.append(Refusal(origin, line, reason, _utc_now()))


def _delimited_rows(text: str, delimiter: str) -> list[tuple[int, str, list[str]]]:
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = next(csv.reader(io.StringIO(line), delimiter=delimiter))
        rows.append((number, line, fields))
    return rows


def _is_header(fields: list[str]) -> bool:
    return bool(fields) and fields[0].strip().lower() in ("datum", "date")


def parse_text(text: str, name: str) -> Batch:
    """The events of one file: TSV (.tsv, .txt), CSV (.csv) or JSON (.json)."""
    batch = Batch()
    suffix = Path(name).suffix.lower()
    if suffix == ".json":
        try:
            items = json.loads(text)
        except ValueError as error:
            _refuse(batch, name, text[:200], f"ogiltig JSON: {error}")
            return batch
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            _refuse(batch, name, text[:200], "JSON ska vara en lista med händelser")
            return batch
        for number, item in enumerate(items, start=1):
            origin = f"{name}#{number}"
            line = json.dumps(item, ensure_ascii=False)
            if not isinstance(item, dict):
                _refuse(batch, origin, line, "händelsen är inget objekt")
                continue
            fields = [item.get(key) for key in JSON_KEYS]
            if "simulated" in item:
                fields.append("ja" if item["simulated"] is True else "nej" if item["simulated"] is False else item["simulated"])
            try:
                batch.events.append(event_from_fields(fields, origin))
            except Refused as reason:
                _refuse(batch, origin, line, str(reason))
        return batch
    delimiter = "," if suffix == ".csv" else "\t"
    for number, line, fields in _delimited_rows(text, delimiter):
        if _is_header(fields):
            continue
        origin = f"{name}:{number}"
        try:
            batch.events.append(event_from_fields(fields, origin))
        except Refused as reason:
            _refuse(batch, origin, line, str(reason))
    return batch


def read_inbox(inbox: Path) -> Batch:
    """The events of every file in the inbox; each file read is moved to inbox/processed/ so it
    is read once."""
    batch = Batch()
    if not inbox.is_dir():
        return batch
    processed = inbox / "processed"
    for path in sorted(item for item in inbox.iterdir() if item.is_file() and not item.name.startswith(".")):
        if path.suffix.lower() not in (".tsv", ".txt", ".csv", ".json"):
            _refuse(batch, path.name, "", f"okänd filtyp: {path.suffix or '(ingen)'}")
        else:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as error:
                _refuse(batch, path.name, "", f"filen kunde inte läsas: {error}")
            else:
                result = parse_text(text, path.name)
                batch.events.extend(result.events)
                batch.refused.extend(result.refused)
        processed.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path.replace(processed / f"{stamp}-{path.name}")
    return batch
