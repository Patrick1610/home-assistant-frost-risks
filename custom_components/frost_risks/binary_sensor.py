"""One advisory on/off output; it does not activate defrost or any other device."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    async_add_entities([DefrostRecommended(hass.data[DOMAIN][entry.entry_id])])


class DefrostRecommended(CoordinatorEntity, BinarySensorEntity):
    _attr_icon = "mdi:car-defrost-front"
    _attr_has_entity_name = True
    _attr_translation_key = "defrost_recommended"
    _unrecorded_attributes = frozenset({"evidence", "memory_status"})

    def __init__(self, runtime):
        super().__init__(runtime)
        self._attr_unique_id = f"{runtime.entry.entry_id}_defrost_recommended"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)}, name=runtime.config["name"]
        )

    @property
    def is_on(self):
        return self.coordinator.data.assessment.recommended

    @property
    def suggested_object_id(self):
        """Keep the new automation-facing ID stable across UI languages."""
        return "Defrost recommended"

    @property
    def extra_state_attributes(self):
        runtime = self.coordinator
        assessment = runtime.data.assessment
        return {
            "reason": assessment.reason,
            "quality": assessment.quality,
            "missing_context": assessment.missing,
            "surface_temperature_used": assessment.surface_temperature,
            "surface_basis": assessment.surface_basis,
            "evidence": {
                key: value
                for key, value in runtime.evidence.serialize().items()
                if key != "observed_at"
            },
            "advisory_only": True,
            "calculation_version": "2.1",
            "memory_status": runtime.memory_status,
        }
