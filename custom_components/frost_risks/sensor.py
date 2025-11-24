"""Sensor platform for Frost Risks integration."""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_NAME,
    SENSOR_TYPES,
    SENSOR_TYPE_ABSOLUTE_HUMIDITY,
    SENSOR_TYPE_DEW_POINT,
    SENSOR_TYPE_FROST_POINT,
    SENSOR_TYPE_FREEZING_POINT,
    SENSOR_TYPE_WET_BULB,
    SENSOR_TYPE_VAPOR_PRESSURE,
    SENSOR_TYPE_HUMIDITY_RATIO,
    SENSOR_TYPE_FROST_RISK,
    FROST_RISK_LEVELS,
)

_LOGGER = logging.getLogger(__name__)

ATTR_HUMIDITY = "humidity"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Frost Risks sensors from a config entry."""
    config = hass.data[DOMAIN][entry.entry_id]
    
    name = config[CONF_NAME]
    temperature_entity = config[CONF_TEMPERATURE_SENSOR]
    humidity_entity = config[CONF_HUMIDITY_SENSOR]

    # Create all sensor types
    sensors = []
    for sensor_type in SENSOR_TYPES:
        sensors.append(
            FrostRisksSensor(
                hass,
                entry.entry_id,
                name,
                temperature_entity,
                humidity_entity,
                sensor_type,
            )
        )

    async_add_entities(sensors, True)


class FrostRisksSensor(SensorEntity):
    """Representation of a Frost Risks Sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        temperature_entity: str,
        humidity_entity: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._base_name = name
        self._temperature_entity = temperature_entity
        self._humidity_entity = humidity_entity
        self._sensor_type = sensor_type
        self._temperature: float | None = None
        self._humidity: float | None = None
        
        sensor_info = SENSOR_TYPES[sensor_type]
        
        # Set entity attributes
        self._attr_name = f"{name} {sensor_info['name_en']}"
        self._attr_unique_id = f"{entry_id}_{sensor_type}"
        self._attr_native_unit_of_measurement = sensor_info["unit"]
        self._attr_device_class = sensor_info["device_class"]
        self._attr_state_class = sensor_info["state_class"]
        self._attr_icon = sensor_info["icon"]
        
        # Set up device info to group all sensors under one device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=name,
            manufacturer="Frost Risks",
            model="Frost Risk Monitor",
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        # Track state changes of temperature and humidity sensors
        @callback
        def async_sensor_state_listener(event):
            """Handle sensor state changes."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._temperature_entity, self._humidity_entity],
                async_sensor_state_listener,
            )
        )

        # Get initial states
        await self.async_update()

    async def async_update(self) -> None:
        """Update the sensor state."""
        # Get current temperature
        temp_state = self.hass.states.get(self._temperature_entity)
        if temp_state and temp_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._temperature = float(temp_state.state)
            except (ValueError, TypeError):
                _LOGGER.error(
                    "Unable to parse temperature from %s: %s",
                    self._temperature_entity,
                    temp_state.state,
                )
                self._temperature = None
        else:
            self._temperature = None

        # Get current humidity
        humidity_state = self.hass.states.get(self._humidity_entity)
        if humidity_state and humidity_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._humidity = float(humidity_state.state)
            except (ValueError, TypeError):
                _LOGGER.error(
                    "Unable to parse humidity from %s: %s",
                    self._humidity_entity,
                    humidity_state.state,
                )
                self._humidity = None
        else:
            self._humidity = None

        # Calculate sensor value
        if self._temperature is not None and self._humidity is not None:
            self._attr_native_value = self._calculate_value()
        else:
            self._attr_native_value = None

    def _calculate_value(self) -> float | None:
        """Calculate the sensor value based on type."""
        if self._temperature is None or self._humidity is None:
            return None

        if self._sensor_type == SENSOR_TYPE_ABSOLUTE_HUMIDITY:
            return self._compute_absolute_humidity(self._temperature, self._humidity)
        elif self._sensor_type == SENSOR_TYPE_DEW_POINT:
            return self._compute_dew_point(self._temperature, self._humidity)
        elif self._sensor_type == SENSOR_TYPE_FROST_POINT:
            return self._compute_frost_point(self._temperature, self._humidity)
        elif self._sensor_type == SENSOR_TYPE_FREEZING_POINT:
            return self._compute_freezing_point(self._temperature, self._humidity)
        elif self._sensor_type == SENSOR_TYPE_WET_BULB:
            return self._compute_wet_bulb_temperature(self._temperature, self._humidity)
        elif self._sensor_type == SENSOR_TYPE_VAPOR_PRESSURE:
            return self._compute_vapor_pressure(self._temperature, self._humidity)
        elif self._sensor_type == SENSOR_TYPE_HUMIDITY_RATIO:
            return self._compute_humidity_ratio(self._temperature, self._humidity)
        elif self._sensor_type == SENSOR_TYPE_FROST_RISK:
            return float(self._compute_frost_risk_level(self._temperature, self._humidity))

        return None

    @staticmethod
    def _compute_absolute_humidity(temperature: float, humidity: float) -> float:
        """
        Calculate absolute humidity in g/m³.
        
        Uses the Magnus formula for saturation vapor pressure.
        Formula: AH = (6.112 × e^((17.67×T)/(T+243.5)) × RH × 2.1674) / (273.15 + T)
        
        Reference: https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/
        """
        abs_temp = temperature + 273.15
        abs_humidity = 6.112 * math.exp((17.67 * temperature) / (243.5 + temperature))
        abs_humidity *= humidity / 100.0
        abs_humidity *= 2.1674
        abs_humidity /= abs_temp
        return round(abs_humidity, 2)

    @staticmethod
    def _compute_dew_point(temperature: float, humidity: float) -> float:
        """
        Calculate dew point temperature in °C using Magnus-Tetens formula.
        
        Formula: Td = (b × α(T,RH)) / (a - α(T,RH))
        where α(T,RH) = (a×T)/(b+T) + ln(RH/100)
        Constants: a = 17.27, b = 237.7°C
        
        Reference: Magnus-Tetens approximation
        """
        a = 17.27
        b = 237.7
        
        alpha = (a * temperature) / (b + temperature) + math.log(humidity / 100.0)
        dew_point = (b * alpha) / (a - alpha)
        
        return round(dew_point, 2)

    @staticmethod
    def _compute_frost_point(temperature: float, humidity: float) -> float:
        """
        Calculate frost point temperature in °C.
        
        The frost point is the temperature at which frost forms (below 0°C).
        Uses modified Magnus formula for ice saturation.
        
        Formula for T < 0°C: Tf = (b × α(T,RH)) / (a - α(T,RH))
        where α(T,RH) = (a×T)/(b+T) + ln(RH/100)
        Constants for ice: a = 21.875, b = 265.5°C
        """
        dew_point = FrostRisksSensor._compute_dew_point(temperature, humidity)
        
        if dew_point < 0:
            # Use ice saturation formula
            a = 21.875
            b = 265.5
            alpha = (a * temperature) / (b + temperature) + math.log(humidity / 100.0)
            frost_point = (b * alpha) / (a - alpha)
            return round(frost_point, 2)
        
        return round(dew_point, 2)

    @staticmethod
    def _compute_freezing_point(temperature: float, humidity: float) -> float:
        """
        Calculate freezing point depression in °C.
        
        This calculates the temperature at which water will freeze given the
        current atmospheric conditions including humidity effects.
        
        Reference: https://pon.fr/dzvents-alerte-givre-et-calcul-humidite-absolue/
        """
        dew_point = FrostRisksSensor._compute_dew_point(temperature, humidity)
        T = temperature + 273.15
        Td = dew_point + 273.15
        
        freezing_point = (
            Td + (2671.02 / ((2954.61 / T) + 2.193665 * math.log(T) - 13.3448)) - T
        ) - 273.15
        
        return round(freezing_point, 2)

    @staticmethod
    def _compute_wet_bulb_temperature(temperature: float, humidity: float) -> float:
        """
        Calculate wet-bulb temperature in °C.
        
        Uses Stull's formula (2011) which is accurate to ±1°C for a wide range of conditions.
        
        Formula: Tw = T × atan(0.151977 × √(RH + 8.313659)) + atan(T + RH) - atan(RH - 1.676331) 
                     + 0.00391838 × RH^(3/2) × atan(0.023101 × RH) - 4.686035
        
        Reference: Stull, R., 2011: Wet-Bulb Temperature from Relative Humidity and Air Temperature.
        Journal of Applied Meteorology and Climatology, 50, 2267-2269.
        """
        T = temperature
        RH = max(0.0, min(100.0, humidity))  # Clamp humidity to valid range [0, 100]
        
        # For very low humidity, use a simplified approach
        if RH < 5.0:
            # At very low humidity, wet-bulb is close to dry-bulb minus a small correction
            return round(T - 0.5, 2)
        
        wet_bulb = (
            T * math.atan(0.151977 * math.sqrt(RH + 8.313659))
            + math.atan(T + RH)
            - math.atan(RH - 1.676331)
            + 0.00391838 * math.pow(RH, 1.5) * math.atan(0.023101 * RH)
            - 4.686035
        )
        
        return round(wet_bulb, 2)

    @staticmethod
    def _compute_vapor_pressure(temperature: float, humidity: float) -> float:
        """
        Calculate vapor pressure in hPa.
        
        Uses Magnus formula: e = es × (RH/100)
        where es = 6.112 × exp((17.67×T)/(T+243.5))
        
        Reference: Magnus formula for saturation vapor pressure
        """
        # Saturation vapor pressure
        es = 6.112 * math.exp((17.67 * temperature) / (temperature + 243.5))
        # Actual vapor pressure
        e = es * (humidity / 100.0)
        
        return round(e, 2)

    @staticmethod
    def _compute_humidity_ratio(temperature: float, humidity: float) -> float:
        """
        Calculate humidity ratio (mixing ratio) in kg/kg.
        
        Formula: W = 0.622 × (e / (P - e))
        where e is vapor pressure and P is atmospheric pressure (assumed 1013.25 hPa)
        
        Reference: ASHRAE Fundamentals
        """
        # Get vapor pressure in hPa
        e = FrostRisksSensor._compute_vapor_pressure(temperature, humidity)
        # Atmospheric pressure in hPa (standard sea level)
        P = 1013.25
        
        # Humidity ratio
        W = 0.622 * (e / (P - e))
        
        return round(W, 6)

    @staticmethod
    def _compute_frost_risk_level(temperature: float, humidity: float) -> int:
        """
        Calculate frost risk level (0-5).
        
        Risk assessment based on multiple factors:
        - Dew point
        - Wet-bulb temperature
        - Freezing point
        - Absolute humidity
        
        Levels:
        0 = No risk
        1 = Very low risk
        2 = Low risk
        3 = Moderate risk
        4 = High risk
        5 = Very high risk (frost highly likely)
        """
        dew_point = FrostRisksSensor._compute_dew_point(temperature, humidity)
        wet_bulb = FrostRisksSensor._compute_wet_bulb_temperature(temperature, humidity)
        freezing_point = FrostRisksSensor._compute_freezing_point(temperature, humidity)
        abs_humidity = FrostRisksSensor._compute_absolute_humidity(temperature, humidity)
        
        # Risk level calculation based on multiple thresholds
        risk_level = 0
        
        # Temperature-based risk
        if temperature <= -5:
            risk_level = max(risk_level, 5)
        elif temperature <= -2:
            risk_level = max(risk_level, 4)
        elif temperature <= 0:
            risk_level = max(risk_level, 3)
        elif temperature <= 2:
            risk_level = max(risk_level, 2)
        elif temperature <= 4:
            risk_level = max(risk_level, 1)
        
        # Dew point-based risk (frost likely if dew point approaches 0°C)
        if dew_point <= -5:
            risk_level = max(risk_level, 4)
        elif dew_point <= -2:
            risk_level = max(risk_level, 3)
        elif dew_point <= 0:
            risk_level = max(risk_level, 2)
        elif dew_point <= 2:
            risk_level = max(risk_level, 1)
        
        # Wet-bulb temperature risk
        if wet_bulb <= 0 and temperature <= 2:
            risk_level = max(risk_level, 4)
        elif wet_bulb <= 1 and temperature <= 3:
            risk_level = max(risk_level, 3)
        
        # Freezing point risk
        if freezing_point <= -2:
            risk_level = max(risk_level, 4)
        elif freezing_point <= 0:
            risk_level = max(risk_level, 3)
        elif freezing_point <= 1:
            risk_level = max(risk_level, 2)
        
        # Absolute humidity consideration (low humidity increases frost risk)
        if abs_humidity < 2.8 and temperature <= 1 and freezing_point <= 0:
            risk_level = max(risk_level, 1)
        elif abs_humidity >= 2.8 and temperature <= 4 and freezing_point <= 0.5:
            risk_level = max(risk_level, 2)
        elif abs_humidity >= 2.8 and temperature <= 1 and freezing_point <= 0:
            risk_level = max(risk_level, 3)
        
        # Ensure risk level is in valid range
        return max(0, min(5, risk_level))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            ATTR_TEMPERATURE: self._temperature,
            ATTR_HUMIDITY: self._humidity,
        }
        
        # Add frost risk description for frost risk sensor
        if self._sensor_type == SENSOR_TYPE_FROST_RISK and self._attr_native_value is not None:
            level = int(self._attr_native_value)
            if level in FROST_RISK_LEVELS:
                attrs["description_en"] = FROST_RISK_LEVELS[level]["en"]
                attrs["description_nl"] = FROST_RISK_LEVELS[level]["nl"]
        
        return attrs


