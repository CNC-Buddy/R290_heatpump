# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import logging
import math
import asyncio
from collections import deque
from datetime import timedelta
from typing import Optional, Deque, Tuple
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, STATE_ON, CONF_SLAVE
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.core import HomeAssistant

from .pv_optimization import PV_CURVE_CONFIG

_LOGGER = logging.getLogger(__name__)


class R290HeatPumpTemperatureCurveSensor(SensorEntity):
    """Linear temperature curve based on number helpers and an outdoor sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry,
        device_info,
        hub,
        modbus_address: int | None = None,
        custom_entity_id: str | None = None,
        display_name: str | None = None,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._outdoor_sensor = entry.data["outdoor_sensor"]
        self._modbus_address = int(modbus_address) if modbus_address is not None else 0x0301
        self._slave_id = 1
        self._hub = hub
        self._state: int | None = None
        # Exponential moving average inertia and step-size tracking
        self._last_cmd: Optional[float] = None
        self._last_ts: Optional[float] = None
        self._last_written: Optional[float] = None

        self._attr_unique_id = custom_entity_id or "r290_heatpump_temperature_curve_now"
        self._attr_name = display_name or "Temperature Curve Now"
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = "measurement"
        self._attr_should_poll = True
        self.entity_id = custom_entity_id or "sensor.r290_heatpump_temperature_curve_now"

        self._defaults = {
            "t_out_min": -15.0,
            "t_out_max": 20.0,
            "t_flow_min": 25.0,
            "t_flow_max": 50.0,
        }

        curve_cfg = PV_CURVE_CONFIG.get(self._entry.data.get("device_type"), {})
        self._curve_prefix = curve_cfg.get("prefix", "heating")
        self._pv_defaults = curve_cfg
        self._pv_current_offset = 0.0
        self._pv_preview_offset = 0.0
        self._pv_last_change: Optional[float] = None
        self._pv_pending_offset: Optional[float] = None
        self._pv_last_candidate: Optional[float] = None
        self._pv_candidate_since: Optional[float] = None
        self._pv_hold_remaining: float = 0.0
        self._pv_hold_handle: Optional[asyncio.TimerHandle] = None
        self._pv_power_history: Deque[Tuple[float, float]] = deque()
        self._pv_last_power_avg: float = 0.0
        self._pv_power_sensor: Optional[str] = None
        self._pv_battery_sensor: Optional[str] = None
        self._pv_power_listener = None
        self._pv_battery_listener = None
        self._pv_callback = None
        self._external_offset_active = 0.0
        self._external_offset_preview = 0.0
        self._external_offset_enabled = False
        self._external_offset_source: str | None = None
        self._external_current_offset = 0.0
        self._external_pending_offset: Optional[float] = None
        self._external_last_candidate: Optional[float] = None
        self._external_candidate_since: Optional[float] = None
        self._external_hold_remaining: float = 0.0
        self._external_hold_handle: Optional[asyncio.TimerHandle] = None
        self._external_number_id = f"number.r290_heatpump_{self._curve_prefix}_external_heating_offset"
        self._external_switch_ids = [
            f"switch.r290_heatpump_{self._curve_prefix}_external_heating_offset",
        ]
        self._last_written_offsets = (0.0, 0.0)
        self._post_write_handle: Optional[asyncio.TimerHandle] = None
        slave_id = int(self._entry.data.get(CONF_SLAVE, 1))
        set_temp_suffix_map = {
            "heating": "heating",
            "floor_heating": "floor_heating",
            "hotwater": "hot_water",
            "cooling": "cooling",
        }
        suffix = set_temp_suffix_map.get(self._curve_prefix, "heating")
        self._set_temp_entity_id = f"number.r290_heatpump_{suffix}_set_temperature_slave_{slave_id}"

    @property
    def state(self):
        return self._state

    def _num(self, key: str) -> float:
        val = self._entry.options.get(key)
        if val is None:
            return float(self._defaults.get(key, 0.0))
        try:
            return float(val)
        except Exception:
            return float(self._defaults.get(key, 0.0))

    def _calc(self, t_out: float, tmin: float, tmax: float, fmin: float, fmax: float) -> int:
        if t_out <= tmin:
            return int(round(fmax))
        if t_out >= tmax:
            return int(round(fmin))
        denom = (tmin - tmax)
        if denom == 0:
            return int(round(fmin))
        val = fmin + ((fmax - fmin) / denom) * (t_out - tmax)
        return int(round(val))

    def _calc_float(self, t_out: float, tmin: float, tmax: float, fmin: float, fmax: float) -> float:
        if t_out <= tmin:
            return float(fmax)
        if t_out >= tmax:
            return float(fmin)
        denom = (tmin - tmax)
        if denom == 0:
            return float(fmin)
        val = fmin + ((fmax - fmin) / denom) * (t_out - tmax)
        return float(val)

    def _apply_inertia(self, raw: float) -> float:
        try:
            inertia = float(self._entry.options.get("inertia_hours", 0.0))
        except Exception:
            inertia = 0.0
        inertia = max(0.0, min(24.0, inertia))
        now = asyncio.get_running_loop().time()
        if inertia <= 0.0:
            self._last_cmd = float(raw)
            self._last_ts = now
            return float(raw)
        prev = self._last_cmd if self._last_cmd is not None else float(raw)
        prev_ts = self._last_ts
        dt = 0.0
        if isinstance(prev_ts, (int, float)) and prev_ts is not None:
            dt = max(0.0, float(now - prev_ts))
        tau = inertia * 3600.0
        alpha = 1.0 - math.exp(-dt / tau) if dt > 0 else 0.0
        cmd = float(prev + alpha * (float(raw) - prev))
        self._last_cmd = cmd
        self._last_ts = now
        return cmd

    def _pv_control_entity_ids(self, prefix: str) -> list[str]:
        return [
            f"switch.r290_heatpump_{prefix}_pv_optimization",
            f"select.r290_heatpump_{prefix}_pv_grid_offset_min",
            f"select.r290_heatpump_{prefix}_pv_grid_offset_max",
            f"select.r290_heatpump_{prefix}_pv_battery_offset",
            f"number.r290_heatpump_{prefix}_pv_grid_threshold_min_kw",
            f"number.r290_heatpump_{prefix}_pv_grid_threshold_max_kw",
            f"number.r290_heatpump_{prefix}_pv_battery_threshold_pct",
            f"number.r290_heatpump_{prefix}_pv_hold_minutes",
            f"number.r290_heatpump_{prefix}_external_offset_hold_minutes",
        ]

    def _ensure_pv_sensor_listeners(self, callback) -> None:
        power_sensor = self._entry.options.get("pv_power_sensor")
        if power_sensor != self._pv_power_sensor:
            if self._pv_power_listener is not None:
                self._pv_power_listener()
                self._pv_power_listener = None
            self._pv_power_sensor = power_sensor
            if power_sensor:
                self._pv_power_listener = async_track_state_change_event(
                    self._hass, [power_sensor], callback
                )

        battery_sensor = self._entry.options.get("pv_battery_sensor")
        if battery_sensor != self._pv_battery_sensor:
            if self._pv_battery_listener is not None:
                self._pv_battery_listener()
                self._pv_battery_listener = None
            self._pv_battery_sensor = battery_sensor
            if battery_sensor:
                self._pv_battery_listener = async_track_state_change_event(
                    self._hass, [battery_sensor], callback
                )

    def _cancel_pv_hold_timer(self) -> None:
        if self._pv_hold_handle is not None:
            try:
                self._pv_hold_handle.cancel()
            except Exception:
                pass
            finally:
                self._pv_hold_handle = None

    def _schedule_pv_hold_timer(self, delay: float) -> None:
        if delay <= 0.0 or self._pv_callback is None:
            return
        self._cancel_pv_hold_timer()
        loop = asyncio.get_running_loop()

        def _fire():
            self._pv_hold_handle = None
            try:
                if self._pv_callback is not None:
                    self._hass.async_create_task(self._pv_callback())
            except Exception as err:
                _LOGGER.debug("PV hold timer callback failed: %s", err)

        try:
            self._pv_hold_handle = loop.call_later(max(0.0, delay), _fire)
        except Exception as err:
            _LOGGER.debug("Unable to schedule PV hold timer: %s", err)

    def _compute_pv_offset(
        self,
        base_cmd: float,
        fmin: float,
        fmax: float,
        *,
        commit: bool = True,
    ) -> float:
        opts = self._entry.options
        enabled = opts.get("pv_enabled", self._entry.data.get("pv_enabled", False))
        if not bool(enabled):
            if self._pv_current_offset != 0.0:
                self._pv_current_offset = 0.0
            if commit:
                self._pv_last_change = None
                self._pv_last_candidate = None
                self._pv_candidate_since = None
                self._pv_pending_offset = None
                self._pv_hold_remaining = 0.0
                self._cancel_pv_hold_timer()
            self._pv_power_history.clear()
            self._pv_last_power_avg = 0.0
            return 0.0

        grid_candidate: Optional[float] = None
        battery_candidates: list[float] = []

        power_sensor = opts.get("pv_power_sensor") or self._entry.data.get("pv_power_sensor")
        if power_sensor:
            sensor = self._hass.states.get(power_sensor)
            if sensor and sensor.state not in (None, "unknown", "unavailable"):
                try:
                    power_val = float(sensor.state)
                    unit = (sensor.attributes.get("unit_of_measurement") or "").lower()
                    if unit == "w" or unit == "wh":
                        power_kw = power_val / 1000.0
                    else:
                        power_kw = power_val
                    avg_power_kw = self._average_recent_power(power_kw, record=commit)
                    threshold_min = float(
                        opts.get(
                            "pv_grid_threshold_min_kw",
                            opts.get(
                                "pv_grid_threshold_kw",
                                self._pv_defaults.get(
                                    "grid_threshold_min_default",
                                    self._pv_defaults.get("grid_threshold_default", 2.0),
                                ),
                            ),
                        )
                    )
                    threshold_max = float(
                        opts.get(
                            "pv_grid_threshold_max_kw",
                            opts.get(
                                "pv_grid_threshold_kw",
                                self._pv_defaults.get(
                                    "grid_threshold_max_default",
                                    self._pv_defaults.get("grid_threshold_default", threshold_min),
                                ),
                            ),
                        )
                    )
                    if threshold_max < threshold_min:
                        threshold_min, threshold_max = threshold_max, threshold_min
                    offset_min = float(
                        opts.get(
                            "pv_grid_offset_min",
                            opts.get(
                                "pv_grid_offset",
                                self._pv_defaults.get("grid_offset_min_default", 0.0),
                            ),
                        )
                    )
                    offset_max = float(
                        opts.get(
                            "pv_grid_offset_max",
                            opts.get(
                                "pv_grid_offset",
                                self._pv_defaults.get("grid_offset_max_default", offset_min),
                            ),
                        )
                    )
                    offset_min = max(-10.0, min(10.0, offset_min))
                    offset_max = max(-10.0, min(10.0, offset_max))
                    if avg_power_kw <= 0.25:
                        grid_candidate = 0.0
                    elif avg_power_kw < threshold_min:
                        grid_candidate = self._pv_current_offset
                    elif math.isclose(threshold_max, threshold_min, abs_tol=1e-6):
                        grid_candidate = offset_max
                    elif avg_power_kw >= threshold_max:
                        grid_candidate = offset_max
                    else:
                        span = threshold_max - threshold_min
                        ratio = (avg_power_kw - threshold_min) / span
                        grid_candidate = offset_min + ratio * (offset_max - offset_min)
                    if grid_candidate is not None:
                        grid_candidate = float(max(-10.0, min(10.0, grid_candidate)))
                except (ValueError, TypeError):
                    pass
        else:
            self._pv_power_history.clear()
            self._pv_last_power_avg = 0.0

        battery_sensor = opts.get("pv_battery_sensor") or self._entry.data.get("pv_battery_sensor")
        if battery_sensor:
            sensor = self._hass.states.get(battery_sensor)
            if sensor and sensor.state not in (None, "unknown", "unavailable"):
                try:
                    battery_val = float(sensor.state)
                    threshold_pct = float(
                        opts.get(
                            "pv_battery_threshold_pct",
                            self._pv_defaults.get("battery_threshold_default", 80.0),
                        )
                    )
                    offset = int(float(opts.get("pv_battery_offset", 0)))
                    # Battery rule: apply when battery is at or below the threshold
                    if battery_val <= threshold_pct:
                        battery_candidates.append(float(max(-10.0, min(10.0, offset))))
                except (ValueError, TypeError):
                    pass

        candidates: list[float] = []
        if grid_candidate is not None:
            candidates.append(grid_candidate)
        candidates.extend(battery_candidates)
        candidate = 0.0
        if candidates:
            candidate = float(max(candidates, key=lambda val: abs(val)))
        candidate = max(-10.0, min(10.0, candidate))
        self._pv_preview_offset = candidate

        if not commit:
            return candidate

        now = asyncio.get_running_loop().time()
        hold_minutes = float(
            opts.get(
                "pv_hold_minutes",
                opts.get(
                    "pv_cooldown_minutes",
                    self._pv_defaults.get("hold_default", 15),
                ),
            )
        )
        hold_seconds = max(0.0, hold_minutes) * 60.0

        if self._pv_last_candidate != candidate:
            self._pv_last_candidate = candidate
            self._pv_candidate_since = now
        if self._pv_candidate_since is None:
            self._pv_candidate_since = now

        if math.isclose(candidate, self._pv_current_offset, abs_tol=0.01):
            if self._pv_pending_offset is not None:
                self._pv_pending_offset = None
            self._pv_hold_remaining = 0.0
            self._cancel_pv_hold_timer()
            return self._pv_current_offset

        current = self._pv_current_offset
        current_sign = 0.0 if math.isclose(current, 0.0, abs_tol=0.01) else math.copysign(1.0, current)
        candidate_sign = 0.0 if math.isclose(candidate, 0.0, abs_tol=0.01) else math.copysign(1.0, candidate)
        magnitude_increasing = abs(candidate) > abs(current) + 1e-6
        sign_changed = candidate_sign != current_sign and not (candidate_sign == 0.0 and current_sign == 0.0)

        if magnitude_increasing or sign_changed:
            self._pv_current_offset = candidate
            self._pv_last_change = now
            self._pv_pending_offset = None
            self._pv_candidate_since = now
            self._pv_hold_remaining = 0.0
            self._cancel_pv_hold_timer()
            return self._pv_current_offset

        elapsed = max(0.0, now - self._pv_candidate_since)
        remaining = 0.0
        if hold_seconds > 0.0:
            remaining = max(0.0, hold_seconds - elapsed)
        self._pv_hold_remaining = remaining

        if hold_seconds <= 0.0 or remaining <= 0.0:
            self._pv_current_offset = candidate
            self._pv_last_change = now
            self._pv_pending_offset = None
            self._pv_candidate_since = now
            self._pv_hold_remaining = 0.0
            self._cancel_pv_hold_timer()
            return self._pv_current_offset

        self._pv_pending_offset = candidate
        self._schedule_pv_hold_timer(remaining)
        return self._pv_current_offset

    def _cancel_external_hold_timer(self) -> None:
        if self._external_hold_handle is not None:
            try:
                self._external_hold_handle.cancel()
            except Exception:
                pass
            finally:
                self._external_hold_handle = None

    def _schedule_external_hold_timer(self, delay: float) -> None:
        if delay <= 0.0 or self._pv_callback is None:
            return
        self._cancel_external_hold_timer()
        loop = asyncio.get_running_loop()

        def _fire():
            self._external_hold_handle = None
            try:
                if self._pv_callback is not None:
                    self._hass.async_create_task(self._pv_callback())
            except Exception as err:
                _LOGGER.debug("External offset hold timer callback failed: %s", err)

        try:
            self._external_hold_handle = loop.call_later(max(0.0, delay), _fire)
        except Exception as err:
            _LOGGER.debug("Unable to schedule external offset hold timer: %s", err)

    def _cancel_post_write_timer(self) -> None:
        if self._post_write_handle is not None:
            try:
                self._post_write_handle.cancel()
            except Exception:
                pass
            finally:
                self._post_write_handle = None

    def _schedule_post_write_timer(self, delay: float, callback) -> None:
        if delay <= 0.0 or callback is None:
            return
        self._cancel_post_write_timer()
        loop = asyncio.get_running_loop()

        def _fire():
            self._post_write_handle = None
            try:
                self._hass.async_create_task(callback())
            except Exception as err:
                _LOGGER.debug("Post-write timer callback failed: %s", err)

        try:
            self._post_write_handle = loop.call_later(delay, _fire)
        except Exception as err:
            _LOGGER.debug("Unable to schedule post-write timer: %s", err)

    def _compute_external_offset(self, *, commit: bool) -> float:
        switch_on = False
        active_source: str | None = None
        for entity_id in self._external_switch_ids:
            state = self._hass.states.get(entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                if str(state.state).lower() == STATE_ON:
                    switch_on = True
                    active_source = entity_id
                    break

        self._external_offset_enabled = switch_on
        self._external_offset_source = active_source

        candidate = 0.0
        if switch_on:
            number_state = self._hass.states.get(self._external_number_id)
            if number_state and number_state.state not in (None, "unknown", "unavailable"):
                try:
                    candidate = float(number_state.state)
                except (TypeError, ValueError):
                    candidate = 0.0
        candidate = float(max(-10.0, min(10.0, candidate)))
        self._external_offset_preview = candidate

        if not commit:
            return candidate

        now = asyncio.get_running_loop().time()
        opts = self._entry.options
        hold_minutes = float(
            opts.get(
                "external_offset_hold_minutes",
                self._pv_defaults.get("external_hold_default", 5.0),
            )
        )
        hold_seconds = max(0.0, hold_minutes) * 60.0

        if self._external_last_candidate != candidate:
            self._external_last_candidate = candidate
            self._external_candidate_since = now
        if self._external_candidate_since is None:
            self._external_candidate_since = now

        if math.isclose(candidate, self._external_current_offset, abs_tol=0.01):
            if self._external_pending_offset is not None:
                self._external_pending_offset = None
            self._external_hold_remaining = 0.0
            self._cancel_external_hold_timer()
            return self._external_current_offset

        elapsed = max(0.0, now - self._external_candidate_since)
        remaining = 0.0
        if hold_seconds > 0.0:
            remaining = max(0.0, hold_seconds - elapsed)
        self._external_hold_remaining = remaining

        if hold_seconds <= 0.0 or remaining <= 0.0:
            self._external_current_offset = candidate
            self._external_candidate_since = now
            self._external_pending_offset = None
            self._external_hold_remaining = 0.0
            self._cancel_external_hold_timer()
            return self._external_current_offset

        self._external_pending_offset = candidate
        self._schedule_external_hold_timer(remaining)
        return self._external_current_offset

    @property
    def extra_state_attributes(self):
        try:
            tmin = self._num("t_out_min")
            tmax = self._num("t_out_max")
            fmin = self._num("t_flow_min")
            fmax = self._num("t_flow_max")
            points = list(range(-15, 31, 5))
            table: dict[str, int] = {}
            for idx, t in enumerate(points, start=1):
                key = f"point{idx:02d}_{t}C"
                table[key] = int(self._calc(float(t), tmin, tmax, fmin, fmax))
            now_val = None
            try:
                out_state = self._hass.states.get(self._outdoor_sensor)
                if out_state and out_state.state not in (None, "unknown", "unavailable"):
                    # Show current (smoothed) target value
                    raw = self._calc_float(float(out_state.state), tmin, tmax, fmin, fmax)
                    cmd = self._apply_inertia(raw)
                    now_val = int(round(cmd))
            except Exception:
                pass
            attrs = {"Kurve": table, "now": now_val}
            attrs["pv_offset"] = round(self._pv_current_offset, 2)
            attrs["pv_offset_preview"] = round(self._pv_preview_offset, 2)
            attrs["pv_enabled"] = bool(self._entry.options.get("pv_enabled", False))
            attrs["pv_offset_pending"] = (
                round(self._pv_pending_offset, 2)
                if self._pv_pending_offset is not None
                else None
            )
            attrs["pv_offset_hold_remaining_seconds"] = int(round(self._pv_hold_remaining))
            attrs["pv_power_avg_kw"] = round(self._pv_last_power_avg, 3)
            attrs["external_offset"] = round(self._external_offset_active, 2)
            attrs["external_offset_preview"] = round(self._external_offset_preview, 2)
            attrs["external_offset_enabled"] = bool(self._external_offset_enabled)
            attrs["external_offset_source"] = self._external_offset_source
            attrs["external_offset_pending"] = (
                round(self._external_pending_offset, 2)
                if self._external_pending_offset is not None
                else None
            )
            attrs["external_offset_hold_remaining_seconds"] = int(
                round(self._external_hold_remaining)
            )
            return attrs
        except Exception:
            return None

    async def async_added_to_hass(self):
        async def _maybe_write_target(_evt=None):
            try:
                if not bool(self._entry.options.get("heatcurve_active", False)):
                    return
                self._ensure_pv_sensor_listeners(_maybe_write_target)
                out_state = self._hass.states.get(self._outdoor_sensor)
                if not out_state or out_state.state in (None, "unknown", "unavailable"):
                    return
                t_out = float(out_state.state)
                tmin = self._num("t_out_min")
                tmax = self._num("t_out_max")
                fmin = self._num("t_flow_min")
                fmax = self._num("t_flow_max")
                raw = self._calc_float(t_out, tmin, tmax, fmin, fmax)
                cmd = self._apply_inertia(raw)
                pv_offset = self._compute_pv_offset(cmd, fmin, fmax, commit=True)
                external_offset = self._compute_external_offset(commit=True)
                self._external_offset_active = external_offset
                final_cmd = cmd + pv_offset + external_offset
                rounded_final = int(round(final_cmd))
                rounded_last = (
                    int(round(self._last_written)) if self._last_written is not None else None
                )
                write_needed = False
                if self._last_written is None:
                    write_needed = True
                else:
                    last_pv, last_external = self._last_written_offsets
                    offsets_changed = (
                        round(float(pv_offset), 3) != round(float(last_pv), 3)
                        or round(float(external_offset), 3) != round(float(last_external), 3)
                    )
                    value_changed = not math.isclose(
                        float(final_cmd), float(self._last_written), abs_tol=0.05
                    )
                    rounded_changed = rounded_last != rounded_final
                    write_needed = offsets_changed or value_changed or rounded_changed
                if not write_needed:
                    self._state = rounded_final
                    return
                await self._hub.async_pb_write_register(
                    self._slave_id, self._modbus_address, int(round(final_cmd)), "holding"
                )
                self._last_written = float(final_cmd)
                self._last_written_offsets = (float(pv_offset), float(external_offset))
                self._state = rounded_final
                self._schedule_post_write_timer(60.0, _maybe_write_target)
                if self._set_temp_entity_id:
                    self._hass.async_create_task(
                        self._hass.services.async_call(
                            "homeassistant",
                            "update_entity",
                            {"entity_id": self._set_temp_entity_id},
                        )
                    )
            except Exception as e:
                _LOGGER.debug("Temperature curve immediate write failed: %s", e)

        if self._outdoor_sensor:
            async_track_state_change_event(
                self._hass,
                [self._outdoor_sensor],
                _maybe_write_target,
            )
        # Update on helper number changes (per curve type)
        curve_prefix = {
            "heating_curve": "heating",
            "floor_heating_curve": "floor_heating",
            "hot_water_curve": "hotwater",
            "cooling_curve": "cooling",
        }.get(self._entry.data.get("device_type"), "heating")
        curve_number_suffixes = (
            "t_out_min",
            "t_out_max",
            "t_flow_min",
            "t_flow_max",
            "inertia_hours",
            "stepsize_c",
        )
        for name in curve_number_suffixes:
            ent_id = f"number.r290_heatpump_{curve_prefix}_{name}"
            async_track_state_change_event(self._hass, [ent_id], _maybe_write_target)

        for ent_id in self._pv_control_entity_ids(curve_prefix):
            async_track_state_change_event(self._hass, [ent_id], _maybe_write_target)

        external_entities = set(self._external_switch_ids + [self._external_number_id])
        for ent_id in external_entities:
            async_track_state_change_event(self._hass, [ent_id], _maybe_write_target)

        # React to switch toggles as well
        try:
            sw_id = f"switch.r290_heatpump_{curve_prefix}_curve_active"
            async_track_state_change_event(self._hass, [sw_id], _maybe_write_target)
        except Exception:
            pass

        self._pv_callback = _maybe_write_target
        self._ensure_pv_sensor_listeners(_maybe_write_target)

        # Periodic write on long interval if enabled
        try:
            long_iv = int(
                self._entry.options.get(
                    "long_scan_interval", self._entry.data.get("long_scan_interval", 300)
                )
            )
        except Exception:
            long_iv = 300

        async def _periodic_write(_now=None):
            await _maybe_write_target()

        async_track_time_interval(
            self._hass, _periodic_write, timedelta(seconds=long_iv)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._pv_power_listener is not None:
            self._pv_power_listener()
            self._pv_power_listener = None
        if self._pv_battery_listener is not None:
            self._pv_battery_listener()
            self._pv_battery_listener = None
        self._cancel_pv_hold_timer()
        self._cancel_external_hold_timer()
        self._cancel_post_write_timer()
        await super().async_will_remove_from_hass()

    async def async_update(self):
        try:
            out = self._hass.states.get(self._outdoor_sensor)
            if not out or out.state in (None, "unknown", "unavailable"):
                self._state = None
                return
            t_out = float(out.state)
            tmin = self._num("t_out_min")
            tmax = self._num("t_out_max")
            fmin = self._num("t_flow_min")
            fmax = self._num("t_flow_max")
            raw = self._calc_float(t_out, tmin, tmax, fmin, fmax)
            cmd = self._apply_inertia(raw)
            pv_offset = self._compute_pv_offset(cmd, fmin, fmax, commit=False)
            self._compute_external_offset(commit=False)
            self._external_offset_active = self._external_current_offset
            final_cmd = cmd + pv_offset + self._external_offset_active
            self._state = int(round(final_cmd))
        except Exception as e:
            _LOGGER.debug("Error in temperature curve update: %s", e)
            self._state = None


    def _average_recent_power(self, sample_kw: float | None, *, record: bool) -> float:
        hist = self._pv_power_history
        now = asyncio.get_running_loop().time()
        cutoff = now - 60.0
        while hist and hist[0][0] < cutoff:
            hist.popleft()

        data = list(hist)
        if sample_kw is not None:
            sample = float(sample_kw)
            if record:
                hist.append((now, sample))
                data = list(hist)
            else:
                data = data + [(now, sample)] if data else [(now, sample)]

        if data:
            avg = sum(val for _, val in data) / len(data)
        else:
            avg = float(sample_kw) if sample_kw is not None else 0.0
        self._pv_last_power_avg = avg
        return avg





