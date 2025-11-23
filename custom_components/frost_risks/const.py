"""Constants for the Frost Risks integration."""

DOMAIN = "frost_risks"

# Configuration constants
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_NAME = "name"

# Sensor types
SENSOR_TYPE_ABSOLUTE_HUMIDITY = "absolute_humidity"
SENSOR_TYPE_DEW_POINT = "dew_point"
SENSOR_TYPE_FROST_POINT = "frost_point"
SENSOR_TYPE_FREEZING_POINT = "freezing_point"
SENSOR_TYPE_WET_BULB = "wet_bulb_temperature"
SENSOR_TYPE_VAPOR_PRESSURE = "vapor_pressure"
SENSOR_TYPE_HUMIDITY_RATIO = "humidity_ratio"
SENSOR_TYPE_FROST_RISK = "frost_risk_level"

# Sensor definitions: [name_en, name_nl, unit, device_class, state_class, icon]
SENSOR_TYPES = {
    SENSOR_TYPE_ABSOLUTE_HUMIDITY: {
        "name_en": "Absolute Humidity",
        "name_nl": "Absolute Vochtigheid",
        "unit": "g/m³",
        "device_class": None,
        "state_class": "measurement",
        "icon": "mdi:water",
    },
    SENSOR_TYPE_DEW_POINT: {
        "name_en": "Dew Point",
        "name_nl": "Dauwpunt",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:thermometer-water",
    },
    SENSOR_TYPE_FROST_POINT: {
        "name_en": "Frost Point",
        "name_nl": "Rijppunt",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:snowflake-thermometer",
    },
    SENSOR_TYPE_FREEZING_POINT: {
        "name_en": "Freezing Point",
        "name_nl": "Vriespunt",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:snowflake-alert",
    },
    SENSOR_TYPE_WET_BULB: {
        "name_en": "Wet-Bulb Temperature",
        "name_nl": "Natte-Bol Temperatuur",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    SENSOR_TYPE_VAPOR_PRESSURE: {
        "name_en": "Vapor Pressure",
        "name_nl": "Dampdruk",
        "unit": "hPa",
        "device_class": "atmospheric_pressure",
        "state_class": "measurement",
        "icon": "mdi:gauge",
    },
    SENSOR_TYPE_HUMIDITY_RATIO: {
        "name_en": "Humidity Ratio",
        "name_nl": "Vochtverhouding",
        "unit": "kg/kg",
        "device_class": None,
        "state_class": "measurement",
        "icon": "mdi:water-percent",
    },
    SENSOR_TYPE_FROST_RISK: {
        "name_en": "Frost Risk Level",
        "name_nl": "Vorst Risico Niveau",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:snowflake-alert",
    },
}

# Frost risk level descriptions
FROST_RISK_LEVELS = {
    0: {"en": "No Risk", "nl": "Geen Risico"},
    1: {"en": "Very Low", "nl": "Zeer Laag"},
    2: {"en": "Low", "nl": "Laag"},
    3: {"en": "Moderate", "nl": "Gemiddeld"},
    4: {"en": "High", "nl": "Hoog"},
    5: {"en": "Very High", "nl": "Zeer Hoog"},
}
