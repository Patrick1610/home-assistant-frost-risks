"""Pure meteorological calculations; temperatures are always degrees Celsius."""

from __future__ import annotations

import math

MIN_ICE_PRESSURE = 6.112 * math.exp(22.46 * -65 / (272.62 - 65))


def valid_number(value: object) -> float | None:
    """Reject booleans, unavailable values and non-finite input."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def valid_air(temperature: object, humidity: object) -> tuple[float, float] | None:
    """Use a bounded engineering domain, not arbitrary/singular extrapolations."""
    temp, rh = valid_number(temperature), valid_number(humidity)
    if temp is None or rh is None or not -45 <= temp <= 60 or not 0 <= rh <= 100:
        return None
    return temp, rh


def vapor_pressure(temperature: float, humidity: float) -> float:
    """Magnus water-vapour pressure in hPa; RH is expressed in percent."""
    return 6.112 * math.exp(17.67 * temperature / (temperature + 243.5)) * humidity / 100


def dew_point(temperature: float, humidity: float) -> float | None:
    """Preserve the existing Magnus-Tetens coefficients and handle dry air."""
    if humidity == 0:
        return None
    alpha = 17.27 * temperature / (237.7 + temperature) + math.log(humidity / 100)
    return 237.7 * alpha / (17.27 - alpha)


def frost_point(temperature: float, humidity: float) -> float | None:
    """Invert ice saturation using actual vapour pressure, not ice-relative RH.

    The subzero Magnus ice approximation uses a=22.46, b=272.62 degC.
    Above ice saturation at zero, report the dew point: condensation precedes
    freezing and a positive result must not be interpreted as ice at that value.
    """
    pressure = vapor_pressure(temperature, humidity)
    if pressure <= 0:
        return None
    if pressure >= 6.112:
        return dew_point(temperature, humidity)
    alpha = math.log(pressure / 6.112)
    point = 272.62 * alpha / (22.46 - alpha)
    return point if -65 <= point <= 0 else None


def legacy_freezing_point(temperature: float, humidity: float) -> float | None:
    """Keep the old entity's numerical meaning; this is NOT water's freezing point."""
    dew = dew_point(temperature, humidity)
    if dew is None:
        return None
    kelvin = temperature + 273.15
    return dew + 2671.02 / (2954.61 / kelvin + 2.193665 * math.log(kelvin) - 13.3448) - kelvin


def wet_bulb(temperature: float, humidity: float) -> float | None:
    """Stull 2011 approximation only within its published input range.

    This is evaporative-cooling context, not a measured surface temperature.
    """
    if humidity == 100:
        return temperature
    if not -20 <= temperature <= 50 or not 5 <= humidity <= 99:
        return None
    return (
        temperature * math.atan(0.151977 * math.sqrt(humidity + 8.313659))
        + math.atan(temperature + humidity)
        - math.atan(humidity - 1.676331)
        + 0.00391838 * humidity**1.5 * math.atan(0.023101 * humidity)
        - 4.686035
    )


def calculate(temperature: object, humidity: object) -> dict[str, float | None]:
    """Calculate the seven numeric outputs without rounding intermediate values."""
    keys = (
        "absolute_humidity",
        "dew_point",
        "frost_point",
        "freezing_point",
        "wet_bulb_temperature",
        "vapor_pressure",
        "humidity_ratio",
    )
    air = valid_air(temperature, humidity)
    if air is None:
        return dict.fromkeys(keys)
    temp, rh = air
    pressure = vapor_pressure(temp, rh)
    values = {
        # 216.74 converts hPa to g/m3 when RH has already been divided by 100.
        "absolute_humidity": 216.74 * pressure / (temp + 273.15),
        "dew_point": dew_point(temp, rh),
        "frost_point": frost_point(temp, rh),
        "freezing_point": legacy_freezing_point(temp, rh),
        "wet_bulb_temperature": wet_bulb(temp, rh),
        "vapor_pressure": pressure,
        "humidity_ratio": 0.622 * pressure / (1013.25 - pressure),
    }
    return {
        key: round(value, 6 if key == "humidity_ratio" else 2) if value is not None else None
        for key, value in values.items()
    }
