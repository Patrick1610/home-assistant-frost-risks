from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.frost_risks.risk import Evidence, Observation, assess

NOW = datetime(2026, 10, 27, 7, tzinfo=UTC)


def context(temperature, humidity, **kwargs):
    return Observation(
        temperature,
        humidity,
        cloud_coverage=100,
        wind_m_s=6,
        night=True,
        rain=False,
        snow=False,
        **kwargs,
    )


@pytest.mark.parametrize(("temperature", "humidity"), [(10, 30), (10, 20), (-5, 10), (0, 0)])
def test_dry_air_does_not_create_a_high_ice_risk(temperature, humidity):
    result = assess(context(temperature, humidity), Evidence(), NOW)
    assert result.recommended is False
    assert result.level <= 1


def test_clear_calm_humid_night_can_form_frost_above_zero_air_temperature():
    clear = Observation(2, 90, cloud_coverage=10, wind_m_s=1, night=True, rain=False, snow=False)
    result = assess(clear, Evidence(), NOW)
    assert result.recommended is True
    assert result.reason == "surface_frost_possible"
    assert result.surface_temperature == -1
    cloudy = assess(replace(clear, cloud_coverage=100, wind_m_s=6), Evidence(), NOW)
    assert cloudy.recommended is False
    assert cloudy.surface_temperature == 1.5


def test_daylight_reduces_radiation_allowance():
    result = assess(
        Observation(2, 90, cloud_coverage=0, wind_m_s=0, night=False, rain=False, snow=False),
        Evidence(),
        NOW,
    )
    assert result.recommended is False
    assert result.surface_basis == "weather_heuristic"
    assert result.surface_temperature == 2


def test_measured_surface_overrides_an_atmospheric_frost_estimate():
    result = assess(context(0, 95, surface_temperature=3), Evidence(), NOW)
    assert result.recommended is False
    assert result.surface_basis == "measured"


def test_extreme_dry_cold_is_no_ice_evidence_not_missing_humidity():
    result = assess(context(-40, 1), Evidence(), NOW)
    assert result.recommended is False
    assert result.reason == "dry_no_ice_evidence"


def test_plain_temperature_humidity_setup_is_usable_but_labels_missing_context():
    result = assess(Observation(0, 95), Evidence(), NOW)
    assert result.recommended is True
    assert result.quality == "limited"
    assert result.surface_basis == "limited_air_screening"
    assert "surface_or_complete_radiation_context" in result.missing


def test_rain_then_freeze_and_rising_temperature_do_not_immediately_erase_ice():
    memory = Evidence()
    rain = replace(context(5, 90), rain=True, rain_reported_at=NOW)
    assert assess(rain, memory, NOW).recommended is False
    cold_time = NOW + timedelta(hours=1)
    result = assess(context(-2, 40), memory, cold_time)
    assert result.reason == "frozen_wet_surface"
    result = assess(context(1, 60), memory, cold_time + timedelta(minutes=10))
    assert result.reason == "residual_ice"


def test_snow_ending_and_restart_preserve_evidence_without_air_data():
    memory = Evidence()
    snow = replace(context(0, 90), snow=True, snow_reported_at=NOW)
    assert assess(snow, memory, NOW).reason == "recent_snow"
    restored = Evidence.restore(memory.serialize(), NOW + timedelta(hours=1))
    result = assess(Observation(None, None), restored, NOW + timedelta(hours=1))
    assert result.recommended is True
    assert result.reason == "recent_snow"


def test_clear_is_acknowledgement_not_a_vehicle_action_and_new_snow_relatches():
    memory = Evidence(snow_at=NOW)
    cleared = NOW + timedelta(minutes=10)
    memory.clear(cleared)
    old_report = replace(context(5, 50), snow=True, snow_reported_at=NOW)
    assert assess(old_report, memory, cleared).recommended is False
    new_report = replace(old_report, snow_reported_at=cleared + timedelta(minutes=1))
    assert assess(new_report, memory, cleared + timedelta(minutes=1)).recommended is True


def test_atmospheric_frost_can_recur_after_a_bounded_post_clear_hold():
    memory = Evidence()
    memory.clear(NOW)
    cold = context(-1, 100)
    assert assess(cold, memory, NOW + timedelta(minutes=1)).reason == "surface_cleared"
    assert assess(cold, memory, NOW + timedelta(minutes=6)).recommended is True


def test_missing_required_sources_are_unknown_not_zero_demand():
    result = assess(Observation(None, None, missing=("temperature", "humidity")), Evidence(), NOW)
    assert result.recommended is None
    assert result.quality == "unknown"


def test_bad_and_future_storage_timestamps_are_ignored():
    restored = Evidence.restore(
        {
            "wet_at": "yesterday",
            "snow_at": (NOW + timedelta(days=1)).isoformat(),
            "ice_at": "2026-10-26T10:00:00",
            "cleared_at": NOW.isoformat(),
        },
        NOW,
    )
    assert restored.wet_at is None
    assert restored.snow_at is None
    assert restored.ice_at is None
    assert restored.cleared_at == NOW


def test_stale_evidence_expires_without_fabricating_a_melt_observation():
    memory = Evidence(snow_at=NOW)
    result = assess(context(10, 50), memory, NOW + timedelta(hours=25))
    assert result.recommended is False
    assert memory.snow_at == NOW
    assert result.quality == "limited"
