"""The alarms and the monitoring's state, kept in the unversioned data/monitoring/<area>/state.json.

An alarm is new until the operator confirms or dismisses it; nothing is sent onward either way,
and every action is logged in the alarm's history. A candidate seen again updates its alarm. A
dismissed alarm comes back as new only if its candidate rises in severity (a high flow becoming a
record, a single detection becoming confirmed). An alarm whose candidate is no longer seen stays,
marked as no longer current.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.monitoring.rules import SEVERITY, Candidate

STATES = ("new", "confirmed", "dismissed")
ACTIONS = {"confirm": "confirmed", "dismiss": "dismissed"}
KEEP_EVENTS = timedelta(days=7)
KEEP_REFUSED = 200
MAX_NOTE = 500


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    """The state: alarms, recent events, refused lines, the latest poll's sources and what the
    rules left out. Safe to use from the poll thread and the web server's threads."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.state = self._read()

    def _read(self) -> dict[str, Any]:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        for key, empty in (("alarms", {}), ("events", []), ("refused", []), ("sources", []), ("filtered", []),
                           ("context", {})):
            state.setdefault(key, empty)
        return state

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, self.path)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def add_events(self, events: list[dict[str, Any]], refused: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep the new events and refused lines; the events of the last KEEP_EVENTS are returned."""
        with self.lock:
            limit = datetime.now(timezone.utc) - KEEP_EVENTS
            kept = [event for event in self.state["events"] + events
                    if datetime.fromisoformat(event["time_utc"].replace("Z", "+00:00")) >= limit]
            self.state["events"] = kept
            self.state["refused"] = (self.state["refused"] + refused)[-KEEP_REFUSED:]
            self._write()
            return list(kept)

    def apply(self, candidates: list[Candidate], sources: list[dict[str, Any]], filtered: list[dict[str, Any]],
              context: dict[str, Any]) -> None:
        """One poll's candidates into the alarms."""
        now = _now()
        with self.lock:
            alarms = self.state["alarms"]
            seen = set()
            for candidate in candidates:
                data = candidate.as_json()
                seen.add(candidate.key)
                alarm = alarms.get(candidate.key)
                if alarm is None:
                    alarms[candidate.key] = {"id": candidate.key, "state": "new", "created_utc": now, "updated_utc": now,
                                             "current": True, "candidate": data,
                                             "history": [{"time_utc": now, "action": "larm", "note": data["title"]}]}
                    continue
                rose = SEVERITY.get(data["severity"], 0) > SEVERITY.get(alarm["candidate"]["severity"], 0)
                if alarm["state"] == "dismissed" and rose:
                    alarm["state"] = "new"
                    alarm["history"].append({"time_utc": now, "action": "larm", "note": f"Högre nivå: {data['title']}"})
                if not alarm["current"]:
                    alarm["history"].append({"time_utc": now, "action": "aktuellt igen", "note": data["title"]})
                alarm.update(candidate=data, current=True, updated_utc=now)
            for key, alarm in alarms.items():
                if key not in seen and alarm["current"]:
                    alarm["current"] = False
                    alarm["updated_utc"] = now
                    alarm["history"].append({"time_utc": now, "action": "inte längre aktuellt", "note": ""})
            self.state["sources"] = sources
            self.state["filtered"] = filtered
            self.state["context"] = context
            self.state["polled_utc"] = now
            self._write()

    def act(self, alarm_id: str, action: str, note: str = "") -> dict[str, Any]:
        """The operator confirms or dismisses an alarm. Nothing is sent onward."""
        if action not in ACTIONS:
            raise ValueError(f"unknown action: {action}")
        with self.lock:
            alarm = self.state["alarms"].get(alarm_id)
            if alarm is None:
                raise KeyError(alarm_id)
            now = _now()
            alarm["state"] = ACTIONS[action]
            alarm["updated_utc"] = now
            alarm["history"].append({"time_utc": now, "action": {"confirm": "bekräftat", "dismiss": "avfärdat"}[action],
                                     "note": note.strip()[:MAX_NOTE]})
            self._write()
            return json.loads(json.dumps(alarm))
