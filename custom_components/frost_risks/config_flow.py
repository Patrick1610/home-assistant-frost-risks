"""Weather-first setup with backwards-compatible individual sensor overrides."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry, selector

from .const import DOMAIN
from .runtime import SOURCE_KEYS, effective_config


def _schema(values):
    fields = {vol.Required("name", default=values.get("name", "Frost Risks")): str}
    for key in SOURCE_KEYS:
        config = {"domain": "weather" if key == "weather_entity" else "sensor"}
        if key in {"temperature_sensor", "surface_temperature_sensor"}:
            config["device_class"] = "temperature"
        elif key == "humidity_sensor":
            config["device_class"] = "humidity"
        fields[vol.Optional(key, description={"suggested_value": values.get(key)})] = (
            selector.EntitySelector(selector.EntitySelectorConfig(**config))
        )
    return vol.Schema(fields)


def _validate(hass, values):
    errors = {}
    if not values.get("weather_entity") and not (
        values.get("temperature_sensor") and values.get("humidity_sensor")
    ):
        errors["base"] = "sources_required"
    if not str(values.get("name", "")).strip():
        errors["name"] = "name_required"
    registry = entity_registry.async_get(hass)
    for key in SOURCE_KEYS:
        entity_id = values.get(key)
        if (
            entity_id
            and hass.states.get(entity_id) is None
            and registry.async_get(entity_id) is None
        ):
            errors[key] = "entity_not_found"
    return errors


class FrostRisksConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                sources = "_".join(
                    user_input[key]
                    for key in ("temperature_sensor", "humidity_sensor", "weather_entity")
                    if user_input.get(key)
                )
                # Retain the historical identity for classic temperature/humidity setup.
                if not user_input.get("weather_entity"):
                    sources = f"{user_input['temperature_sensor']}_{user_input['humidity_sensor']}"
                await self.async_set_unique_id(sources)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        # HA owns the read-only config_entry property; do not assign it in __init__.
        return FrostRisksOptionsFlow()


class FrostRisksOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                values = {**self.config_entry.options, **user_input}
                # Explicitly clear removed optional sources instead of falling back to old data.
                values.update({key: user_input.get(key) for key in SOURCE_KEYS})
                self.hass.config_entries.async_update_entry(self.config_entry, title=values["name"])
                return self.async_create_entry(title="", data=values)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or effective_config(self.config_entry)),
            errors=errors,
        )
