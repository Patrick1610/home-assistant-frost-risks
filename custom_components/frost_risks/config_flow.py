"""Config flow for Frost Risks integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


class FrostRisksConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Frost Risks."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that the entities exist
            temperature_sensor = user_input[CONF_TEMPERATURE_SENSOR]
            humidity_sensor = user_input[CONF_HUMIDITY_SENSOR]

            # Check if entities exist
            if not self.hass.states.get(temperature_sensor):
                errors[CONF_TEMPERATURE_SENSOR] = "entity_not_found"
            if not self.hass.states.get(humidity_sensor):
                errors[CONF_HUMIDITY_SENSOR] = "entity_not_found"

            if not errors:
                # Create unique ID based on the sensors
                await self.async_set_unique_id(
                    f"{temperature_sensor}_{humidity_sensor}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Frost Risks"): cv.string,
                vol.Required(CONF_TEMPERATURE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required(CONF_HUMIDITY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FrostRisksOptionsFlow:
        """Get the options flow for this handler."""
        return FrostRisksOptionsFlow(config_entry)


class FrostRisksOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Frost Risks."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that the entities exist
            temperature_sensor = user_input[CONF_TEMPERATURE_SENSOR]
            humidity_sensor = user_input[CONF_HUMIDITY_SENSOR]

            # Check if entities exist
            if not self.hass.states.get(temperature_sensor):
                errors[CONF_TEMPERATURE_SENSOR] = "entity_not_found"
            if not self.hass.states.get(humidity_sensor):
                errors[CONF_HUMIDITY_SENSOR] = "entity_not_found"

            if not errors:
                # Update the config entry with new data
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=user_input,
                )
                return self.async_create_entry(title="", data={})

        # Get current values
        current_name = self.config_entry.data.get(CONF_NAME, "Frost Risks")
        current_temp = self.config_entry.data.get(CONF_TEMPERATURE_SENSOR, "")
        current_humidity = self.config_entry.data.get(CONF_HUMIDITY_SENSOR, "")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=current_name): cv.string,
                vol.Required(CONF_TEMPERATURE_SENSOR, default=current_temp): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required(CONF_HUMIDITY_SENSOR, default=current_humidity): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
