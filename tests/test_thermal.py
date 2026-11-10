"""Independent analytical heat-balance checks, not physical vehicle validation."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.frost_risks.thermal import GlassState, HeatingHistory, parameters

NOW = datetime(2026, 11, 10, 5, 0, tzinfo=UTC)


def step(state, minutes=0, inside=20, outside=0, unheated=-2, config=None):
    return state.advance(
        NOW + timedelta(minutes=minutes),
        unheated=unheated,
        inside=inside,
        outside=outside,
        config=config or {},
    )


def test_analytical_capacity_equilibrium_and_one_time_constant():
    state = GlassState()
    first = step(state)
    # Independent oracle: 2500kg/m3 * 720J/kgK * .0045m = 8100J/m2K;
    # h=5+15=20W/m2K, tau=405s and T_eq=-2+5/20*20=3C.
    assert first["capacity_j_m2k"] == 8100
    assert first["time_constant_seconds"] == 405
    assert first["equilibrium_temperature"] == 3
    assert state.temperature == -2  # No instantaneous or retroactive heating.
    step(state, minutes=405 / 60)
    assert state.temperature == pytest.approx(3 - 5 / math.e)


def test_previous_boundary_owns_elapsed_interval_and_cooling_has_inertia():
    state = GlassState()
    step(state, inside=0)
    step(state, minutes=1, inside=20)
    assert state.temperature == -2  # Reading at t=1 did not exist at t=0.
    step(state, minutes=10)
    before = state.temperature
    step(state, minutes=10, inside=0)
    assert state.temperature == before
    step(state, minutes=11, inside=0)
    assert -2 < state.temperature < before


def test_unheated_baseline_preserved_when_inside_equals_outside():
    state = GlassState()
    step(state, inside=0)
    for minute in range(1, 100):
        step(state, minutes=minute, inside=0)
        assert state.temperature == -2


def test_long_gap_does_not_replay_warm_boundary_and_clock_backwards_is_conservative():
    state = GlassState()
    step(state)
    assert step(state, minutes=120)["status"] == "history_gap_unheated"
    assert state.temperature == -2
    assert step(state, minutes=119)["status"] == "history_gap_unheated"
    assert state.temperature == -2


def test_persistence_matches_uninterrupted_analytic_trajectory():
    direct = GlassState()
    step(direct)
    step(direct, minutes=3)
    restored = GlassState.restore(direct.serialize(), NOW + timedelta(minutes=3))
    step(direct, minutes=5)
    step(restored, minutes=5)
    assert restored.temperature == pytest.approx(direct.temperature)


def test_restart_with_colder_boundary_does_not_replay_old_cabin_warmth():
    original = GlassState()
    step(original, inside=20)
    restored = GlassState.restore(original.serialize(), NOW + timedelta(minutes=10))
    result = step(restored, minutes=10, inside=0)
    assert restored.temperature == -2
    assert result["status"] == "restored_gap_conservative_boundary"


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), -1, 0, 1000])
def test_invalid_parameters_are_rejected(bad):
    with pytest.raises(ValueError):
        parameters({"inside_heat_transfer": bad})


def test_corrupt_or_future_persisted_glass_cannot_retain_warmth():
    for data in [
        None,
        {},
        {"temperature": 50, "updated_at": (NOW + timedelta(hours=1)).isoformat()},
        {"temperature": "nan", "updated_at": NOW.isoformat()},
    ]:
        assert GlassState.restore(data, NOW).temperature is None


def test_heating_edges_are_separate_from_clearance_and_restore():
    state = HeatingHistory()
    assert not state.observe(False, NOW)
    assert state.last_ended_at is None
    assert not state.observe(True, NOW + timedelta(minutes=1))
    restored = HeatingHistory.restore(state.serialize(), NOW + timedelta(minutes=2))
    assert restored.observe(False, NOW + timedelta(minutes=6))
    assert restored.last_duration_seconds == 300
    assert restored.last_ended_at == NOW + timedelta(minutes=6)
    assert "not_confirmed_surface_clearance" in restored.diagnostics()["meaning"]


def test_unknown_or_long_observation_gap_is_not_a_proven_heating_end():
    state = HeatingHistory()
    state.observe(True, NOW)
    state.observe(None, NOW + timedelta(minutes=1))
    assert not state.observe(False, NOW + timedelta(minutes=2))
    state.observe(True, NOW + timedelta(minutes=3))
    assert not state.observe(False, NOW + timedelta(hours=3))
    assert state.last_ended_at is None
