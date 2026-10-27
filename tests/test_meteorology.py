import math

import pytest

from custom_components.frost_risks.meteorology import calculate, frost_point, valid_air


@pytest.mark.parametrize(("temperature", "humidity", "expected"), [(13, 87, 9.86), (14, 87, 10.49)])
def test_absolute_humidity_uses_grams_not_hundredths(temperature, humidity, expected):
    values = calculate(temperature, humidity)
    assert values["absolute_humidity"] == expected
    # Independent ideal-gas check: rho=p/(Rv*T), converting hPa->Pa and kg->g.
    pressure_pa = values["vapor_pressure"] * 100
    density = pressure_pa / (461.5 * (temperature + 273.15)) * 1000
    assert values["absolute_humidity"] == pytest.approx(density, abs=0.01)


def test_frost_point_inverts_actual_vapour_pressure_over_ice():
    pressure = 6.112 * math.exp(22.46 * -10 / (272.62 - 10))
    air_saturation = 6.112 * math.exp(17.67 * -5 / (-5 + 243.5))
    rh = 100 * pressure / air_saturation
    assert frost_point(-5, rh) == pytest.approx(-10, abs=1e-9)


def test_legacy_index_retains_its_existing_values_but_is_not_used_as_ice_temperature():
    assert calculate(13, 87)["freezing_point"] == 9.22
    assert calculate(14, 87)["freezing_point"] == 10.06


@pytest.mark.parametrize("humidity", [0, 100])
def test_humidity_endpoints_do_not_raise(humidity):
    values = calculate(-5, humidity)
    assert values["absolute_humidity"] >= 0
    if humidity == 0:
        assert values["dew_point"] is None
        assert values["frost_point"] is None
        assert values["vapor_pressure"] == 0
    else:
        assert values["wet_bulb_temperature"] == -5


@pytest.mark.parametrize(
    ("temperature", "humidity"),
    [
        (None, 50),
        (True, 50),
        ("unavailable", 50),
        (float("nan"), 50),
        (float("inf"), 50),
        (-273.15, 50),
        (-237.7, 50),
        (-243.5, 50),
        (61, 50),
        (20, -1),
        (20, 101),
        (20, float("nan")),
    ],
)
def test_invalid_or_singular_input_is_unavailable(temperature, humidity):
    assert valid_air(temperature, humidity) is None
    assert all(value is None for value in calculate(temperature, humidity).values())


def test_stull_values_and_domain_are_explicit():
    assert calculate(20, 50)["wet_bulb_temperature"] == pytest.approx(13.70, abs=0.01)
    assert calculate(-30, 50)["wet_bulb_temperature"] is None
    assert calculate(10, 1)["wet_bulb_temperature"] is None
