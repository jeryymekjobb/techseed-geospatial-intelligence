"""Ensemble Kalman filter for the fire-spread forecast (plan: reports/2026-10-05-plan-datassimilering-brandprognos-claude-opus-5-5.md).

Each ensemble member is the forecast model of tools/fire_spread.py (FBP rate of
spread, elliptical growth from the front) with two parameters of its own:

- `log_k`, the logarithm of a factor on the rate of spread;
- `delta`, a turn in degrees of the spread direction from the downwind direction.

At each satellite pass the filter compares what every member predicts for the
interval since the previous pass - the advance of the front and its direction,
measured exactly as the hindcast measures the observed spread
(`fire_spread.observed_advance`) - with what the detections show, and moves the
parameters by the standard update with perturbed observations. The advance only
updates the rate and the direction only updates the turn (localisation): with 50
members, chance correlations between, say, the turn and the advance would otherwise
move a parameter the observation says nothing about. Between passes a little
process noise lets the ensemble follow a fire that changes behaviour.

All settings are fixed in `Settings` before any test is run; the hindcast must
not tune them. Only the standard library is used.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Sequence

from tools import fire_spread as fs


@dataclass(frozen=True)
class Settings:
    size: int = 50
    log_k_sd: float = 0.7           # prior: about a factor of two on the rate
    delta_sd: float = 20.0          # prior: degrees off the downwind direction
    process_log_k_sd: float = 0.15  # added between passes
    process_delta_sd: float = 5.0
    advance_error_m: float = 500.0  # observation error: the larger of this and
    advance_error_share: float = 0.3  # this share of the observed advance
    direction_error_deg: float = 20.0
    min_direction_advance_m: float = 1000.0  # direction only counts for a clear advance


@dataclass
class Member:
    log_k: float
    delta: float

    @property
    def k(self) -> float:
        return math.exp(self.log_k)


def turn(degrees: float) -> float:
    """An angle difference folded into -180..180."""
    return (degrees + 180.0) % 360.0 - 180.0


def member_steps(steps: Sequence[fs.SpreadStep], member: Member) -> list[fs.SpreadStep]:
    """The model's hourly steps with the member's rate factor and turn."""
    return [fs.SpreadStep(step.ros_m_per_h * member.k, step.back_m_per_h * member.k, step.lb,
                          (step.towards_deg + member.delta) % 360.0) for step in steps]


def predicted_spread(hull: Sequence[fs.Point], steps: Sequence[fs.SpreadStep], member: Member,
                     min_distance_m: float = 300.0) -> tuple[float, float | None]:
    """Advance and direction the member predicts over the steps, measured like the observations."""
    fronts = fs.forecast(hull, member_steps(steps, member))
    if not fronts:
        return 0.0, None
    return fs.observed_advance(hull, fronts[-1], min_distance_m)


@dataclass
class EnsembleFilter:
    settings: Settings = field(default_factory=Settings)
    seed: int | None = None
    members: list[Member] = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        s = self.settings
        self.members = [Member(self.rng.gauss(0.0, s.log_k_sd), self.rng.gauss(0.0, s.delta_sd)) for _ in range(s.size)]

    def predict(self) -> None:
        """Process noise between passes."""
        s = self.settings
        for member in self.members:
            member.log_k += self.rng.gauss(0.0, s.process_log_k_sd)
            member.delta += self.rng.gauss(0.0, s.process_delta_sd)

    def update(self, hull: Sequence[fs.Point], steps: Sequence[fs.SpreadStep],
               observed_advance_m: float, observed_direction_deg: float | None) -> dict[str, float]:
        """Update the parameters with the spread observed over the steps since `hull`.

        Returns the ensemble means before and after, for the report.
        """
        s = self.settings
        predictions = [predicted_spread(hull, steps, member) for member in self.members]
        use_direction = observed_direction_deg is not None and observed_advance_m >= s.min_direction_advance_m
        # Observation vectors: advance, and the turn of the direction from each member's own prediction.
        observed: list[float] = [observed_advance_m]
        errors: list[float] = [max(s.advance_error_m, s.advance_error_share * observed_advance_m)]
        if use_direction:
            observed.append(0.0)
            errors.append(s.direction_error_deg)
        predicted = []
        for advance, direction in predictions:
            row = [advance]
            if use_direction:
                # The direction is compared as a turn relative to the observed one, which keeps it continuous.
                row.append(0.0 if direction is None else turn(direction - observed_direction_deg))
            predicted.append(row)
        before = self.means()
        states = [[member.log_k, member.delta] for member in self.members]
        gain = kalman_gain(states, predicted, errors)
        # Localisation: the advance (observation 0) informs the rate (state 0), the direction
        # (observation 1) the turn (state 1); chance cross-correlations are dropped.
        gain[1][0] = 0.0
        if use_direction:
            gain[0][1] = 0.0
        for member, state, row in zip(self.members, states, predicted):
            innovation = [obs + self.rng.gauss(0.0, err) - pred for obs, err, pred in zip(observed, errors, row)]
            member.log_k = state[0] + sum(gain[0][j] * innovation[j] for j in range(len(innovation)))
            member.delta = state[1] + sum(gain[1][j] * innovation[j] for j in range(len(innovation)))
        return {"log_k_before": before["log_k"], "log_k_after": self.means()["log_k"],
                "delta_before": before["delta"], "delta_after": self.means()["delta"]}

    def means(self) -> dict[str, float]:
        return {"log_k": statistics.fmean(m.log_k for m in self.members),
                "delta": statistics.fmean(m.delta for m in self.members),
                "k": statistics.fmean(m.k for m in self.members)}

    def forecast(self, hull: Sequence[fs.Point], steps: Sequence[fs.SpreadStep]) -> list[list[list[fs.Point]]]:
        """Every member's fronts after each step: [member][hour] -> front."""
        return [fs.forecast(hull, member_steps(steps, member)) for member in self.members]


def kalman_gain(states: list[list[float]], predicted: list[list[float]], errors: list[float]) -> list[list[float]]:
    """K = C_xy (C_yy + R)^-1 from the ensemble, for one or two observations."""
    n = len(states)
    mean_x = [statistics.fmean(row[i] for row in states) for i in range(len(states[0]))]
    mean_y = [statistics.fmean(row[j] for row in predicted) for j in range(len(predicted[0]))]
    cxy = [[sum((states[m][i] - mean_x[i]) * (predicted[m][j] - mean_y[j]) for m in range(n)) / (n - 1)
            for j in range(len(mean_y))] for i in range(len(mean_x))]
    cyy = [[sum((predicted[m][a] - mean_y[a]) * (predicted[m][b] - mean_y[b]) for m in range(n)) / (n - 1)
            + (errors[a] ** 2 if a == b else 0.0) for b in range(len(mean_y))] for a in range(len(mean_y))]
    inverse = invert(cyy)
    return [[sum(cxy[i][a] * inverse[a][j] for a in range(len(mean_y))) for j in range(len(mean_y))] for i in range(len(mean_x))]


def invert(matrix: list[list[float]]) -> list[list[float]]:
    if len(matrix) == 1:
        return [[1.0 / matrix[0][0]]]
    (a, b), (c, d) = matrix
    determinant = a * d - b * c
    return [[d / determinant, -b / determinant], [-c / determinant, a / determinant]]


def reach_fraction(point: fs.Point, fronts: Sequence[Sequence[fs.Point]]) -> float:
    """Share of the members' fronts (for one horizon) that contain the point."""
    return sum(1 for front in fronts if fs.inside_convex(point, front)) / len(fronts) if fronts else 0.0
