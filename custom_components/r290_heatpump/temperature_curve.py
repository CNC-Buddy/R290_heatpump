import logging
import math
import asyncio
from datetime import timedelta
from typing import Optional
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTemperature
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
        # Exponential moving average inertia and deadband tracking
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
        self._pv_power_sensor: Optional[str] = None
        self._pv_battery_sensor: Optional[str] = None
        self._pv_power_listener = None
        self._pv_battery_listener = None
        self._pv_callback = None

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
            f"select.r290_heatpump_{prefix}_pv_grid_offset",
            f"select.r290_heatpump_{prefix}_pv_battery_offset",
            f"number.r290_heatpump_{prefix}_pv_grid_threshold_kw",
            f"number.r290_heatpump_{prefix}_pv_battery_threshold_pct",
            f"number.r290_heatpump_{prefix}_pv_cooldown_minutes",
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
            return 0.0

        offsets = []

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
                    threshold = float(
                        opts.get(
                            "pv_grid_threshold_kw",
                            self._pv_defaults.get("grid_threshold_default", 2.0),
                        )
                    )
                    offset = int(float(opts.get("pv_grid_offset", 0)))
                    if power_kw >= threshold:
                        offsets.append(offset)
                except (ValueError, TypeError):
                    pass

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
                        offsets.append(offset)
                except (ValueError, TypeError):
                    pass

        candidate = 0.0
        if offsets:
            candidate = float(max(offsets, key=lambda val: abs(val)))
        candidate = max(-10.0, min(10.0, candidate))

        if not commit:
            return candidate

        now = asyncio.get_running_loop().time()
        cooldown_minutes = float(
            opts.get("pv_cooldown_minutes", self._pv_defaults.get("cooldown_default", 15))
        )
        cooldown_seconds = max(0.0, cooldown_minutes) * 60.0

        if self._pv_last_change is None:
            self._pv_last_change = now
            self._pv_current_offset = candidate
            return candidate

        if candidate != self._pv_current_offset:
            if cooldown_seconds > 0 and (now - self._pv_last_change) < cooldown_seconds:
                return self._pv_current_offset
            self._pv_last_change = now
            self._pv_current_offset = candidate

        return self._pv_current_offset

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
            attrs["pv_offset"] = int(round(self._pv_current_offset))
            attrs["pv_offset_preview"] = int(round(self._pv_preview_offset))
            attrs["pv_enabled"] = bool(self._entry.options.get("pv_enabled", False))
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
                final_cmd = cmd + pv_offset
                final_cmd = max(float(fmin), min(float(fmax), final_cmd))
                self._pv_preview_offset = pv_offset
                try:
                    deadband = float(self._entry.options.get("deadband_c", 0.5))
                except Exception:
                    deadband = 0.5
                deadband = max(0.0, min(2.0, deadband))
                should_write = False
                if self._last_written is None:
                    should_write = True
                else:
                    should_write = (
                        abs(float(final_cmd) - float(self._last_written)) >= float(deadband)
                    )
                if not should_write:
                    self._state = int(round(final_cmd))
                    return
                await self._hub.async_pb_write_register(
                    self._slave_id, self._modbus_address, int(round(final_cmd)), "holding"
                )
                self._last_written = float(final_cmd)
                self._state = int(round(final_cmd))
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
        for name in ("t_out_min", "t_out_max", "t_flow_min", "t_flow_max", "inertia_hours", "deadband_c"):
            ent_id = f"number.r290_heatpump_{curve_prefix}_{name}"
            async_track_state_change_event(self._hass, [ent_id], _maybe_write_target)

        for ent_id in self._pv_control_entity_ids(curve_prefix):
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
                    "long_scan_interval", self._entry.data.get("long_scan_interval", 600)
                )
            )
        except Exception:
            long_iv = 600

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
            self._pv_preview_offset = pv_offset
            final_cmd = cmd + pv_offset
            final_cmd = max(float(fmin), min(float(fmax), final_cmd))
            self._state = int(round(final_cmd))
        except Exception as e:
            _LOGGER.debug("Error in temperature curve update: %s", e)
            self._state = None





