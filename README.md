[![GitHub release](https://img.shields.io/github/v/release/CNC-Buddy/R290_heatpump)](https://github.com/CNC-Buddy/R290_heatpump/releases)
[![GitHub All Releases](https://img.shields.io/github/downloads/CNC-Buddy/R290_heatpump/total)](https://github.com/CNC-Buddy/R290_heatpump/releases)  
[![Buy Me a Coffee](https://buymeacoffee.com/assets/img/custom_images/white_img.png)](https://buymeacoffee.com/cnc.buddy)



# R290 Heat Pump (Home Assistant Integration)

A Home Assistant custom integration for monitoring and controlling an R290 heat pump produced by SolarEast via Modbus, including PV-aware heatcurve optimization, COP calculation, and an optional Lovelace dashboard. You can find the diffrent Sales Names  at the end of the Readme or under Device Names for BLN0##TC#. It can be, that BLN0##TB# will also work.

[Video: Feature Overview]

- Demo video : [Demo at Youtube](https://youtu.be/2ENamuptTN0)

## Features

- Modbus bridge (RTU-over-TCP/TCP) with batched register reads and configurable block size/pause.
- Heat pump entities
  - Rich set of sensors, writable numbers, and selects (per register map).
  - Multi-slave support; stable entity IDs with `slave_N` suffix.
  - Compressor diagnostics: start counters and runtime (in hours) for all slaves.
- PV optimization for temperature curves
  - Per-curve switch to enable optimization.
  - Selectable grid/battery offsets (−10 … +10 °C), thresholds, and cooldown.
  - Battery rule: triggers when battery SoC is less than or equal to its threshold.
  - Grid rule: triggers when PV power is greater than or equal to its threshold.
  - If both trigger, the offset with the larger absolute value wins (bounded to ±10 °C).
- COP calculator (no external DB)
  - Uses an in-memory accumulator persisted via HA storage.
  - Period sensors: Today, Yesterday, 7d, 30d, 365d, Overall.
  - Event-driven updates (optional): trigger on heat meter, power meter, or both.
- Lovelace dashboard
  - Packaged storage dashboard with a curated overview.
  - Can be created during bridge setup and recreated from options.

## Installation

- Copy this repo into your Home Assistant `custom_components/r290_heatpump` directory.
- Restart Home Assistant.
- Add integration via Settings → Devices & Services → “Add Integration” → R290 Heat Pump.

### Installation via HACS (recommended)

- Open HACS: HACS > Integrations > menu (⋯) > Custom repositories
- Add repository URL: `https://github.com/CNC-Buddy/R290_heatpump` with type "Integration"
- Search for "R290 Heat Pump" in HACS and install
- Restart Home Assistant
- Add the integration: Settings > Devices & Services > Add Integration > R290 Heat Pump
  
## Configuration (Flows)

- Modbus Bridge
  - Connection: `rtuovertcp` or `tcp`, host, port.
  - Timeouts/retries, block size/pause for batch reads.
  - Checkbox: `Create dashboard` (creates the bundled Lovelace dashboard during setup).
  - Options: `Recreate dashboard` (if removed, re-create it from options later).
- Heat Pump
  - Slave ID, fast/long scan intervals.
- Temperature Curves (heating, floor heating, hot water, cooling)
  - Required: outdoor temperature sensor entity.
  - Optional: PV power sensor and/or battery SoC sensor.
  - Entities created per curve: switch, selects (offsets), numbers (thresholds, cooldown).
- COP Calculator
  - Required: heat meter entity and power meter entity (must differ).
  - Options: trigger updates on heat meter changes and/or power meter changes (event-driven).

## PV Optimization — Logic

- Enable/disable per curve with `switch.r290_heatpump_<prefix>_pv_optimization`.
- Grid rule
  - Interprets PV power in kW (auto-converts W/Wh → kW).
  - Applies `pv_grid_offset` when power ≥ `pv_grid_threshold_kw`.
- Battery rule
  - Applies `pv_battery_offset` when SoC ≤ `pv_battery_threshold_pct`.
- If both rules match, the offset with the largest absolute value is selected.
- Cooldown prevents rapid switching: a change of offset requires that `pv_cooldown_minutes` has elapsed since the last change.
- Final command is clamped to `[t_flow_min, t_flow_max]`.

Entity naming uses the curve prefixes `heating`, `floor_heating`, `hotwater`, `cooling`, e.g.:

- `switch.r290_heatpump_heating_pv_optimization`
- `select.r290_heatpump_heating_pv_grid_offset`
- `select.r290_heatpump_heating_pv_battery_offset`
- `number.r290_heatpump_heating_pv_grid_threshold_kw`
- `number.r290_heatpump_heating_pv_battery_threshold_pct`
- `number.r290_heatpump_heating_pv_cooldown_minutes`

## Compressor Diagnostics

- Starts counter: total increasing.
- Runtime: in hours (state persisted and restored). Internal accumulation is in seconds; state exposed in hours.
- Created for all slaves; enabled by default.

## Dashboard

- A storage-mode Lovelace dashboard is included.
- During Modbus Bridge setup, keep `Create dashboard` checked to auto-generate it.
- If you remove it, use the Modbus Bridge Options and toggle `Recreate dashboard` to generate it again.

## Event-Driven COP Updates

- In COP Calculator options, choose which meter(s) should trigger recomputation.
- When enabled, COP sensors set `should_poll=False` and update on source entity state changes.
- Otherwise, a 5-minute polling interval is used.

## Troubleshooting

- “Cannot connect” during bridge setup: verify host/port, and device network reachability.
- No entities: ensure the bridge is configured and the heat pump entry is added for the correct slave.
- PV offsets not applying: verify the PV power/battery sensors and thresholds; check the per-curve switch state.
- COP shows `unknown`: confirm both meter entities publish numeric states; enable event triggers if you prefer push updates.

## Development Notes

- This integration uses HA’s config entries, selectors, and storage-based dashboards.
- Batching minimizes Modbus register calls and supports multiple scan intervals.
- PV and COP logic are isolated so behavior can be refined without touching Modbus I/O.

## Open Topics

- Dashboard optimization [open]
- Integrating L-Parameter [open]
- Split COP: hot water vs heating [open]
- Add remarks/notes [open]

## Testing Stage

- COP event-driven updates [implemented; needs verification]
- PV optimization battery rule (<= threshold) [implemented; needs verification]
- Config flow: dashboard create/recreate [implemented; needs verification]
- Diagnostics at slave 2 (counters + status) [enabled by default; verify entities visible]
- User parameters writable? [partially supported via numbers; verify coverage]
- Heatcurve switch not affecting behavior? [to investigate]
- Adjust hub default values [open; collect desired defaults]
- Hub options reset on restart? [investigate] 

## My used Hardware

- 2x Terra Next ONE+ - BLN-012TC3
- PUSR DR302 - Modbus RTU Gateway
- Shelly 3EM for electrical enegry monitoring
- kamstrup Multical 303 for heat energy monitoring
- nanoCUL USB Stick 868 Mhz with CC1101 SMA antenna for Multical 303 readout with Wmbusmeters Addon

-------------------------------------------------------

The Modbus communication is the same according to the instructions, same for the device parameters and settings. 
Here is a list of the different sales types:

###########__6kW - 230V___###############

SolarEast Heat Pump Ltd. - BLN-006TC1  			            (China)
Jiangsu Sunrain Solar Energy Co., Ltd. - SMHP - 006C1 	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - BLN-006TC1  	  (China)
12warm.de - Terra Next ONE - BLN-006TC1  		            (Germany)
Hainzl - BLN-006TC1  				                          	(Germany)
Erba Wärmetechnik GmbH - BLN-006TC1  		              	(Germany)
WP Heater - BLN-006TC1  				                        (Germany)
SKS Kompressoren GmbH - BLN-006TC1  		              	(Germany)
M&S POWER - HP-M6-E-S  				                        	(Germany)
Megawave Energy Ltd - MWMHPC-6KW1		                  	(United Kingdom)
ARDEN Heat Pumps Pty Ltd - BLN-006TC1		              	(Australia)
NAGAI - BLN-006TC1				                            	(Bosnia-Herzegovina, Croatia)
SunAir Energy Solutions - BLN-006TC1  		            	(Spain, Nederland)
PERFEXIM - PHA-50 50-006-0816-001		                  	(Poland)
ElektroFrigo - BLN-006TC1				                        (Serbia)

###########__8kW - 230V___###############

SolarEast Heat Pump Ltd. - BLN-008TC1  		            	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - SMHP - 008C1  	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - BLN-008TC1    	(China)
12warm.de - Terra Next ONE - BLN-008TC1              		(Germany)
Hainzl - BLN-008TC1  				                          	(Germany)
Megawave Energy Ltd - MWMHPC-8KW1		                  	(United Kingdom)
NAGAI - BLN-008TC1				                            	(Bosnia-Herzegovina, Croatia)
SunAir Energy Solutions - BLN-008TC1  		            	(Spain, Nederland)

###########__8kW - 380V___###############

SolarEast Heat Pump Ltd. - BLN-008TC3  	            		(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - SMHP - 008C3  	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - BLN-008TC3    	(China)
12warm.de - Terra Next ONE - BLN-008TC3  	            	(Germany)
Hainzl - BLN-008TC3  				                          	(Germany)
Megawave Energy Ltd - MWMHPC-8KW3		                  	(United Kingdom)
SunAir Energy Solutions - BLN-008TC3  		            	(Spain, Nederland)

###########__12kW - 230V___###############

SolarEast Heat Pump Ltd. - BLN-012TC1  			            (China)
Jiangsu Sunrain Solar Energy Co., Ltd. - SMHP - 012C1  	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - BLN-012TC1    	(China)
12warm.de - Terra Next ONE+ - BLN-012TC1          	  	(Germany)
Hainzl - BLN-012TC1  			                          		(Germany)
WP Heater - BLN-012TC1  				                        (Germany)
SKS Kompressoren GmbH - BLN-012TC1  			              (Germany)
M&S POWER - HP-M12-E-S  			                        	(Germany)
Megawave Energy Ltd - MWMHPC-12KW1			                (United Kingdom)
ARDEN Heat Pumps Pty Ltd - BLN-012TC1		              	(Australia)
NAGAI - BLN-0012TC1					                            (Bosnia-Herzegovina, Croatia)
SunAir Energy Solutions - BLN-012TC1  		            	(Spain, Nederland)
PERFEXIM - PHA-50 50-012-1455-001			                  (Poland)
ElektroFrigo - BLN-012TC1			                        	(Serbia)

###########__12kW - 380V___###############

SolarEast Heat Pump Ltd. - BLN-012TC3  		            	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - SMHP - 012C3  	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - BLN-012TC3  	  (China)
12warm.de - Terra Next ONE+ - BLN-012TC3  	            (Germany)
Hainzl - BLN-012TC3  				                          	(Germany)
Erba Wärmetechnik GmbH - BLN-0012TC3  	            		(Germany)
Kamäleon - BLN-0012TC3  	                        			(Germany)
WP Heater - BLN-012TC3 			                        		(Germany)
SKS Kompressoren GmbH - BLN-012TC3  		               	(Germany)
M&S POWER - HP-M12-E-S2  		                        		(Germany)
KWE - Primus BLN-012TC3  			                        	(Germany)
Megawave Energy Ltd - MWMHPC-12KW3			                (United Kingdom)
ARDEN Heat Pumps Pty Ltd - BLN-012TC3		              	(Australia)
NAGAI - BLN-012TC3				                            	(Bosnia-Herzegovina, Croatia)
SunAir Energy Solutions - BLN-012TC3  		            	(Spain, Nederland)
PERFEXIM - PHA-50 50-012-1455-003		                  	(Poland)
ElektroFrigo - BLN-012TC3			                        	(Serbia)

###########__18kW - 230V___###############

SolarEast Heat Pump Ltd. - BLN-018TC1  		            	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - SMHP - 018C1  	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - BLN-018TC1    	(China)
12warm.de - Terra Next Pro - BLN-018TC1              		(Germany)
Hainzl - BLN-018TC1  				                          	(Germany)
SKS Kompressoren GmbH - BLN-018TC1  		              	(Germany)
WP Heater - BLN-018TC1  			                        	(Germany)
Megawave Energy Ltd - MWMHPC-18KW1		                	(United Kingdom)
ARDEN Heat Pumps Pty Ltd - BLN-018TC1			              (Australia)
NAGAI - BLN-018TC1				                            	(Bosnia-Herzegovina, Croatia)
SunAir Energy Solutions - BLN-018TC1  		            	(Spain, Nederland)
PERFEXIM - PHA-50 50-018-1945-001			                  (Poland)
ElektroFrigo - BLN-018TC1			                        	(Serbia)

###########__18kW - 380V___###############

SolarEast Heat Pump Ltd. - BLN-018TC3  		             	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - SMHP - 018C3  	(China)
Jiangsu Sunrain Solar Energy Co., Ltd. - BLN-018TC3    	(China)
12warm.de - Terra Next Pro - BBLN-018TC3  		          (Germany)
Hainzl - BLN-018TC3  				                          	(Germany)
Erba Wärmetechnik GmbH - BLN-018TC3  		              	(Germany)
SKS Kompressoren GmbH - BLN-018TC3  	              		(Germany)
WP Heater - BLN-018TC3  			                        	(Germany)
M&S POWER - HP-M18-E-S  			                        	(Germany)
KWE - Primus BLN-018TC3  			                        	(Germany)
Megawave Energy Ltd - MWMHPC-18KW3	                		(United Kingdom)
ARDEN Heat Pumps Pty Ltd - BLN-018TC3			              (Australia)
NAGAI - BLN-018TC3				                            	(Bosnia-Herzegovina, Croatia)
SunAir Energy Solutions - BLN-018TC3  		            	(Spain, Nederland)
PERFEXIM - PHA-50 50-018-1945-003	                  		(Poland)
ElektroFrigo - BLN-018TC3			                        	(Serbia)

#####################################################

Contributions and issue reports are welcome. Please describe your setup (bridge mode, firmware, HA version) when reporting issues.
