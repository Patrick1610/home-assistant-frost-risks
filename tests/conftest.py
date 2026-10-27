import pytest

pytest_plugins = ("pytest_homeassistant_custom_component",)


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Load the actual integration under test, never installed HA core code."""


@pytest.fixture
def legacy_config():
    return {
        "name": "Test frost",
        "temperature_sensor": "sensor.temperature",
        "humidity_sensor": "sensor.humidity",
    }
