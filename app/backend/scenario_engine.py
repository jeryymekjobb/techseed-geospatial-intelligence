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
(GOD VIEW's filter); `hidden_layers` lists the hidden ones. `place_sensor` with a
latitude and longitude inside the map area places a synthetic IoT sensor there
(the main screen's right-click menu); `placed_sensors` lists them. `image` chooses
what the maps show under their overlays for every screen - `auto` the latest image
taken up to the clock, `off` the map, or a scene's image as "scene|image" - and is
in the status as `image`; it is a setting, not an event. `image_types` ticks the image
types "auto" follows (comma-separated, for example "radar,natural"; empty for none) and is
in the status as `image_types`, None until ticked, when the screens use their default.
`camera` sends every main screen's camera to the incident or the overview ("incident" or
"home"); the status's `camera` counts the requests, so a screen flies only on a new one.
`choose` sets one of the main screen's panel choices for every screen ("key=value", for example
"horizon=12" or "hydro_station=2176:3"; `choices` in the status, the panel's own defaults until set).
`map_layer_on` and `map_layer_off` switch a map layer by its name for every screen
(`map_layers` in the status: the layers switched, the others as each map starts them).
`base_maps` ticks the base maps the same way (`base_maps` in the status; basemaps.js).
`reset` clears the events and the image and map choices together with the clock; the
ticks go back to the saved display profile (`profile`, profiles.py), or None without one.

So that visitors can follow the satellite passes, the clock goes no faster than
SLOW_SPEED inside the slow windows (set_slow_windows), whatever the chosen speed;
the clock is advanced window by window, so a high speed cannot jump over one.
"""

from __future__ import annotations

import bisect
import math
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
# Phase 2: SATELLITE DETECTION with the time of a satellite pass starts a sequence the
# operator steps through with `next`, in their own time.
DETECTION_STEPS = ("acquired", "anomaly", "downlink", "zoom", "iot", "correlate")
DETECTION_BEFORE, DETECTION_AFTER = timedelta(minutes=2), timedelta(minutes=6)
# Events mission control can trigger. Toggles switch a view on and off; the others
# are kept until `reset`. `target` names a sensor or road and is optional.
EVENT_KINDS = (
    "satellite_detection", "sensor_failure", "satcom_failure", "satcom_restore",
    "road_closed", "power_failure", "plus60", "god_view", "filter", "space_view", "iot",
    "place_sensor",
)
# Sensors the operator places from the main screen's map: at most this many, named P1, P2 …
MAX_PLACED_SENSORS = 10
# Map categories mission control can hide; maritime, aviation and emergency are not in the demo.
FILTERS = ("space", "iot", "infrastructure", "weather")
TOGGLES = ("plus60", "god_view", "space_view")
TARGET_PATTERN = re.compile(r"[a-z0-9_-]{1,64}")
IMAGE_PATTERN = re.compile(r"auto|off|[A-Za-z0-9_]{1,80}\|[a-z]{1,20}")
IMAGE_TYPES_PATTERN = re.compile(r"(?:[a-z]{1,20}(?:,[a-z]{1,20}){0,19})?")
CHOICE_PATTERN = re.compile(r"[a-z_]{1,32}=[A-Za-z0-9_.:-]{1,40}")
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
    # (min_lat, max_lat, min_lon, max_lon) a placed sensor must lie in; None accepts any position.
    area: tuple[float, float, float, float] | None = None
    monotonic: Callable[[], float] = time.monotonic
    speed: float = DEFAULT_SPEED
    # The saved display profile's ticks ({"image_types", "base_maps"}), read at the start and at every reset.
    profile: Callable[[], dict[str, Any] | None] | None = None
    _clock: datetime = field(init=False)
    _playing: bool = field(default=False, init=False)
    _since: float = field(default=0.0, init=False)
    revision: int = field(default=0, init=False)
    jump: int = field(default=0, init=False)  # increases when the clock moves other than by playing
    log: list[dict[str, Any]] = field(default_factory=list, init=False)
    events: list[dict[str, Any]] = field(default_factory=list, init=False)
    event_seq: int = field(default=0, init=False)
    _slow: list[tuple[datetime, datetime]] = field(default_factory=list, init=False)
    _detection: dict[str, Any] | None = field(default=None, init=False)
    _image: str = field(default="auto", init=False)
    _image_types: list[str] | None = field(default=None, init=False)
    _base_maps: list[str] | None = field(default=None, init=False)
    _camera: dict[str, Any] = field(default_factory=lambda: {"target": None, "seq": 0}, init=False)
    _map_layers: dict[str, bool] = field(default_factory=dict, init=False)
    _choices: dict[str, str] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self._clock = self.start
        self._since = self.monotonic()
        self._apply_profile()

    def _apply_profile(self) -> None:
        saved = (self.profile() if self.profile else None) or {}
        self._image_types = saved.get("image_types")
        self._base_maps = saved.get("base_maps")

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
                "status": {**self._status(), "detection": self._detection_status(), "image": self._image,
                           "image_types": None if self._image_types is None else list(self._image_types),
                           "base_maps": None if self._base_maps is None else list(self._base_maps),
                           "camera": dict(self._camera), "map_layers": dict(self._map_layers),
                           "choices": dict(self._choices)},
            }

    def _status(self) -> dict[str, Any]:
        """The state the events add up to, so a screen that connects late shows the same."""
        status: dict[str, Any] = {
            "satcom_up": True, "plus60": False, "god_view": False, "space_view": False, "power_failure": False,
            "failed_sensors": [], "closed_roads": [], "satcom_down_since": None, "last_outage": None,
            "hidden_layers": [],
            # IoT on or off from mission control: off leaves every sensor out of the screens and the assessment.
            "iot": True,
            "placed_sensors": [],
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
            elif kind == "iot":
                status["iot"] = not status["iot"]
            elif kind == "place_sensor":
                number = len(status["placed_sensors"]) + 1
                status["placed_sensors"].append({"id": target, "name": f"Sensor P{number}",
                                                 "latitude": event["latitude"], "longitude": event["longitude"]})
            elif kind == "filter":
                hidden = status["hidden_layers"]
                hidden.remove(target) if target in hidden else hidden.append(target)
        return status

    def _detection_status(self) -> dict[str, Any] | None:
        if self._detection is None:
            return None
        step = self._detection["step"]
        return {"pass_utc": self._detection["pass_utc"], "step": step, "name": DETECTION_STEPS[step], "steps": len(DETECTION_STEPS)}

    def _start_detection(self, at: str) -> None:
        """Stand just before the pass, paused, so the operator tells the sequence step by step."""
        try:
            moment = parse_utc(at)
        except ValueError as exc:
            raise CommandError("invalid pass time") from exc
        self._detection = {"pass_utc": utc_text(moment), "step": 0}
        self._playing = False
        self._clock = max(self.start, min(self.end, moment - DETECTION_BEFORE))
        self.jump += 1

    def _next_detection_step(self) -> None:
        if self._detection is None:
            raise CommandError("no detection sequence to step through")
        self._detection["step"] += 1
        step = self._detection["step"]
        if step >= len(DETECTION_STEPS):
            self._detection = None
            return
        if DETECTION_STEPS[step] == "zoom":
            # The pass's detections appear on the map.
            self._clock = min(self.end, parse_utc(self._detection["pass_utc"]) + DETECTION_AFTER)
            self.jump += 1

    def _record_event(self, kind: str, target: str | None, **extra: Any) -> None:
        if target is not None and not TARGET_PATTERN.fullmatch(target):
            raise CommandError("target must be 1–64 characters a-z, 0-9, _ or -")
        if kind == "filter" and target not in FILTERS:
            raise CommandError(f"filter needs a target: {', '.join(FILTERS)}")
        self.event_seq += 1
        self.events.append({"seq": self.event_seq, "kind": kind, "target": target, "clock_utc": utc_text(self._clock), **extra})
        del self.events[:-MAX_EVENTS]

    def _place_sensor(self, latitude: float | None, longitude: float | None) -> None:
        if latitude is None or longitude is None or not (math.isfinite(latitude) and math.isfinite(longitude)):
            raise CommandError("place_sensor needs a latitude and a longitude")
        if self.area is not None:
            min_lat, max_lat, min_lon, max_lon = self.area
            if not (min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon):
                raise CommandError("the sensor must be placed inside the map area")
        placed = sum(1 for event in self.events if event["kind"] == "place_sensor")
        if placed >= MAX_PLACED_SENSORS:
            raise CommandError(f"at most {MAX_PLACED_SENSORS} placed sensors")
        self._record_event("place_sensor", f"placed-{placed + 1}", latitude=round(latitude, 5), longitude=round(longitude, 5))

    def command(
        self, name: str, *, at: str | None = None, speed: float | None = None, target: str | None = None,
        latitude: float | None = None, longitude: float | None = None,
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
                self._detection = None
                self._image = "auto"
                self._apply_profile()
                self._map_layers.clear()
                self._choices.clear()
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
            elif name == "satellite_detection" and at:
                self._start_detection(at)
                self._record_event(name, target)
            elif name == "next":
                self._next_detection_step()
            elif name == "place_sensor":
                self._place_sensor(latitude, longitude)
            elif name == "image":
                if target is None or not IMAGE_PATTERN.fullmatch(target):
                    raise CommandError('image needs "auto", "off" or "scene|image"')
                self._image = target
            elif name == "image_types":
                if target is None or not IMAGE_TYPES_PATTERN.fullmatch(target):
                    raise CommandError('image_types needs image types separated by commas, for example "radar,natural"')
                self._image_types = list(dict.fromkeys(target.split(","))) if target else []
            elif name == "choose":
                if target is None or not CHOICE_PATTERN.fullmatch(target):
                    raise CommandError('choose needs "key=value"')
                key, _, value = target.partition("=")
                self._choices[key] = value
            elif name in ("map_layer_on", "map_layer_off"):
                if not target or len(target) > 120:
                    raise CommandError(f"{name} needs a layer name")
                self._map_layers[target] = name == "map_layer_on"
            elif name == "camera":
                if target not in ("incident", "home"):
                    raise CommandError('camera needs "incident" or "home"')
                self._camera = {"target": target, "seq": self._camera["seq"] + 1}
            elif name == "base_maps":
                if target is None or not IMAGE_TYPES_PATTERN.fullmatch(target):
                    raise CommandError('base_maps needs base maps separated by commas, for example "offline,online"')
                self._base_maps = list(dict.fromkeys(target.split(","))) if target else []
            elif name in EVENT_KINDS:
                self._record_event(name, target)
            else:
                raise CommandError(f"unknown command: {name}")
            self.revision += 1
            self.log.append({"command": name, "at": at, "speed": speed, "target": target, "clock_utc": utc_text(self._clock), "revision": self.revision})
            del self.log[:-100]
        return self.snapshot()
