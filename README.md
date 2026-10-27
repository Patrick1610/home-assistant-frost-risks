# Frost Risks

Frost Risks provides local meteorological calculations and an advisory
**Defrost recommended** sensor for a potentially icy or snow-covered surface.
It does **not** turn on heating, defrost, a vehicle, or any other device. It has no
Tesla/Tessie dependency, network calls, account, or weather subscription of its own.

Use the output to decide whether an independently controlled preheating session
needs a defrost stage. Ordinary cold, dry air is not by itself evidence of ice.
The same calculations can support a window, roof, greenhouse, or another exposed
surface. This is a transparent screening model, not an ice detector, calibrated
probability, safety guarantee, or prediction of a guaranteed melting time.

## Install or update

Add `https://github.com/Patrick1610/home-assistant-frost-risks` as a HACS custom
integration repository, or copy `custom_components/frost_risks` into Home
Assistant's `custom_components` directory. Minimum Home Assistant: **2025.12**.
Restart Home Assistant after installing updated integration code.

In Settings → Devices & services → Frost Risks, choose either:

- **One weather entity**, such as a local OpenWeatherMap entity; or
- **A temperature and a relative-humidity sensor**, as in previous versions.

Individual temperature/RH sensors override their respective weather values. An
explicitly selected sensor becoming unavailable does not silently switch to a
different weather source. Existing sensor-only entries keep working without
recreation or mandatory additional setup.

Optional context:

- A weather entity supplies temperature/RH, cloud coverage, wind and its current
  precipitation condition. It must describe the **same location** as the surface.
  A weather entity for home must not automatically be used for a car elsewhere.
- Current rain/snow amount or rate sensors can override precipitation detection.
  They must report **current precipitation**, not a lifetime or seasonal total.
  A positive value supplies precipitation evidence; zero means none reported now.
- A measured surface-temperature sensor takes precedence over an estimate.

Weather observations older than three hours are unavailable context. If wind
units or optional weather fields are missing, they are not invented as zero wind,
clear sky, or no snow. A strong independent snow report remains useful even if
other required meteorological values are missing. The integration never fetches
a forecast or locates a vehicle itself.

## Outputs and identities

The original eight entities retain their unique IDs (`entry_id` + sensor key),
device binding and existing configuration entry. Home Assistant entity IDs and
recorded history therefore remain attached to the same entities:

| Existing sensor | Meaning |
|---|---|
| Absolute Humidity | Actual water-vapour density, g/m³ |
| Dew Point | Magnus-Tetens condensation temperature, °C |
| Frost Point | Ice-saturation inverse from actual vapour pressure below zero; above zero it reports the dew point |
| Freezing Point | **Deprecated legacy humidity-derived index**, not water's freezing point |
| Wet-Bulb Temperature | Stull evaporative-cooling approximation, °C |
| Vapor Pressure | Partial vapour pressure, hPa |
| Humidity Ratio | kg water vapour per kg dry air, using standard pressure |
| Frost Risk Level | Advisory surface-risk category, not a percentage probability |

Two entities are added to the existing device:

- **Defrost recommended** (`binary_sensor.<name>_defrost_recommended`):
  `on`, `off`, or `unknown` when a recommendation cannot be established.
  Unknown retains readable reason/quality/missing-context attributes.
- **Surface cleared** (`button.<name>_surface_cleared`): acknowledgement that the
  relevant surface has actually been cleared, for example after a completed
  defrost stage. It only clears internal evidence; it does not control a device.

The on/off recommendation includes `reason`, `quality`, `missing_context`,
`surface_temperature_used`, `surface_basis`, timestamped `evidence`,
`calculation_version` and `advisory_only`. A computed surface value is explicitly
labelled as estimated; it is never presented as a measured glass temperature.

Reasons include `surface_frost_possible`, `frozen_wet_surface`, `recent_snow`,
`residual_ice`, `dry_no_ice_evidence`, `surface_above_freezing`, `surface_cleared`
and `insufficient_data`. `quality` is `good`, `limited`, or `unknown`, not a
calibrated confidence percentage. `good` means the selected context is present,
not that actual ice has been observed.

## How the recommendation works

There must be a plausible subzero surface **and moisture**, or retained evidence
of recent snow/ice. A low dew point in warm dry air does not raise the risk merely
because the dew point is negative. The legacy Freezing Point index is never used
to decide whether a surface freezes.

Without a measured surface, these explicit empirical allowances are used:

| Context | Estimated surface below air temperature |
|---|---:|
| Daylight | 0 °C |
| Night, clouds ≤30%, wind ≤2 m/s | 3 °C |
| Night, clouds ≥80% or wind ≥5 m/s | 0.5 °C |
| Other complete night context | 1.5 °C |
| Missing radiation context | 2 °C, labelled `limited_air_screening` |

Night is obtained from Home Assistant's `sun.sun`, or an unambiguous weather
condition (`clear-night` / `sunny`). These allowances are screening heuristics,
not a calibrated thermal model. Sheltered parking, a warm engine, recent driving,
solar heating and other heat sources can change the real surface temperature.
The limited fallback keeps temperature/RH-only installations useful without
silently claiming that the sky is clear or the wind calm.

At or below zero, vapour deposition is screened against the frost point; a
positive dew point means condensation can occur before that water freezes.
Recent wetness can freeze even in otherwise dry air. Current or recent snow
can justify defrost independently of a missing humidity observation.

Risk categories: 0 = no current evidence; 1 = cold/near-zero surface but no
identified ice evidence; 3 = possible surface frost; 4 = recent snow or possible
frozen/residual wetness. Categories 2 and 5 are reserved rather than manufacturing
more precision from the same measurements. Existing consumers of the old
numeric score should be reviewed; the new binary sensor is the simpler output.

## Evidence, restart and clearing

The integration remembers recent wetness for **6 hours** and possible snow or
frozen wetness for **24 hours**, even if rain/snow has stopped. These are bounded
screening windows, **not assertions that material has melted when a timer ends**.
A long history gap lowers data quality. No past evidence is fabricated when the
integration is first installed; observation starts then.

State is stored per entry with aware UTC timestamps using Home Assistant's
storage helper. Restarts and unchanged-source options reloads preserve it.
Malformed/future timestamps are ignored. Changing source bindings starts a new
context so evidence from one location cannot be transferred to a different one.
Renaming an instance does not discard its memory. No Recorder query or history
rewrite is performed.

Use **Surface cleared** only after a completed/confirmed clearing operation.
An unchanged numeric precipitation value is not replayed after acknowledgement;
a value change supplies a new observation. A genuinely current weather condition
reporting continuing snowfall/rain can legitimately add new evidence.
Do not select rolling historical totals as if they measured current precipitation. Atmospheric frost formation
is held off for five minutes after acknowledgement, then may become plausible
again if the conditions persist. An actuator automation should retain its own
session, eligibility and repeat limits instead of treating every `on` reading as
permission to start another defrost cycle.

Calculations update on local source events and once a minute, so memory/timers
also progress when values do not change. State writes are debounced; unload
removes listeners/timers and flushes pending evidence. Diagnostic evidence
attributes are excluded from Recorder, and one-minute heartbeats do not create
new advisory-history rows. Observation heartbeats are persisted at most every
30 minutes; material evidence changes are persisted promptly. No climate or switch
services are called by this integration.

## Upgrade from 2.0.0

- Version 2.1.1 also makes the new entities' names/IDs independent of platform
  setup ordering, with forced-order regression checks in English and Dutch.
- **Absolute Humidity is corrected by a factor of 100 before rounding.** At
  13 °C / 87% the correct output is 9.86 g/m³, not 0.10; at 14 °C / 87% it is
  10.49 g/m³. The earlier implementation mixed fractional RH with a constant for
  percent RH. Review automations with old absolute-humidity thresholds.
- Past Recorder values/statistics are **not** rewritten, purged, or backfilled.
  Historical plots spanning this release therefore show the old scale followed
  by the corrected scale. `calculation_version` marks the new calculation.
- The old Freezing Point entity remains numerically compatible and explicitly
  marked `legacy` / `deprecated`. It is not the physical freezing point of water.
- The Frost Point inverse and risk model change. The old risk score could report
  level 4 at +10 °C / 30% RH, or high risk from cold alone. The new model requires
  relevant surface/moisture evidence. Review old score-based automations.
- Configure/Options works with modern Home Assistant's read-only `config_entry`
  property. Saved options actually override entry data; removing an optional
  source does not resurrect its old value.

Input validation rejects booleans, NaN/infinity, RH outside 0–100%, and air
temperature outside the declared −45…60 °C engineering domain. RH=0 gives zero
vapour density but no finite dew/frost point. Temperatures with °F units are
converted before calculation. The ice inverse is bounded to −65…0 °C; Stull is
used within −20…50 °C and RH5…99%, with exact saturation handled separately.
Missing/out-of-domain numerical calculations are unavailable rather than invented
zeroes. The binary recommendation remains `unknown` with readable diagnostics when
required data are insufficient. Extremely dry air with a frost point below the
formula domain is correctly classified as no deposition evidence when the
surface is warmer than that domain.

## Sources and limits

- [Met Office: frost and ice](https://weather.metoffice.gov.uk/learn-about/weather/types-of-weather/frost-and-ice):
  exposed surfaces can freeze with air temperatures 0–4 °C on clear, calm nights.
  This supports including radiation context; it does not validate our exact
  empirical allowances or prove that a particular vehicle is iced over.
- [WMO Guide No. 8, Annex 4.B, humidity formulae](https://radiometrics.com/wp-content/uploads/2021/10/wmo_8_en-2012.pdf):
  ice saturation/inversion coefficients 22.46 and 272.62; the inverse uses actual
  vapour pressure, not RH treated as if it were already relative to ice.
- [Stull 2011](https://doi.org/10.1175/JAMC-D-11-0143.1): wet-bulb approximation,
  its input range and limitations. Wet-bulb temperature is contextual, not a
  measurement of glass or evidence that ice already exists.

The model needs evaluation against real observed frost/snow events before anyone
can claim a detection rate or choose optimum thresholds for a specific surface.

## Development checks

Use Python 3.14 and the pinned test dependency group in `pyproject.toml`, or an
existing compatible environment. Run:

```sh
python -m pytest -q
python -m ruff check custom_components tests
python -m ruff format --check custom_components tests
```

Tests cover independent numerical checks, warm/dry and dry-freeze false positives,
radiation context, rain then freezing, snow memory/clearing, invalid/missing data,
unit conversion, persistence, time-based updates, unchanged entity/device IDs,
weather-only setup, modern OptionsFlow and cleanup on unload.

## License

MIT. Originally inspired by
[papo-o/home-assistant-frost-risks](https://github.com/papo-o/home-assistant-frost-risks).
