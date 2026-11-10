from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_home_assistant import make_runtime, set_weather

from custom_components.frost_risks.const import DOMAIN
from custom_components.frost_risks.runtime import FrostRuntime


def inside(hass, value="20", unit="°C"):
    hass.states.async_set("sensor.inside", value, {"unit_of_measurement": unit})


async def test_warming_reduces_frost_without_clear_and_cooling_recurs_gradually(hass, freezer):
    now = dt_util.utcnow()
    set_weather(hass, temperature=0, humidity=95, cloud_coverage=None, wind_speed=None)
    inside(hass)
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Car",
            "weather_entity": "weather.local",
            "interior_temperature_sensor": "sensor.inside",
        },
    )
    assert runtime.data.assessment.level == 3
    assert runtime.evidence.cleared_at is None
    for minute in range(1, 21):
        freezer.move_to(now + timedelta(minutes=minute))
        set_weather(hass, temperature=0, humidity=95, cloud_coverage=None, wind_speed=None)
        inside(hass)
        await runtime.async_refresh()
    assert runtime.data.assessment.level == 0
    assert runtime.data.assessment.surface_basis == "thermal_rc_estimate"
    assert runtime.data.assessment.quality == "limited"
    assert "surface_or_complete_radiation_context" in runtime.data.assessment.missing
    assert runtime.evidence.cleared_at is None
    warm = runtime.data.assessment.surface_temperature
    inside(hass, "0")
    await runtime.async_refresh()
    assert runtime.data.assessment.surface_temperature == warm
    levels = []
    for minute in range(21, 41):
        freezer.move_to(now + timedelta(minutes=minute))
        set_weather(hass, temperature=0, humidity=95, cloud_coverage=None, wind_speed=None)
        inside(hass, "0")
        await runtime.async_refresh()
        levels.append(runtime.data.assessment.level)
    assert 1 in levels and levels[-1] == 3
    await runtime.async_stop()


async def test_stale_outdoor_input_with_fresh_cabin_cannot_reduce_risk(hass, freezer):
    now = dt_util.utcnow()
    set_weather(hass, temperature=0, humidity=95)
    inside(hass)
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Car",
            "weather_entity": "weather.local",
            "interior_temperature_sensor": "sensor.inside",
        },
    )
    freezer.move_to(now + timedelta(minutes=16))
    inside(hass)
    await runtime.async_refresh()
    assert runtime.data.assessment.level == 3
    assert runtime.data.assessment.surface_basis != "thermal_rc_estimate"
    assert runtime.thermal_diagnostics["status"] == "unheated_fallback_missing_input"
    await runtime.async_stop()


async def test_measured_surface_has_priority_over_warm_cabin(hass):
    set_weather(hass, temperature=0, humidity=95)
    inside(hass)
    hass.states.async_set("sensor.glass", "-3", {"unit_of_measurement": "°C"})
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Car",
            "weather_entity": "weather.local",
            "interior_temperature_sensor": "sensor.inside",
            "surface_temperature_sensor": "sensor.glass",
        },
    )
    assert runtime.data.assessment.surface_basis == "measured"
    assert runtime.data.assessment.surface_temperature == -3
    assert runtime.thermal_diagnostics["status"] == "measured_surface_priority"
    await runtime.async_stop()


async def test_thermal_option_does_not_erase_existing_snow_memory(hass):
    set_weather(hass, "snowy", temperature=0)
    runtime, entry = await make_runtime(hass, {"name": "Car", "weather_entity": "weather.local"})
    original_snow = runtime.evidence.snow_at
    await runtime.async_stop()
    inside(hass)
    set_weather(hass, "cloudy", temperature=0)
    hass.config_entries.async_update_entry(
        entry, options={"interior_temperature_sensor": "sensor.inside"}
    )
    restored = FrostRuntime(hass, entry)
    await restored.async_start()
    assert restored.evidence.snow_at == original_snow
    assert restored.data.assessment.level == 4
    assert restored.memory_status == "restored"
    await restored.async_stop()


async def test_stale_or_unavailable_inside_cannot_keep_a_warm_estimate(hass, freezer):
    now = dt_util.utcnow()
    set_weather(hass, temperature=0, humidity=95)
    inside(hass, "68", "°F")
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Car",
            "weather_entity": "weather.local",
            "interior_temperature_sensor": "sensor.inside",
        },
    )
    assert runtime.data.observation.interior_temperature == 20
    freezer.move_to(now + timedelta(minutes=16))
    await runtime.async_refresh()
    assert runtime.thermal_diagnostics["status"] == "unheated_fallback_missing_input"
    assert runtime.data.assessment.surface_basis != "thermal_rc_estimate"
    assert "thermal_input_unavailable_or_stale" in runtime.data.assessment.missing
    await runtime.async_stop()


async def test_heating_end_persists_without_clearing_ice_evidence(hass, freezer):
    now = dt_util.utcnow()
    set_weather(hass, "snowy", temperature=0)
    hass.states.async_set("switch.defrost", "off")
    runtime, entry = await make_runtime(
        hass,
        {
            "name": "Car",
            "weather_entity": "weather.local",
            "surface_heating_entity": "switch.defrost",
        },
    )
    assert runtime.heating.last_ended_at is None
    hass.states.async_set("switch.defrost", "on")
    await runtime.async_refresh()
    freezer.move_to(now + timedelta(minutes=5))
    hass.states.async_set("switch.defrost", "off")
    await runtime.async_refresh()
    assert runtime.heating.last_duration_seconds == 300
    assert runtime.evidence.cleared_at is None
    assert runtime.evidence.snow_at is not None
    stored = await runtime.store.async_load()
    assert stored["heating"]["last_ended_at"] is not None
    await runtime.async_stop()
    restored = FrostRuntime(hass, entry)
    await restored.async_start()
    assert restored.heating.last_ended_at == now + timedelta(minutes=5)
    assert restored.evidence.cleared_at is None
    await restored.async_stop()


async def test_manual_clear_keeps_thermal_temperature_not_artificial_warmth(hass):
    set_weather(hass, temperature=0, humidity=95)
    inside(hass, "0")
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Car",
            "weather_entity": "weather.local",
            "interior_temperature_sensor": "sensor.inside",
        },
    )
    before = runtime.glass.temperature
    await runtime.async_clear_surface()
    assert runtime.evidence.cleared_at is not None
    assert runtime.glass.temperature == before
    assert runtime.data.assessment.level == 0
    await runtime.async_stop()


async def test_options_can_configure_and_remove_thermal_sources_without_changing_weather(hass):
    set_weather(hass)
    inside(hass)
    hass.states.async_set("switch.defrost", "off")
    entry = MockConfigEntry(domain=DOMAIN, data={"name": "Car", "weather_entity": "weather.local"})
    entry.add_to_hass(hass)
    form = await hass.config_entries.options.async_init(entry.entry_id)
    saved = await hass.config_entries.options.async_configure(
        form["flow_id"],
        {
            "name": "Car",
            "weather_entity": "weather.local",
            "interior_temperature_sensor": "sensor.inside",
            "surface_heating_entity": "switch.defrost",
            "inside_heat_transfer": 7.0,
        },
    )
    assert saved["type"] == "create_entry"
    assert entry.options["inside_heat_transfer"] == 7.0
    form = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        form["flow_id"],
        {
            "name": "Car",
            "weather_entity": "weather.local",
        },
    )
    assert entry.options["interior_temperature_sensor"] is None
    assert entry.options["surface_heating_entity"] is None
    assert entry.options["weather_entity"] == "weather.local"


async def test_missing_sources_error_has_precedence_over_invalid_thermal_parameters(hass):
    from custom_components.frost_risks.config_flow import _validate

    assert _validate(hass, {"name": "Car", "inside_heat_transfer": 0}) == {
        "base": "sources_required"
    }


async def test_live_ha_outputs_expose_estimated_basis_and_separate_heat_history(hass):
    from homeassistant.helpers import entity_registry

    set_weather(hass, temperature=0, humidity=95)
    inside(hass)
    hass.states.async_set("switch.defrost", "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="thermal-output",
        data={
            "name": "Car",
            "weather_entity": "weather.local",
            "interior_temperature_sensor": "sensor.inside",
            "surface_heating_entity": "switch.defrost",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = entity_registry.async_get(hass)
    surface = hass.states.get(
        registry.async_get_entity_id("sensor", DOMAIN, "thermal-output_surface_temperature")
    )
    advisory = hass.states.get(
        registry.async_get_entity_id("binary_sensor", DOMAIN, "thermal-output_defrost_recommended")
    )
    assert surface.attributes["surface_basis"] == "thermal_rc_estimate"
    assert surface.attributes["calibration"] == "uncalibrated_reference_glass"
    assert advisory.attributes["heating_history"]["configured"] is True
    assert advisory.attributes["heating_history"]["last_heating_ended_at"] is None
    assert advisory.attributes["evidence"]["cleared_at"] is None
    assert await hass.config_entries.async_unload(entry.entry_id)
