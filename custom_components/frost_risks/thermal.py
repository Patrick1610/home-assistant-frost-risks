"""Optional, uncalibrated glass heat balance; never an ice-clearance detector.

The existing weather estimate is the unheated equilibrium, not measured glass.
For each interval use the PREVIOUS boundary conditions (zero-order hold):
 C_A*dT/dt = (h_out+h_in)*(T_unheated-T) + h_in*(T_inside-T_air).
The exact exponential step preserves thermal inertia without Euler overshoot.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from .meteorology import valid_number
from .risk import _safe_time

GLASS_DENSITY = 2500.0  # kg/m3, AGC EN572 reference float glass, not Tesla-specific.
GLASS_SPECIFIC_HEAT = 720.0  # J/(kg K), same AGC reference.
MAX_HISTORY_GAP = timedelta(minutes=15)
THERMAL_DEFAULTS = {
    "glass_thickness_mm": 4.5,
    "inside_heat_transfer": 5.0,
    "outside_heat_transfer": 15.0,
}
THERMAL_LIMITS = {
    "glass_thickness_mm": (2.0, 20.0),
    "inside_heat_transfer": (0.5, 50.0),
    "outside_heat_transfer": (1.0, 100.0),
}


def parameters(config: dict) -> dict[str, float]:
    """Reject corrupt parameters rather than producing an unstable warm estimate."""
    values = {}
    for key, default in THERMAL_DEFAULTS.items():
        value = valid_number(config.get(key, default))
        low, high = THERMAL_LIMITS[key]
        if value is None or not low <= value <= high:
            raise ValueError(f"invalid thermal parameter: {key}")
        values[key] = value
    return values


@dataclass
class GlassState:
    temperature: float | None = None
    updated_at: datetime | None = None
    equilibrium: float | None = None
    time_constant: float | None = None
    _resumed: bool = field(default=False, repr=False)

    @classmethod
    def restore(cls, data: object, now: datetime) -> GlassState:
        if not isinstance(data, dict):
            return cls()
        temperature = valid_number(data.get("temperature"))
        equilibrium = valid_number(data.get("equilibrium"))
        tau = valid_number(data.get("time_constant"))
        at = _safe_time(data.get("updated_at"), now)
        if (
            temperature is None
            or equilibrium is None
            or tau is None
            or not -100 <= temperature <= 100
            or not -100 <= equilibrium <= 100
            or not 1 <= tau <= 100000
            or at is None
        ):
            return cls()
        return cls(temperature, at, equilibrium, tau, _resumed=True)

    def serialize(self):
        return {
            "temperature": self.temperature,
            "equilibrium": self.equilibrium,
            "time_constant": self.time_constant,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def reset(self) -> None:
        self.temperature = self.equilibrium = self.time_constant = self.updated_at = None
        self._resumed = False

    def advance(
        self,
        now: datetime,
        *,
        unheated: float,
        inside: float,
        outside: float,
        config: dict,
    ) -> dict:
        values = parameters(config)
        if not all(math.isfinite(v) and -100 <= v <= 100 for v in (unheated, inside, outside)):
            raise ValueError("invalid thermal boundary")
        hi, ho = values["inside_heat_transfer"], values["outside_heat_transfer"]
        capacity = GLASS_DENSITY * GLASS_SPECIFIC_HEAT * values["glass_thickness_mm"] / 1000
        equilibrium = unheated + hi / (hi + ho) * (inside - outside)
        tau = capacity / (hi + ho)
        gap = now - self.updated_at if self.updated_at is not None else None
        status = "tracking"
        if self.temperature is None or gap is None:
            self.temperature = unheated
            status = "initialized_unheated"
        elif gap < timedelta(0) or gap > MAX_HISTORY_GAP:
            self.temperature = unheated
            status = "history_gap_unheated"
        else:
            # New sensor readings must not warm the glass retroactively.
            interval_equilibrium = self.equilibrium
            if self._resumed:
                # No readings were observed while unloaded. Do not replay old
                # cabin warmth if the boundary is now colder.
                interval_equilibrium = min(interval_equilibrium, equilibrium)
                status = "restored_gap_conservative_boundary"
            self.temperature = interval_equilibrium + (
                self.temperature - interval_equilibrium
            ) * math.exp(-gap.total_seconds() / self.time_constant)
        self._resumed = False
        self.updated_at = now
        self.equilibrium, self.time_constant = equilibrium, tau
        return {
            "status": status,
            "calibration": "uncalibrated_reference_glass",
            "surface_temperature": round(self.temperature, 3),
            "unheated_surface_temperature": unheated,
            "inside_temperature": inside,
            "outside_temperature": outside,
            "equilibrium_temperature": round(equilibrium, 3),
            "time_constant_seconds": round(tau, 3),
            "capacity_j_m2k": capacity,
            **values,
        }


@dataclass
class HeatingHistory:
    """Observe a heat source, independently of any claim that ice has melted."""

    active: bool | None = None
    started_at: datetime | None = None
    observed_at: datetime | None = None
    last_ended_at: datetime | None = None
    last_duration_seconds: float | None = None

    @classmethod
    def restore(cls, data: object, now: datetime) -> HeatingHistory:
        if not isinstance(data, dict):
            return cls()
        duration = valid_number(data.get("last_duration_seconds"))
        return cls(
            data.get("active") if isinstance(data.get("active"), bool) else None,
            _safe_time(data.get("started_at"), now),
            _safe_time(data.get("observed_at"), now),
            _safe_time(data.get("last_ended_at"), now),
            duration if duration is not None and duration >= 0 else None,
        )

    def observe(self, active: bool | None, now: datetime) -> bool:
        """Return True only for an observed on-to-off edge, never unknown-to-off."""
        ended = False
        gap = now - self.observed_at if self.observed_at else None
        continuity = gap is not None and timedelta(0) <= gap <= MAX_HISTORY_GAP
        if active is None:
            self.active = self.started_at = self.observed_at = None
            return False
        if active and self.active is not True:
            self.started_at = now
        elif active and not continuity:
            self.started_at = now
        elif not active and self.active is True and continuity:
            self.last_ended_at = now
            self.last_duration_seconds = (
                (now - self.started_at).total_seconds() if self.started_at is not None else None
            )
            self.started_at = None
            ended = True
        if not active:
            self.started_at = None
        self.active, self.observed_at = active, now
        return ended

    def serialize(self):
        return {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in asdict(self).items()
        }

    def diagnostics(self):
        return {
            "active": self.active,
            "last_heating_ended_at": self.last_ended_at.isoformat() if self.last_ended_at else None,
            "last_heating_duration_seconds": self.last_duration_seconds,
            "meaning": "observed_heating_end_not_confirmed_surface_clearance",
        }
