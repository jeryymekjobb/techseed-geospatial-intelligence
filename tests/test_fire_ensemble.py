"""Tests for the ensemble Kalman filter (tools/fire_ensemble.py) on an invented fire whose
true rate factor and turn are known: the filter must find them from the observed spread."""

from __future__ import annotations

import math
import statistics

import pytest

from tools import fire_spread as fs
from tools.fire_ensemble import EnsembleFilter, Member, Settings, invert, kalman_gain, member_steps, reach_fraction, turn

STEP = fs.SpreadStep(150.0, 15.0, 2.0, 0.0)  # 150 m/h towards north
START = [(-100.0, -100.0), (100.0, -100.0), (100.0, 100.0), (-100.0, 100.0)]


def run_against(truth: Member, seed: int, passes: int = 6, hours: int = 6) -> EnsembleFilter:
    """Observe the truth's spread pass by pass, as the hindcast observes the detections."""
    ensemble = EnsembleFilter(seed=seed)
    hull = list(START)
    for index in range(passes):
        steps = [STEP] * hours
        front = fs.forecast(hull, member_steps(steps, truth))[-1]
        advance, direction = fs.observed_advance(hull, front)
        if index:
            ensemble.predict()
        ensemble.update(hull, steps, advance, direction)
        hull = front
    return ensemble


def test_turns_fold_into_half_circles() -> None:
    assert turn(350 - 10) == -20 and turn(10 - 350) == 20 and turn(180) == -180


def test_the_gain_matches_the_scalar_formula() -> None:
    assert invert([[2.0, 1.0], [1.0, 1.0]]) == [[1.0, -1.0], [-1.0, 2.0]]
    states = [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]
    predicted = [[0.0], [10.0], [20.0]]  # y = 10 x
    gain = kalman_gain(states, predicted, [10.0])
    # C_xy = 10, C_yy = 100 + R 100 -> K = 10 / 200 for the first parameter, 0 for the second.
    assert gain[0][0] == pytest.approx(0.05) and gain[1][0] == pytest.approx(0.0)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_filter_finds_a_known_rate_and_turn(seed: int) -> None:
    truth = Member(math.log(2.0), 25.0)
    ensemble = run_against(truth, seed)
    means = ensemble.means()
    assert math.exp(means["log_k"]) == pytest.approx(2.0, abs=0.3)
    assert means["delta"] == pytest.approx(25.0, abs=6.0)
    # The spread of the ensemble has narrowed from the prior.
    assert statistics.stdev(member.log_k for member in ensemble.members) < Settings().log_k_sd / 2


def test_a_slower_fire_than_the_model_is_found_too() -> None:
    # 75 m/h: fourteen-hour intervals (about 1 050 m) give the 1 km advance a direction needs.
    ensemble = run_against(Member(math.log(0.5), -15.0), seed=4, hours=14)
    assert math.exp(ensemble.means()["log_k"]) == pytest.approx(0.5, abs=0.15)
    assert ensemble.means()["delta"] == pytest.approx(-15.0, abs=8.0)


def test_without_a_clear_advance_the_turn_keeps_its_prior() -> None:
    # Six hours at 75 m/h is under 1 km: the rate is learned, the turn is left alone.
    ensemble = run_against(Member(math.log(0.5), -15.0), seed=4)
    assert math.exp(ensemble.means()["log_k"]) == pytest.approx(0.5, abs=0.15)
    assert abs(ensemble.means()["delta"]) < 6.0


def test_a_small_advance_does_not_steer_the_direction() -> None:
    ensemble = EnsembleFilter(seed=5)
    before = [member.delta for member in ensemble.members]
    # 400 m with a direction far off: below the 1 km for directions, so only the rate moves.
    ensemble.update(START, [STEP] * 2, 400.0, 180.0)
    assert [member.delta for member in ensemble.members] == pytest.approx(before, abs=1e-9)


def test_the_same_seed_gives_the_same_result() -> None:
    first = run_against(Member(math.log(2.0), 25.0), seed=7, passes=2).means()
    second = run_against(Member(math.log(2.0), 25.0), seed=7, passes=2).means()
    assert first == second


def test_the_reach_fraction_counts_the_members_whose_front_contains_a_point() -> None:
    small = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
    large = [(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)]
    assert reach_fraction((3.0, 0.0), [small, large, large, small]) == 0.5
    assert reach_fraction((0.0, 0.0), [small, large]) == 1.0 and reach_fraction((9.0, 0.0), [small]) == 0.0
