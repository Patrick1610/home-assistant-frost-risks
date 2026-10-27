"""Existing meteorological entity IDs, backed by a shared local runtime."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FROST_RISK_LEVELS, SENSOR_TYPES
from .runtime import FrostRuntime


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(FrostRisksSensor(runtime, key) for key in SENSOR_TYPES)


class FrostRisksSensor(CoordinatorEntity[FrostRuntime], SensorEntity):
    """Preserve all eight pre-existing unique IDs and their device binding."""

    def __init__(self, runtime: FrostRuntime, sensor_type: str) -> None:
        super().__init__(runtime)
        self.sensor_type = sensor_type
        info = SENSOR_TYPES[sensor_type]
        self._attr_name = f"{runtime.config['name']} {info['name_en']}"
        self._attr_unique_id = f"{runtime.entry.entry_id}_{sensor_type}"
        self._attr_native_unit_of_measurement = info["unit"]
        self._attr_device_class = info["device_class"]
        self._attr_state_class = info["state_class"]
        self._attr_icon = info["icon"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            name=runtime.config["name"],
            manufacturer="Frost Risks",
            model="Frost Risk Monitor",
        )

    @property
    def native_value(self):
        return self.coordinator.data.values.get(self.sensor_type)

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self):
        snapshot = self.coordinator.data
        attributes = {
            "temperature": snapshot.observation.temperature,
            "humidity": snapshot.observation.humidity,
            "calculation_version": "2.1",
        }
        if self.sensor_type == "freezing_point":
            attributes.update(
                legacy=True,
                deprecated=True,
                meaning="Legacy humidity-derived index; not water's freezing point",
            )
        if self.sensor_type == "frost_risk_level":
            descriptions = FROST_RISK_LEVELS.get(snapshot.assessment.level, {})
            attributes.update(
                description_en=descriptions.get("en"),
                description_nl=descriptions.get("nl"),
                reason=snapshot.assessment.reason,
                quality=snapshot.assessment.quality,
                missing_context=snapshot.assessment.missing,
                advisory_only=True,
            )
        return attributes
