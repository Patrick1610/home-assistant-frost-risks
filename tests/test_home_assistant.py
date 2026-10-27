from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.frost_risks.const import DOMAIN, SENSOR_TYPES
from custom_components.frost_risks.runtime import FrostRuntime


def set_weather(hass, state="cloudy", **attrs):
    hass.states.async_set(
        "weather.local",
        state,
        {
            "temperature": 13,
            "temperature_unit": "°C",
            "humidity": 87,
            "wind_speed": 18,
            "wind_speed_unit": "km/h",
            "cloud_coverage": 100,
            **attrs,
        },
    )


async def make_runtime(hass, data, options=None):
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options or {}, entry_id="preserved")
    entry.add_to_hass(hass)
    runtime = FrostRuntime(hass, entry)
    await runtime.async_start()
    return runtime, entry


async def test_existing_entry_loads_same_eight_ids_and_two_new_entities(hass, legacy_config):
    hass.states.async_set("sensor.temperature", "13", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.humidity", "87", {"unit_of_measurement": "%"})
    entry = MockConfigEntry(
        domain=DOMAIN, data=legacy_config, entry_id="same-id", unique_id="old-id"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    from homeassistant.helpers import device_registry, entity_registry

    registry = entity_registry.async_get(hass)
    for key in SENSOR_TYPES:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"same-id_{key}")
        assert entity_id is not None
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, "same-id_defrost_recommended")
    assert registry.async_get_entity_id("button", DOMAIN, "same-id_surface_cleared")
    assert device_registry.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "same-id"), "same-id"
    )
    assert entry.unique_id == "old-id"
    runtime = hass.data[DOMAIN][entry.entry_id]
    assert runtime.data.values["absolute_humidity"] == 9.86
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not runtime._unsubscribers


async def test_weather_only_source_and_fahrenheit_sensor_override(hass):
    set_weather(hass)
    hass.states.async_set("sensor.fahrenheit", "55.4", {"unit_of_measurement": "°F"})
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Local",
            "weather_entity": "weather.local",
            "temperature_sensor": "sensor.fahrenheit",
        },
    )
    assert runtime.data.observation.temperature == pytest.approx(13)
    assert runtime.data.observation.wind_m_s == 5
    assert runtime.data.values["absolute_humidity"] == 9.86
    await runtime.async_stop()


async def test_missing_override_does_not_silently_switch_to_weather(hass):
    set_weather(hass)
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Local",
            "weather_entity": "weather.local",
            "temperature_sensor": "sensor.absent",
        },
    )
    assert runtime.data.observation.temperature is None
    assert runtime.data.assessment.recommended is None
    await runtime.async_stop()


async def test_independent_snow_evidence_survives_missing_air_and_failed_optional_override(hass):
    set_weather(hass, "snowy", temperature=None, humidity=None)
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Local",
            "weather_entity": "weather.local",
            "snow_sensor": "sensor.absent",
        },
    )
    assert runtime.data.assessment.recommended is True
    assert "snow_sensor" in runtime.data.assessment.missing
    await runtime.async_stop()


async def test_options_are_effective_and_optional_sources_can_be_removed(hass, legacy_config):
    set_weather(hass)
    runtime, _ = await make_runtime(
        hass,
        legacy_config,
        {
            "weather_entity": "weather.local",
            "temperature_sensor": None,
            "humidity_sensor": None,
        },
    )
    assert runtime.data.values["absolute_humidity"] == 9.86
    await runtime.async_stop()


async def test_clearing_weather_option_restores_explicit_classic_sensor_setup(hass, legacy_config):
    hass.states.async_set("sensor.temperature", "13", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.humidity", "87")
    runtime, _ = await make_runtime(
        hass, {**legacy_config, "weather_entity": "weather.old"}, {"weather_entity": None}
    )
    assert runtime.data.values["absolute_humidity"] == 9.86
    assert runtime.data.observation.snow is None
    await runtime.async_stop()


async def test_store_and_elapsed_time_survive_reload(hass):
    set_weather(hass, "snowy", temperature=0)
    runtime, entry = await make_runtime(hass, {"name": "Local", "weather_entity": "weather.local"})
    assert runtime.data.assessment.recommended is True
    await runtime.async_stop()
    set_weather(hass, "cloudy", temperature=3)
    restored = FrostRuntime(hass, entry)
    await restored.async_start()
    assert restored.data.assessment.reason == "recent_snow"
    await restored.async_clear_surface()
    assert restored.data.assessment.recommended is False
    await restored.async_stop()


async def test_time_tick_recomputes_even_without_new_sensor_value(hass):
    set_weather(hass, "cloudy", temperature=10)
    runtime, _ = await make_runtime(hass, {"name": "Local", "weather_entity": "weather.local"})
    with patch.object(runtime, "async_refresh", new=AsyncMock()) as refresh:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1, seconds=1))
        await hass.async_block_till_done()
        refresh.assert_awaited_once()
    await runtime.async_stop()


async def test_stale_weather_is_not_treated_as_dry_clear_calm(hass):
    set_weather(hass, "cloudy", temperature=10)
    runtime, _ = await make_runtime(hass, {"name": "Local", "weather_entity": "weather.local"})
    with patch(
        "custom_components.frost_risks.runtime.dt_util.utcnow",
        return_value=dt_util.utcnow() + timedelta(hours=4),
    ):
        await runtime.async_refresh()
    assert runtime.data.assessment.recommended is None
    assert "weather_entity" in runtime.data.assessment.missing
    await runtime.async_stop()


async def test_stale_snow_override_is_missing_not_a_fresh_snow_report(hass, legacy_config):
    hass.states.async_set("sensor.temperature", "10", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.humidity", "30")
    hass.states.async_set("sensor.old_snow", "1")
    runtime, _ = await make_runtime(hass, {**legacy_config, "snow_sensor": "sensor.old_snow"})
    await runtime.async_clear_surface()
    with patch(
        "custom_components.frost_risks.runtime.dt_util.utcnow",
        return_value=dt_util.utcnow() + timedelta(hours=4),
    ):
        await runtime.async_refresh()
    assert runtime.data.observation.snow is None
    assert "snow_sensor" in runtime.data.assessment.missing
    assert runtime.data.assessment.recommended is False
    await runtime.async_stop()


async def test_saving_new_source_binding_does_not_transfer_snow_between_locations(hass):
    set_weather(hass, "snowy")
    runtime, entry = await make_runtime(hass, {"name": "Local", "weather_entity": "weather.local"})
    await runtime.async_stop()
    hass.states.async_set("sensor.temperature", "13", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.humidity", "87")
    hass.config_entries.async_update_entry(
        entry,
        options={
            "weather_entity": None,
            "temperature_sensor": "sensor.temperature",
            "humidity_sensor": "sensor.humidity",
        },
    )
    restored = FrostRuntime(hass, entry)
    await restored.async_start()
    assert restored.memory_status == "new_source_binding"
    assert restored.evidence.snow_at is None
    assert restored.data.assessment.recommended is False
    await restored.async_stop()


async def test_missing_wind_units_are_not_guessed_and_exceptional_weather_is_not_no_snow(hass):
    set_weather(hass, "exceptional", wind_speed_unit=None)
    runtime, _ = await make_runtime(hass, {"name": "Local", "weather_entity": "weather.local"})
    assert runtime.data.observation.wind_m_s is None
    assert runtime.data.observation.snow is None
    assert runtime.data.assessment.quality == "limited"
    await runtime.async_stop()


async def test_options_flow_opens_on_modern_home_assistant_without_property_assignment(
    hass, legacy_config
):
    entry = MockConfigEntry(domain=DOMAIN, data=legacy_config)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_options_flow_saves_weather_source_without_changing_entry_identity(
    hass, legacy_config
):
    set_weather(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=legacy_config, unique_id="keep-identity")
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Updated",
            "weather_entity": "weather.local",
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["temperature_sensor"] is None
    assert entry.options["weather_entity"] == "weather.local"
    assert entry.data == legacy_config
    assert entry.unique_id == "keep-identity"
    assert entry.title == "Updated"


async def test_new_setup_accepts_weather_only_and_rejects_no_sources(hass):
    set_weather(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "No sources"}
    )
    assert result["errors"] == {"base": "sources_required"}
    with patch("custom_components.frost_risks.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Weather",
                "weather_entity": "weather.local",
            },
        )
    assert result["type"] == "create_entry"
    assert result["result"].unique_id == "weather.local"


async def test_invalid_units_degrade_source_not_the_whole_entry(hass):
    set_weather(hass, "snowy", wind_speed_unit="unrecognised-wind-unit")
    hass.states.async_set(
        "sensor.bad_units", "13", {"unit_of_measurement": "unrecognised-temp-unit"}
    )
    runtime, _ = await make_runtime(
        hass,
        {
            "name": "Local",
            "weather_entity": "weather.local",
            "temperature_sensor": "sensor.bad_units",
        },
    )
    assert runtime.last_update_success
    assert runtime.data.observation.temperature is None
    assert runtime.data.observation.wind_m_s is None
    assert runtime.data.assessment.recommended is True
    await runtime.async_stop()


async def test_unknown_advice_keeps_its_diagnostics_visible_in_real_ha_state(hass, legacy_config):
    hass.states.async_set("sensor.temperature", "unavailable")
    hass.states.async_set("sensor.humidity", "unavailable")
    entry = MockConfigEntry(domain=DOMAIN, data=legacy_config, entry_id="diagnostic-id")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_frost_defrost_recommended")
    assert state.state == "unknown"
    assert state.attributes["reason"] == "insufficient_data"
    assert "temperature" in state.attributes["missing_context"]
    assert state.attributes["quality"] == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_binary_state_is_stable_across_unchanged_minute_ticks(hass):
    set_weather(hass, "cloudy", temperature=13)
    hass.states.async_set("sun.sun", "above_horizon")
    entry = MockConfigEntry(
        domain=DOMAIN, data={"name": "Local", "weather_entity": "weather.local"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    runtime = hass.data[DOMAIN][entry.entry_id]
    await runtime.async_refresh()
    await hass.async_block_till_done()
    first = hass.states.get("binary_sensor.local_defrost_recommended")
    with patch(
        "custom_components.frost_risks.runtime.dt_util.utcnow",
        return_value=dt_util.utcnow() + timedelta(minutes=1),
    ):
        await runtime.async_refresh()
    await hass.async_block_till_done()
    second = hass.states.get("binary_sensor.local_defrost_recommended")
    assert second.state == first.state
    assert second.attributes == first.attributes
    assert second.last_updated == first.last_updated
    assert "observed_at" not in second.attributes["evidence"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_clear_ack_does_not_replay_unchanged_numeric_precipitation(hass, legacy_config):
    hass.states.async_set("sensor.temperature", "13", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.humidity", "87")
    hass.states.async_set("sensor.snow", "2", {"unit_of_measurement": "mm"})
    runtime, _ = await make_runtime(hass, {**legacy_config, "snow_sensor": "sensor.snow"})
    assert runtime.data.assessment.recommended is True
    await runtime.async_clear_surface()
    assert runtime.data.assessment.recommended is False
    hass.states.async_set("sensor.snow", "2", {"unit_of_measurement": "mm"})
    await runtime.async_refresh()
    assert runtime.data.assessment.recommended is False
    hass.states.async_set("sensor.snow", "3", {"unit_of_measurement": "mm"})
    await runtime.async_refresh()
    assert runtime.data.assessment.recommended is True
    await runtime.async_stop()


async def test_current_continuing_weather_snow_can_add_fresh_evidence_after_clear(hass):
    set_weather(hass, "snowy")
    runtime, _ = await make_runtime(hass, {"name": "Local", "weather_entity": "weather.local"})
    await runtime.async_clear_surface()
    set_weather(hass, "snowy")
    await runtime.async_refresh()
    assert runtime.data.assessment.recommended is True
    await runtime.async_stop()


async def test_restore_diagnoses_invalid_timestamp_and_button_only_clears_local_evidence(
    hass, legacy_config
):
    hass.states.async_set("sensor.temperature", "13", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.humidity", "87")
    entry = MockConfigEntry(domain=DOMAIN, data=legacy_config, entry_id="button-test")
    entry.add_to_hass(hass)
    probe = FrostRuntime(hass, entry)
    await probe.store.async_save(
        {"source_binding": probe._binding, "evidence": {"snow_at": "tomorrow"}}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    runtime = hass.data[DOMAIN][entry.entry_id]
    assert runtime.memory_status == "restored_partial_invalid_timestamps"
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.test_frost_surface_cleared",
        },
        blocking=True,
    )
    assert runtime.evidence.cleared_at is not None
    assert runtime.evidence.snow_at is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("language", ["en", "nl"])
async def test_new_ids_are_stable_before_sensor_platform_in_both_languages(hass, language):
    hass.config.language = language
    set_weather(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Different fallback title",
        data={"name": "Named surface", "weather_entity": "weather.local"},
    )
    entry.add_to_hass(hass)
    original_forward = hass.config_entries.async_forward_entry_setups

    async def forward_binary_and_button_first(config_entry, _platforms):
        for platform in (Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR):
            await original_forward(config_entry, [platform])

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=forward_binary_and_button_first,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.named_surface_defrost_recommended") is not None
    assert hass.states.get("button.named_surface_surface_cleared") is not None
    assert hass.states.get("binary_sensor.different_fallback_title_defrost_recommended") is None
    assert await hass.config_entries.async_unload(entry.entry_id)
