"""An explicit acknowledgement of surface clearing, with no device control."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    async_add_entities([ClearSurfaceEvidence(hass.data[DOMAIN][entry.entry_id])])


class ClearSurfaceEvidence(ButtonEntity):
    _attr_icon = "mdi:snowflake-off"
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "surface_cleared"

    def __init__(self, runtime):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_surface_cleared"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)}, name=runtime.config["name"]
        )

    @property
    def suggested_object_id(self):
        return "Surface cleared"

    async def async_press(self) -> None:
        await self.runtime.async_clear_surface()
