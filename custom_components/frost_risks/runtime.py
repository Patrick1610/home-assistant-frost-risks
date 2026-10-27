"""Shared local observations and persisted surface evidence for one entry."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter

from .meteorology import calculate, valid_number
from .risk import Assessment, Evidence, Observation, assess

_LOGGER = logging.getLogger(__name__)
SOURCE_KEYS = (
    "temperature_sensor",
    "humidity_sensor",
    "weather_entity",
    "rain_sensor",
    "snow_sensor",
    "surface_temperature_sensor",
)
VALID_WEATHER = {
    "clear-night",
    "cloudy",
    "exceptional",
    "fog",
    "hail",
    "lightning",
    "lightning-rainy",
    "partlycloudy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
    "sunny",
    "windy",
    "windy-variant",
}
RAIN_CONDITIONS = {"rainy", "pouring", "lightning-rainy", "snowy-rainy"}
SNOW_CONDITIONS = {"snowy", "snowy-rainy", "hail"}
MAX_WEATHER_AGE = timedelta(hours=3)


def effective_config(entry: ConfigEntry) -> dict[str, Any]:
    """Old entry.data stays valid; explicit options, including cleared fields, win."""
    return {**entry.data, **entry.options}


def _bounded(value: object, low: float, high: float) -> float | None:
    number = valid_number(value)
    return number if number is not None and low <= number <= high else None


def _temperature(value: object, unit: str | None) -> float | None:
    number = valid_number(value)
    if number is None:
        return None
    try:
        converted = TemperatureConverter.convert(number, unit or "°C", "°C")
    except (HomeAssistantError, ValueError, TypeError):
        return None
    return _bounded(converted, -80, 80)


def _reported_at(state: State):
    return getattr(state, "last_reported", state.last_updated)


@dataclass(frozen=True)
class Snapshot:
    observation: Observation
    values: dict[str, float | None]
    assessment: Assessment


class FrostRuntime(DataUpdateCoordinator[Snapshot]):
    """Recompute on events and once a minute without polling any device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"Frost Risks {entry.entry_id}")
        self.entry = entry
        self.config = effective_config(entry)
        self.evidence = Evidence()
        self.store = Store(
            hass, 1, f"frost_risks.{entry.entry_id}.surface_evidence", atomic_writes=True
        )
        self._unsubscribers = []
        self._last_saved = None
        self._last_evidence = None
        self.memory_status = "new"
        self._binding = json.dumps(
            {key: self.config.get(key) for key in SOURCE_KEYS}, sort_keys=True
        )

    async def async_start(self) -> None:
        stored = await self.store.async_load()
        if isinstance(stored, dict) and stored.get("source_binding") == self._binding:
            self.evidence = Evidence.restore(stored.get("evidence"), dt_util.utcnow())
            self.memory_status = "restored"
            original = stored.get("evidence")
            if not isinstance(original, dict) or any(
                value is not None and getattr(self.evidence, key) is None
                for key, value in (original.items() if isinstance(original, dict) else ())
                if key in Evidence.__dataclass_fields__
            ):
                self.memory_status = "restored_partial_invalid_timestamps"
        elif stored is not None:
            self.memory_status = "new_source_binding"
        sources = {str(self.config[key]) for key in SOURCE_KEYS if self.config.get(key)}
        sources.add("sun.sun")

        @callback
        def source_changed(_event) -> None:
            self.hass.async_create_task(self.async_request_refresh())

        async def tick(_now) -> None:
            await self.async_refresh()

        self._unsubscribers = [
            async_track_state_change_event(self.hass, sources, source_changed),
            async_track_time_interval(self.hass, tick, timedelta(minutes=1)),
        ]
        await self.async_refresh()

    def _state(self, key: str) -> State | None:
        entity_id = self.config.get(key)
        return self.hass.states.get(entity_id) if isinstance(entity_id, str) and entity_id else None

    def observe(self) -> Observation:
        now = dt_util.utcnow()
        missing: list[str] = []
        weather = self._state("weather_entity")
        weather_ok = (
            weather is not None
            and weather.state in VALID_WEATHER
            and timedelta(0) <= now - _reported_at(weather) <= MAX_WEATHER_AGE
        )
        attrs = weather.attributes if weather_ok else {}
        if self.config.get("weather_entity") and not weather_ok:
            missing.append("weather_entity")

        def air_value(key: str, attribute: str, *, temperature: bool = False):
            if self.config.get(key):
                state = self._state(key)
                value = state.state if state is not None else None
                unit = state.attributes.get("unit_of_measurement") if state else None
            else:
                value = attrs.get(attribute)
                unit = attrs.get("temperature_unit")
            parsed = _temperature(value, unit) if temperature else _bounded(value, 0, 100)
            if parsed is None:
                missing.append(attribute)
            return parsed

        temp = air_value("temperature_sensor", "temperature", temperature=True)
        humidity = air_value("humidity_sensor", "humidity")
        surface = None
        if self.config.get("surface_temperature_sensor"):
            state = self._state("surface_temperature_sensor")
            surface = _temperature(
                state.state if state else None,
                state.attributes.get("unit_of_measurement") if state else None,
            )
            if surface is None:
                missing.append("surface_temperature")
        clouds = _bounded(attrs.get("cloud_coverage"), 0, 100)
        wind = valid_number(attrs.get("wind_speed"))
        if wind is not None and attrs.get("wind_speed_unit") is not None:
            try:
                wind = SpeedConverter.convert(
                    wind,
                    attrs["wind_speed_unit"],
                    UnitOfSpeed.METERS_PER_SECOND,
                )
            except (HomeAssistantError, ValueError, TypeError):
                wind = None
        else:
            wind = None
        wind = _bounded(wind, 0, 100)
        sun = self.hass.states.get("sun.sun")
        night = (
            sun.state == "below_horizon"
            if sun is not None and sun.state in {"above_horizon", "below_horizon"}
            else True
            if weather_ok and weather.state == "clear-night"
            else False
            if weather_ok and weather.state == "sunny"
            else None
        )

        def precipitation(key: str, conditions: set[str]):
            fallback = (
                weather.state in conditions
                if weather_ok and weather.state not in {"exceptional", "lightning"}
                else None
            )
            stamp = _reported_at(weather) if weather_ok else None
            if self.config.get(key):
                state = self._state(key)
                number = _bounded(state.state if state else None, 0, 10000)
                if (
                    number is not None
                    and timedelta(0) <= now - _reported_at(state) <= MAX_WEATHER_AGE
                ):
                    # Re-reporting the same amount is not new precipitation after clearing.
                    return number > 0, state.last_changed
                missing.append(key)
                return (True, stamp) if fallback is True else (None, None)
            return fallback, stamp

        rain, rain_at = precipitation("rain_sensor", RAIN_CONDITIONS)
        snow, snow_at = precipitation("snow_sensor", SNOW_CONDITIONS)
        if rain is None:
            missing.append("rain_context")
        if snow is None:
            missing.append("snow_context")
        return Observation(
            temp,
            humidity,
            surface,
            clouds,
            wind,
            night,
            rain,
            snow,
            rain_at,
            snow_at,
            tuple(dict.fromkeys(missing)),
        )

    async def _async_update_data(self) -> Snapshot:
        now = dt_util.utcnow()
        observation = self.observe()
        assessment = assess(observation, self.evidence, now)
        values = calculate(observation.temperature, observation.humidity)
        values["frost_risk_level"] = assessment.level
        self._schedule_save(now)
        return Snapshot(observation, values, assessment)

    def _storage_data(self):
        return {"source_binding": self._binding, "evidence": self.evidence.serialize()}

    def _schedule_save(self, now) -> None:
        evidence = self.evidence.serialize()
        material = {key: value for key, value in evidence.items() if key != "observed_at"}
        if (
            material != self._last_evidence
            or self._last_saved is None
            or now - self._last_saved >= timedelta(minutes=30)
        ):
            self.store.async_delay_save(self._storage_data, 10)
            self._last_saved = now
            self._last_evidence = material

    async def async_clear_surface(self) -> None:
        self.evidence.clear(dt_util.utcnow())
        await self.store.async_save(self._storage_data())
        await self.async_refresh()

    async def async_stop(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        await self.async_shutdown()
        await self.store.async_save(self._storage_data())
