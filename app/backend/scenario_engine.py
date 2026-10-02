"""Shared scenario clock for every screen (main screen, mission control, kiosk).

One engine holds the playback state: the simulated UTC clock, the speed in
simulated seconds per real second, and whether it is playing. Commands change it
for everyone; screens follow it through `/api/scenario/stream`. The clock is
computed from the real monotonic time, so it needs no ticking thread.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

MIN_SPEED, MAX_SPEED = 60.0, 4 * 86400.0
DEFAULT_SPEED = 3600.0


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
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self._clock = self.start
        self._since = self.monotonic()

    def _advance(self) -> None:
        """Move the stored clock to now; stop at the end."""
        now = self.monotonic()
        if self._playing:
            self._clock = min(self.end, self._clock + timedelta(seconds=(now - self._since) * self.speed))
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
                "start_utc": utc_text(self.start),
                "end_utc": utc_text(self.end),
                "revision": self.revision,
                "jump": self.jump,
            }

    def command(self, name: str, *, at: str | None = None, speed: float | None = None) -> dict[str, Any]:
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
            else:
                raise CommandError(f"unknown command: {name}")
            self.revision += 1
            self.log.append({"command": name, "at": at, "speed": speed, "clock_utc": utc_text(self._clock), "revision": self.revision})
            del self.log[:-100]
        return self.snapshot()
