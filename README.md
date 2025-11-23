[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Frost Risks

A modern Home Assistant custom component for comprehensive frost risk monitoring and meteorological calculations.

## Features

This integration creates **8 advanced meteorological sensors** based on temperature and humidity readings:

1. **Absolute Humidity** (g/m³) - Actual water vapor content in the air
2. **Dew Point** (°C) - Temperature at which water vapor condenses
3. **Frost Point** (°C) - Temperature at which frost forms (below 0°C)
4. **Freezing Point** (°C) - Atmospheric freezing point with humidity effects
5. **Wet-Bulb Temperature** (°C) - Temperature with evaporative cooling
6. **Vapor Pressure** (hPa) - Partial pressure of water vapor
7. **Humidity Ratio** (kg/kg) - Mass of water vapor per unit mass of dry air
8. **Frost Risk Level** (0-5) - Multi-factor frost risk assessment

### Modern Architecture

- ✅ **Config Flow UI** - Easy setup through Home Assistant UI (no YAML required)
- ✅ **SensorEntity** - Uses modern Home Assistant sensor architecture
- ✅ **Async/Await** - Fully asynchronous implementation
- ✅ **Auto-Update** - Automatically recalculates when temperature or humidity changes
- ✅ **HACS Compatible** - Ready for installation via HACS
- ✅ **Bilingual** - English and Dutch translations included

### Accurate Meteorological Formulas

All calculations use scientifically validated formulas:
- **Magnus-Tetens** formula for dew point
- **Stull's formula (2011)** for wet-bulb temperature
- **ASHRAE** standards for humidity ratio
- **Modified Magnus** formula for frost point

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/Patrick1610/home-assistant-frost-risks` as repository
6. Category: Integration
7. Click "Add"
8. Search for "Frost Risks" and install
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/frost_risks` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### UI Configuration (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Frost Risks**
4. Enter a name for your sensor group
5. Select your temperature sensor (must have device_class: temperature)
6. Select your humidity sensor (must have device_class: humidity)
7. Click **Submit**

The integration will automatically create all 8 sensors.

### Example Sensors Created

If you name your integration "Living Room", you'll get:

```
sensor.living_room_absolute_humidity
sensor.living_room_dew_point
sensor.living_room_frost_point
sensor.living_room_freezing_point
sensor.living_room_wet_bulb_temperature
sensor.living_room_vapor_pressure
sensor.living_room_humidity_ratio
sensor.living_room_frost_risk_level
```

## Frost Risk Levels

The frost risk level sensor provides a 0-5 scale based on multiple meteorological factors:

| Level | Description | Risk |
|-------|-------------|------|
| 0 | No Risk | No frost expected |
| 1 | Very Low | Minimal frost risk |
| 2 | Low | Slight possibility of frost |
| 3 | Moderate | Frost possible in favorable conditions |
| 4 | High | Frost likely |
| 5 | Very High | Frost highly likely |

The risk assessment considers:
- Current temperature
- Dew point temperature
- Wet-bulb temperature
- Freezing point
- Absolute humidity

## Usage Examples

### Automation - Frost Warning

```yaml
automation:
  - alias: "Frost Warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.outdoor_frost_risk_level
        above: 3
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Frost Warning"
          message: "High frost risk detected. Protect sensitive plants!"
```

### Automation - Smart Heating

```yaml
automation:
  - alias: "Prevent Pipe Freezing"
    trigger:
      - platform: numeric_state
        entity_id: sensor.garage_frost_risk_level
        above: 4
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.garage_heater
        data:
          temperature: 5
```

### Dashboard Card

```yaml
type: entities
title: Frost Monitoring
entities:
  - entity: sensor.outdoor_temperature
  - entity: sensor.outdoor_humidity
  - entity: sensor.outdoor_dew_point
  - entity: sensor.outdoor_frost_point
  - entity: sensor.outdoor_wet_bulb_temperature
  - entity: sensor.outdoor_frost_risk_level
```

## Sensor Attributes

Each sensor includes additional attributes:

```yaml
temperature: 2.5  # Source temperature in °C
humidity: 85      # Source humidity in %
```

The frost risk level sensor also includes:
```yaml
description_en: "High"       # English description
description_nl: "Hoog"       # Dutch description
```

## Technical Details

### Formulas Used

#### Absolute Humidity
```
AH = (6.112 × e^((17.67×T)/(T+243.5)) × RH × 2.1674) / (273.15 + T)
```

#### Dew Point (Magnus-Tetens)
```
α = (17.27×T)/(237.7+T) + ln(RH/100)
Td = (237.7 × α) / (17.27 - α)
```

#### Wet-Bulb Temperature (Stull's Formula)
```
Tw = T×atan(0.151977×√(RH+8.313659)) + atan(T+RH) - atan(RH-1.676331)
     + 0.00391838×RH^1.5×atan(0.023101×RH) - 4.686035
```

#### Vapor Pressure
```
es = 6.112 × exp((17.67×T)/(T+243.5))
e = es × (RH/100)
```

#### Humidity Ratio
```
W = 0.622 × (e / (P - e))
where P = 1013.25 hPa (standard atmospheric pressure)
```

## Multiple Instances

You can add multiple instances of this integration for different locations:

1. **Outdoor** monitoring (garden, balcony)
2. **Indoor** monitoring (living room, bedroom)
3. **Garage/Shed** monitoring
4. **Greenhouse** monitoring

Each instance creates its own set of 8 sensors.

## Support & Contributing

- 🐛 **Issues**: [Report bugs or request features](https://github.com/Patrick1610/home-assistant-frost-risks/issues)
- 💬 **Discussions**: [Ask questions and share ideas](https://github.com/Patrick1610/home-assistant-frost-risks/discussions)
- 🔧 **Pull Requests**: Contributions are welcome!

## Credits

Originally inspired by [papo-o/home-assistant-frost-risks](https://github.com/papo-o/home-assistant-frost-risks), completely rewritten for modern Home Assistant architecture.

## License

MIT License - See [LICENSE](LICENSE) file for details


