"""Shared scenario clock for every screen (main screen, mission control, kiosk).

One engine holds the playback state: the simulated UTC clock, the speed in
simulated seconds per real second, and whether it is playing. Commands change it
for everyone; screens follow it through `/api/scenario/stream`. The clock is
computed from the real monotonic time, so it needs no ticking thread.

Mission control also triggers events (satellite detection, sensor failure, SATCOM
failure and so on). Each one is stored with its scenario time and a sequence
number, and the derived status (SATCOM up or down, GOD VIEW, +60 MIN, failed
sensors, closed roads, power failure) is part of every snapshot. While SATCOM is
down, `satcom_down_since` gives the scenario time it went down; after a restore,
`last_outage` gives the scenario times the last outage started and ended.
`filter` with a category in FILTERS hides or shows that category on the maps
(GOD VIEW's filter); `hidden_layers` lists the hidden ones. `reset` clears
the events together with the clock.

So that visitors can follow the satellite passes, the clock goes no faster than
SLOW_SPEED inside the slow windows (set_slow_windows), whatever the chosen speed;
the clock is advanced window by window, so a high speed cannot jump over one.
"""

from __future__ import annotations

import bisect
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

MIN_SPEED, MAX_SPEED = 60.0, 4 * 86400.0
# Ten scenario minutes per second: slow enough to follow, a scenario day in under 2.5 minutes.
DEFAULT_SPEED = 600.0
SLOW_SPEED = 60.0
# Events mission control can trigger. Toggles switch a view on and off; the others
# are kept until `reset`. `target` names a sensor or road and is optional.
EVENT_KINDS = (
    "satellite_detection", "sensor_failure", "satcom_failure", "satcom_restore",
    "road_closed", "power_failure", "plus60", "god_view", "filter", "space_view",
)
# Map categories mission control can hide; maritime, aviation and emergency are not in the demo.
FILTERS = ("space", "iot", "infrastructure", "weather")
TOGGLES = ("plus60", "god_view", "space_view")
TARGET_PATTERN = re.compile(r"[a-z0-9_-]{1,64}")
MAX_EVENTS = 100


def utc_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


class CommandError(ValueError):
    pass


@dataclass
class ScenarioEngine:
    start: datetime
    end: datetime
    monotonic: Callable[[], float] = time.monotonic
    speed: float = DEFAULT_SPEED
    _clock: datetime = field(init=False)
    _playing: bool = field(default=False, init=False)
    _since: float = field(default=0.0, init=False)
    revision: int = field(default=0, init=False)
    jump: int = field(default=0, init=False)  # increases when the clock moves other than by playing
    log: list[dict[str, Any]] = field(default_factory=list, init=False)
    events: list[dict[str, Any]] = field(default_factory=list, init=False)
    event_seq: int = field(default=0, init=False)
    _slow: list[tuple[datetime, datetime]] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self._clock = self.start
        self._since = self.monotonic()

    def set_slow_windows(self, windows: list[tuple[datetime, datetime]]) -> None:
        """Scenario periods in which the clock goes no faster than SLOW_SPEED; overlaps are merged."""
        merged: list[tuple[datetime, datetime]] = []
        for start, end in sorted(windows):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        with self._lock:
            self._advance()
            self._slow = merged

    def _window_at(self, moment: datetime) -> tuple[datetime, datetime] | None:
        index = bisect.bisect_right(self._slow, (moment, datetime.max.replace(tzinfo=moment.tzinfo))) - 1
        if index >= 0 and self._slow[index][0] <= moment < self._slow[index][1]:
            return self._slow[index]
        return None

    def _speed_at(self, moment: datetime) -> float:
        return min(self.speed, SLOW_SPEED) if self._window_at(moment) else self.speed

    def _advance(self) -> None:
        """Move the stored clock to now, window by window; stop at the end."""
        now = self.monotonic()
        if self._playing:
            remaining = now - self._since  # real seconds
            clock = self._clock
            while remaining > 0 and clock < self.end:
                window = self._window_at(clock)
                if window:
                    boundary = window[1]
                else:
                    later = bisect.bisect_right(self._slow, (clock, datetime.max.replace(tzinfo=clock.tzinfo)))
                    boundary = self._slow[later][0] if later < len(self._slow) else self.end
                boundary = min(boundary, self.end)
                speed = self._speed_at(clock)
                needed = (boundary - clock).total_seconds() / speed
                if needed >= remaining:
                    clock += timedelta(seconds=remaining * speed)
                    remaining = 0.0
                else:
                    clock, remaining = boundary, remaining - needed
            self._clock = min(self.end, clock)
            if self._clock >= self.end:
                self._playing = False
                self.revision += 1
        self._since = now

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._advance()
            return {
                "clock_utc": utc_text(self._clock),
                "playing": self._playing,
                "finished": self._clock >= self.end,
                "speed": self.speed,
                "effective_speed": self._speed_at(self._clock),
                "slowed": self._speed_at(self._clock) < self.speed,
                "start_utc": utc_text(self.start),
                "end_utc": utc_text(self.end),
                "revision": self.revision,
                "jump": self.jump,
                "events": list(self.events),
                "status": self._status(),
            }

    def _status(self) -> dict[str, Any]:
        """The state the events add up to, so a screen that connects late shows the same."""
        status: dict[str, Any] = {
            "satcom_up": True, "plus60": False, "god_view": False, "space_view": False, "power_failure": False,
            "failed_sensors": [], "closed_roads": [], "satcom_down_since": None, "last_outage": None,
            "hidden_layers": [],
        }
        for event in self.events:
            kind, target = event["kind"], event["target"]
            if kind == "satcom_failure":
                if status["satcom_up"]:
                    status["satcom_down_since"] = event["clock_utc"]
                status["satcom_up"] = False
            elif kind == "satcom_restore":
                if not status["satcom_up"]:
                    status["last_outage"] = {"from_utc": status["satcom_down_since"], "to_utc": event["clock_utc"]}
                    status["satcom_down_since"] = None
                status["satcom_up"] = True
            elif kind in TOGGLES:
                status[kind] = not status[kind]
            elif kind == "power_failure":
                status["power_failure"] = True
            elif kind == "sensor_failure" and target not in status["failed_sensors"]:
                status["failed_sensors"].append(target)
            elif kind == "road_closed" and target not in status["closed_roads"]:
                status["closed_roads"].append(target)
            elif kind == "filter":
                hidden = status["hidden_layers"]
                hidden.remove(target) if target in hidden else hidden.append(target)
        return status

    def _record_event(self, kind: str, target: str | None) -> None:
        if target is not None and not TARGET_PATTERN.fullmatch(target):
            raise CommandError("target must be 1–64 characters a-z, 0-9, _ or -")
        if kind == "filter" and target not in FILTERS:
            raise CommandError(f"filter needs a target: {', '.join(FILTERS)}")
        self.event_seq += 1
        self.events.append({"seq": self.event_seq, "kind": kind, "target": target, "clock_utc": utc_text(self._clock)})
        del self.events[:-MAX_EVENTS]

    def command(
        self, name: str, *, at: str | None = None, speed: float | None = None, target: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._advance()
            if name == "play":
                if self._clock >= self.end:
                    self._clock = self.start
                    self.jump += 1
                self._playing = True
            elif name == "pause":
                self._playing = False
            elif name == "reset":
                self._playing = False
                self._clock = self.start
                self.events.clear()
                self.jump += 1
            elif name == "seek":
                if not at:
                    raise CommandError("seek needs a time")
                try:
                    moment = parse_utc(at)
                except ValueError as exc:
                    raise CommandError("invalid time") from exc
                self._clock = max(self.start, min(self.end, moment))
                self.jump += 1
            elif name == "speed":
                if speed is None or not MIN_SPEED <= float(speed) <= MAX_SPEED:
                    raise CommandError(f"speed must be {MIN_SPEED:.0f}–{MAX_SPEED:.0f}")
                self.speed = float(speed)
            elif name in EVENT_KINDS:
                self._record_event(name, target)
            else:
                raise CommandError(f"unknown command: {name}")
            self.revision += 1
            self.log.append({"command": name, "at": at, "speed": speed, "target": target, "clock_utc": utc_text(self._clock), "revision": self.revision})
            del self.log[:-100]
        return self.snapshot()
