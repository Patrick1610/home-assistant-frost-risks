"""Advisory surface-ice screening with bounded, restartable evidence memory.

No output is a measurement of ice or a probability. Thresholds are deliberately
explicit heuristics; caller-supplied cloud/wind/surface observations improve them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .meteorology import MIN_ICE_PRESSURE, frost_point, valid_air, valid_number, vapor_pressure

WET_MEMORY = timedelta(hours=6)
ICE_MEMORY = timedelta(hours=24)
HISTORY_GAP = timedelta(minutes=15)


@dataclass(frozen=True)
class Observation:
    temperature: float | None
    humidity: float | None
    surface_temperature: float | None = None
    cloud_coverage: float | None = None
    wind_m_s: float | None = None
    night: bool | None = None
    rain: bool | None = None
    snow: bool | None = None
    rain_reported_at: datetime | None = None
    snow_reported_at: datetime | None = None
    missing: tuple[str, ...] = ()


def _safe_time(value: object, now: datetime) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed > now:
        return None
    return parsed.astimezone(UTC)


@dataclass
class Evidence:
    wet_at: datetime | None = None
    snow_at: datetime | None = None
    ice_at: datetime | None = None
    cleared_at: datetime | None = None
    observed_at: datetime | None = None

    @classmethod
    def restore(cls, data: object, now: datetime) -> Evidence:
        if not isinstance(data, dict):
            return cls()
        return cls(**{key: _safe_time(data.get(key), now) for key in cls.__dataclass_fields__})

    def serialize(self) -> dict[str, str | None]:
        return {
            key: value.isoformat() if value else None
            for key in self.__dataclass_fields__
            for value in (getattr(self, key),)
        }

    def clear(self, now: datetime) -> None:
        """Acknowledge a cleared surface; no actuator is called."""
        self.wet_at = self.snow_at = self.ice_at = None
        self.cleared_at = now

    def recent(self, field: str, now: datetime, duration: timedelta) -> bool:
        value = getattr(self, field)
        return value is not None and timedelta(0) <= now - value <= duration


@dataclass(frozen=True)
class Assessment:
    recommended: bool | None
    level: int | None
    reason: str
    quality: str
    surface_temperature: float | None
    surface_basis: str
    missing: tuple[str, ...]


def _new_report(reported_at: datetime | None, evidence: Evidence, now: datetime) -> bool:
    return (
        reported_at is not None
        and reported_at <= now
        and (evidence.cleared_at is None or reported_at > evidence.cleared_at)
    )


def assess(observation: Observation, evidence: Evidence, now: datetime) -> Assessment:
    """Update evidence and screen for frost, frozen wetness, and retained snow."""
    gap = evidence.observed_at is None or now - evidence.observed_at > HISTORY_GAP
    if observation.rain is True and _new_report(observation.rain_reported_at, evidence, now):
        evidence.wet_at = observation.rain_reported_at
    if observation.snow is True and _new_report(observation.snow_reported_at, evidence, now):
        evidence.snow_at = observation.snow_reported_at
        evidence.wet_at = observation.snow_reported_at
    evidence.observed_at = now

    missing = list(observation.missing)
    if gap:
        missing.append("history_gap")
    air = valid_air(observation.temperature, observation.humidity)
    surface = valid_number(observation.surface_temperature)
    if surface is not None and not -80 <= surface <= 80:
        surface = None
    basis = "measured" if surface is not None else "unmeasured"
    context_complete = (
        observation.cloud_coverage is not None
        and observation.wind_m_s is not None
        and observation.night is not None
    )
    if surface is None and air is not None:
        temp, _ = air
        if context_complete:
            if observation.night is False:
                allowance = 0.0
            elif observation.cloud_coverage <= 30 and observation.wind_m_s <= 2:
                allowance = 3.0
            elif observation.cloud_coverage >= 80 or observation.wind_m_s >= 5:
                allowance = 0.5
            else:
                allowance = 1.5
            basis = "weather_heuristic"
        else:
            # Explicit, conservative cold-air screening; never claim clear/calm weather.
            allowance = 2.0
            basis = "limited_air_screening"
            missing.append("surface_or_complete_radiation_context")
        surface = temp - allowance

    quality = "good" if not missing and not gap and basis != "limited_air_screening" else "limited"
    if evidence.recent("snow_at", now, ICE_MEMORY):
        return Assessment(True, 4, "recent_snow", quality, surface, basis, tuple(missing))
    if evidence.recent("ice_at", now, ICE_MEMORY):
        return Assessment(True, 4, "residual_ice", quality, surface, basis, tuple(missing))
    if surface is None:
        return Assessment(None, None, "insufficient_data", "unknown", None, basis, tuple(missing))
    if surface <= 0 and evidence.recent("wet_at", now, WET_MEMORY):
        evidence.ice_at = now
        return Assessment(True, 4, "frozen_wet_surface", quality, surface, basis, tuple(missing))
    if air is None:
        return Assessment(
            None, None, "insufficient_data", "unknown", surface, basis, tuple(missing)
        )
    frost = frost_point(*air)
    if frost is None and air[1] > 0:
        # Ice saturation below the -65C inverse bound is a known dry-air case,
        # not missing humidity. The surface itself must remain above that bound.
        if surface >= -65 and vapor_pressure(*air) < MIN_ICE_PRESSURE:
            return Assessment(
                False, 1, "dry_no_ice_evidence", quality, surface, basis, tuple(missing)
            )
        return Assessment(
            None,
            None,
            "insufficient_data",
            "unknown",
            surface,
            basis,
            tuple([*missing, "frost_point_outside_formula_domain"]),
        )
    # Saturation over ice below zero, or existing condensation which can freeze.
    deposition = surface <= 0 and frost is not None and surface <= frost
    cleared_after_report = (
        evidence.cleared_at is not None and now - evidence.cleared_at < timedelta(minutes=5)
    )
    if deposition and not cleared_after_report:
        # Atmospheric formation can recur; acknowledgement is a bounded five-minute hold.
        return Assessment(
            True, 3, "surface_frost_possible", quality, surface, basis, tuple(missing)
        )
    if cleared_after_report:
        return Assessment(False, 0, "surface_cleared", quality, surface, basis, tuple(missing))
    if surface > 0:
        reason = "surface_above_freezing"
    elif observation.humidity == 0 or frost is not None and surface > frost:
        reason = "dry_no_ice_evidence"
    else:
        reason = "no_ice_evidence"
    return Assessment(
        False, 1 if surface <= 2 else 0, reason, quality, surface, basis, tuple(missing)
    )
