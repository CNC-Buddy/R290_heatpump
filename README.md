[![GitHub release](https://img.shields.io/github/v/release/CNC-Buddy/R290_heatpump)](https://github.com/CNC-Buddy/R290_heatpump/releases)
[![GitHub All Releases](https://img.shields.io/github/downloads/CNC-Buddy/R290_heatpump/total)](https://github.com/CNC-Buddy/R290_heatpump/releases)  
[![Buy Me a Coffee](https://buymeacoffee.com/assets/img/custom_images/white_img.png)](https://buymeacoffee.com/cnc.buddy)


# R290 Heat Pump (Home Assistant Integration)

A Home Assistant custom integration for monitoring and controlling an R290 heat pump produced by SolarEast via Modbus, including PV-aware heatcurve optimization, COP calculation, and an optional Lovelace dashboard. You can find the different sales names at the end of this README or in Device Names for BLN0##TC#. It can be, that BLN0##TB# will also work.

[Video: Feature Overview]

- Demo video: [Feature overview on YouTube](https://youtu.be/2ENamuptTN0)

## Features

- Modbus bridge (RTU-over-TCP/TCP) with batched register reads and configurable block size/pause.
- Heat pump entities
  - Rich set of sensors, writable numbers, and selects (per register map).
  - Multi-slave support; stable entity IDs with `slave_N` suffix.
  - Compressor diagnostics: start counters and runtime (in hours) for all slaves.
- PV optimization for temperature curves
  - Per-curve switch to enable optimization.
  - Grid rule uses configurable min/max thresholds (`pv_grid_threshold_min_kw`, `pv_grid_threshold_max_kw`) and offsets (`pv_grid_offset_min`, `pv_grid_offset_max`) to interpolate a dynamic temperature boost.
  - Battery rule: triggers when battery SoC is less than or equal to its threshold (`pv_battery_threshold_pct`) and applies the configured offset.
  - If both trigger, the offset with the larger absolute value wins (bounded to ±10 °C).
  - Independent hold timers for PV offsets (`pv_hold_minutes`) and external offsets (`external_offset_hold_minutes`) prevent rapid switching.
- COP calculator (no external DB)
  - Uses an in-memory accumulator persisted via HA storage.
  - Period sensors: Today, Yesterday, 7d, 30d, 365d, Overall.
  - Event-driven updates (optional): trigger on heat meter, power meter, or both.
  - Optional separate heating and hot-water COP sensors using an external on/off hot-water status sensor.
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
  - Connection: **RTU over TCP**, **Modbus TCP**, or **ModbusProxy** compatibility mode; host, port.
  - Timeouts/retries, block size/pause for batch reads.
  - Checkbox: `Create dashboard` (creates the bundled Lovelace dashboard during setup).
  - Options: `Recreate dashboard` (if removed, re-create it from options later).
- Heat Pump
  - Slave ID, fast/long scan intervals.
- Temperature Curves (heating, floor heating, hot water, cooling)
  - Required: outdoor temperature sensor entity.
  - Optional: PV power sensor and/or battery SoC sensor.
- Entities created per curve: switch, selects (offsets), numbers (thresholds, hold time).
- COP Calculator
  - Required: heat meter entity and power meter entity (must differ).
  - Options: trigger updates on heat meter changes and/or power meter changes (event-driven).
  - Optional split: select a hot-water status sensor (`on` = hot water, `off` = heating). Split accounting follows the status at the time an energy delta is received; it does not reconstruct historical operating-mode changes.

### Release 1.0.6

This release combines the shared bridge, update delivery and reconnect changes below with the published 1.0.2 PV reset behavior. The configurable `pv_offset_reset_kw`, its number entities and dashboard controls remain available. Returning the PV grid offset to zero respects `pv_hold_minutes`. The local COP additions are also included: optional heating/hot-water segments and time-based distribution of delayed heat-meter deltas across daily buckets.

Validation: 34 offline regression tests, including five PV reset/hold cases and four COP accumulation/storage cases, plus eight loopback transport tests per supported test version of pymodbus (3.10.0 and 3.16.1). Tests use doubles or simulated devices and do not establish long-term stability on every gateway.

### Clear connection labels (1.0.6)

Setup and bridge options now display **ModbusProxy** for the existing `tcp_proxy` mode. The other labels are **RTU over TCP** (`rtuovertcp`) and **Modbus TCP** (`tcp`). Saved configuration values and routing remain unchanged, so existing entries need no migration. The bridge connection-type sensor also uses these display names; automations comparing that sensor's state must use the new label. Diagnostic `connection_type` attributes retain the raw protocol value.

This is a naming change. The finite timeout required in the proxy configuration is described below; updating the integration alone does not resolve a blocked proxy.

### Reconnect feedback and verification (1.0.5)

The reconnect button now clears the previous communication result after acquiring the I/O lock and opening a new connection. An open socket alone reports `Not checked`. The button reads one already configured register per active slave on this bridge, then requests the fastest batch refresh for the slaves that answered. Other bridges are not touched; regular slow polling remains unchanged. When no register entities are active, reconnect only tests the TCP connection and leaves the Modbus status unverified.

Connection and probe failures are returned as Home Assistant action errors instead of being hidden in the log. Button attributes show `reconnecting`, the UTC attempt timestamp `last_reconnect`, `last_reconnect_error`, and `verified_slaves`. Bridge status continues to describe the most recent Modbus request, so a successful request from one slave does not verify all other slaves. Repeated clicks during the same attempt do not queue more reconnects. A reconnect waits for in-flight bus operations, including their timeouts, and never interrupts a write. It does not change the configured protocol: for the affected proxy route, select `tcp_proxy` on the R290 bridge, keeping the proxy's upstream setting `rtutcp`.

Validation: 25 offline lifecycle/action regression tests and 8 loopback transport tests; transport tested with pymodbus 3.10.0 and 3.16.1. No live-device writes or automatic installation were performed.

### Proxy compatibility and update delivery (1.0.4)

For a direct RTU-over-TCP gateway, keep `rtuovertcp`. For a normal Modbus TCP server, keep `tcp`. The new, explicitly selected `tcp_proxy` mode is a workaround for proxies that misclassify RTU requests at register 0 and always return TCP transaction ID 1. It uses the TCP framer and a fresh client/socket for each transaction, closes it afterwards, and keeps reads and writes serialized through the shared bridge. It does not change the proxy's upstream protocol or connect directly to the gateway behind it.

This costs an extra TCP connection setup per transaction. Response transaction IDs are still validated; timed-out writes are not automatically retried in this mode. A proxy that truncates Modbus exception responses still needs a proxy-side fix: a client cannot reconstruct missing data or repair the proxy's upstream stream. The workaround rejects malformed replies rather than treating them as measurements. Use normal `tcp` after the proxy itself is fixed.

The proxy device also needs an explicit, finite upstream `timeout`. In the examined proxy code an omitted timeout means an unbounded wait while holding the device lock. A device that does not respond then blocks subsequent clients, even after they disconnect; the client idle timeout does not cover this wait. The observed TerraNext configuration omitted this field, and the log filled all 16 client slots after the first stalled request. For this route, set the proxy device's `timeout` to `2.0` seconds and `connection_time` to `0.1` seconds, with the R290 bridge's `request_timeout` at `10` seconds. The client budget allows for the proxy's two upstream attempts. Restart the proxy after saving to clear already blocked handlers, and verify that its generated TerraNext configuration includes `timeout: 2.0`. A loopback reproduction confirmed the indefinite lock with no timeout and recovery with a finite timeout; this does not prove why the original device request went unanswered or eliminate every possible timeout.

Bridge status now describes the last Modbus operation: `Not checked` until a register operation succeeds, `Connected` after success, and `Error` after a failed operation. Attributes expose `socket_connected`, `last_request_success`, `last_response` (UTC), and `last_error`. `Connected` describes the last operation, not freshness of every sensor; intentional socket closure in `tcp_proxy` does not mean a communication failure. The legacy `connected` attribute continues to indicate the socket state.

Register entities now receive completed batch updates directly, without a second entity polling cycle. Startup registers addresses first and lets the existing delayed batch refresh collect them, instead of asking for a full refresh for each sensor/number. Missing registers in a completed batch make the corresponding entities unavailable. Each entry retains its `scan_interval` and `long_scan_interval`. These are coordinator scheduling intervals; reading time, the shared bus queue, pauses and timeouts can extend the elapsed time between completed refreshes.

Installation: replace the complete `custom_components/r290_heatpump` directory and restart Home Assistant Core. Existing entries and entity IDs stay intact. Then select the desired connection type in the bridge options; it propagates to all linked entries.

Validation: the offline lifecycle suite runs with `python -m unittest discover -s tests -v`. `python tests/proxy_transport_checks.py` runs separately with real pymodbus installed, using only loopback test servers. It covers repeated proxy reads/writes, both slaves, register 0, direct RTU and normal TCP, invalid replies, no write retry, and delayed-response isolation. Tested with pymodbus 3.10.0 and 3.16.1. A separate local reproduction also passed valid FC03/FC06 transactions against the unchanged TCzerny/ha-modbusproxy source; this is not a live-device validation.

### Shared bridge connection (1.0.3)

Heat pumps and temperature curves remain separate integration entries, with their own sensor assignments and options. Entries linked to a bridge share one Modbus client and serialize reads and writes. The bridge device is their parent in Home Assistant's device registry.

Changing the bridge's host, port, protocol, timeouts or batch settings updates all linked entries, including their saved configuration. A failed connection check keeps the previous settings. Existing installations with one bridge automatically associate legacy entries with it on startup, including entries that still contain the old gateway address. Existing entity IDs and curve options are preserved.

After installing this update, restart Home Assistant completely to stop callbacks left running by the previous version. Separate entries can subsequently be reloaded without closing the connection used by other entries.

## PV Optimization — Logic

- Enable/disable per curve with `switch.r290_heatpump_<prefix>_pv_optimization`.
- Grid rule
  - Interprets PV power in kW (auto-converts W/Wh → kW).
  - Uses `pv_grid_threshold_min_kw` / `pv_grid_threshold_max_kw` together with `pv_grid_offset_min` / `pv_grid_offset_max` to interpolate a linear offset. Below `pv_offset_reset_kw`, the grid offset returns to zero after the configured hold time; between reset and minimum thresholds, the current offset is retained. At/above the maximum threshold, the maximum offset applies.
- Battery rule
  - Applies `pv_battery_offset` when SoC ≤ `pv_battery_threshold_pct`.
- If both rules match, the offset with the largest absolute value is selected.
- Offset hold time (configured via `pv_hold_minutes`) prevents rapid switching: a change of offset requires that the configured duration has elapsed since the last change.
- External offset commands respect `external_offset_hold_minutes` before a change is committed.
- The base curve is bounded by `[t_flow_min, t_flow_max]`; PV and external offsets are applied afterwards and can move the final target outside those base limits.

Entity naming uses the curve prefixes `heating`, `floor_heating`, `hotwater`, `cooling`, e.g.:

- `switch.r290_heatpump_heating_pv_optimization`
- `select.r290_heatpump_heating_pv_grid_offset_min`
- `select.r290_heatpump_heating_pv_grid_offset_max`
- `select.r290_heatpump_heating_pv_battery_offset`
- `number.r290_heatpump_heating_pv_grid_threshold_min_kw`
- `number.r290_heatpump_heating_pv_grid_threshold_max_kw`
- `number.r290_heatpump_heating_pv_battery_threshold_pct`
- `number.r290_heatpump_heating_pv_hold_minutes`
- `number.r290_heatpump_heating_external_offset_hold_minutes`

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
- Run the connection and lifecycle regression tests with `python -m unittest discover -s tests -v`. They exercise the integration code with Home Assistant and Modbus client doubles, without accessing hardware. They do not replace a test in Home Assistant with the actual gateway.

## Open Topics

- Dashboard optimization [open]
- Integrating L-Parameter [open]
- Optional split COP: hot water vs heating [implemented; field validation ongoing]
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

---

Contributions and issue reports are welcome. Please describe your setup (bridge mode, firmware, HA version) when reporting issues.

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

