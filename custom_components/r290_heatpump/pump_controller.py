"""Entity-based pump controller, independent of browser lifetime and Modbus I/O."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import math
import time

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store

from .pump_config import CONTROL_FIELDS, validate_config
from .pump_logic import MODES, PumpLogic, Snapshot, UnitReading


class PumpController:
    """Explicitly armed control survives reload; new entries remain observers."""

    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.config = validate_config(hass, {**entry.data, **entry.options}, exclude_entry=entry.entry_id)
        self.logic = PumpLogic(self.config)
        self.mode = "observe"
        self._resume_mode = None
        self.decision = None
        self.last_command = None
        self._requested_speed = None
        self.last_command_at = None
        self.error = None
        self._stopped = False
        self._lock = asyncio.Lock()
        self._task = None
        self._pending = False
        self._unsubs = []
        self._listeners = set()
        self._last_write_time = -math.inf
        self._feedback_since = None
        self._records = deque(maxlen=250)
        self._store = Store(hass, 1, f"r290_heatpump.pump.{entry.entry_id}")

    async def async_start(self):
        saved = await self._store.async_load()
        if isinstance(saved, dict):
            self._records.extend(saved.get("records", [])[-250:])
            resume = saved.get("resume")
            resume = resume if isinstance(resume, dict) else {}
            if (self.config["commissioned"] and resume.get("binding") == self._binding()
                    and resume.get("mode") in ("auto", "manual")):
                speed = resume.get("manual_speed", self.config["manual_speed"])
                if isinstance(speed, (int, float)) and math.isfinite(speed) and self.config["min_speed"] <= speed <= self.config["max_speed"]:
                    self.config["manual_speed"] = speed
                    self.logic = PumpLogic(self.config)
                    self._resume_mode = resume["mode"]
        ids = set()
        for key in CONTROL_FIELDS:
            value = self.config.get(key)
            ids.update(value if isinstance(value, list) else [value] if value else [])
        self._unsubs.append(async_track_state_change_event(self.hass, list(ids), self._schedule))
        self._unsubs.append(async_track_time_interval(self.hass, self._schedule, timedelta(seconds=10)))
        self._record("lifecycle", "waiting_to_resume" if self._resume_mode else "started_in_observe")
        await self.async_evaluate()

    def _binding(self):
        """Never transfer saved authority to another actuator or source mapping."""
        return {key: self.config.get(key) for key in (*sorted(CONTROL_FIELDS), "output_min", "output_max", "commissioned")}

    def _storage_state(self):
        mode = self._resume_mode or self.mode
        resume = {"mode": mode, "binding": self._binding(), "manual_speed": self.config["manual_speed"]} if mode in ("auto", "manual") and not self.error else None
        return {"records": list(self._records), "resume": resume}

    @callback
    def _schedule(self, _event=None):
        if self._stopped:
            return
        self._pending = True
        if self._task is None or self._task.done():
            self._task = self.hass.async_create_task(self._drain())

    async def _drain(self):
        while self._pending and not self._stopped:
            self._pending = False
            await self.async_evaluate()

    def _record(self, kind, reason, **data):
        self._records.append({"at": datetime.now(timezone.utc).isoformat(), "kind": kind,
                              "reason": reason, "mode": self.mode, **data})
        self._store.async_delay_save(self._storage_state, 10)

    @callback
    def async_add_listener(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _publish(self):
        for listener in tuple(self._listeners):
            listener()

    def _state(self, entity_id):
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in ("unknown", "unavailable", "None", "") or state.attributes.get("restored"):
            return None
        return state

    def _boolean(self, entity_id):
        state = self._state(entity_id)
        if state is None:
            return None
        # Sensor bit entities in this integration also use on/off. Never treat
        # an unknown enum, e.g. a general operating-mode register, as false.
        value = str(state.state).lower()
        return True if value in ("on", "true", "1") else False if value in ("off", "false", "0") else None

    def _numeric(self, entity_id, quantity):
        state = self._state(entity_id)
        if state is None:
            return None
        # last_changed cannot detect communication loss for an unchanged value.
        stamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
        if stamp is None or (datetime.now(timezone.utc) - stamp).total_seconds() > self.config["max_age"]:
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        unit = state.attributes.get("unit_of_measurement", "")
        if quantity == "temperature":
            if unit == "°F":
                value = (value - 32) / 1.8
            elif unit not in ("°C", "C"):
                return None
            return value if -30 <= value <= 100 else None
        if quantity == "flow":
            if unit in ("m³/h", "m3/h"):
                value *= 1000 / 60
            elif unit in ("L/h", "l/h"):
                value /= 60
            elif unit not in ("L/min", "l/min", "l/m", "L/m"):
                return None
            return value if 0 <= value <= 1000 else None
        if quantity == "frequency":
            return value if unit == "Hz" and 0 <= value <= 200 else None
        return value

    def _any_boolean(self, entity_ids):
        """An active unit wins; off requires valid off from every source."""
        values = [self._boolean(entity_id) for entity_id in entity_ids]
        if True in values:
            return True
        return None if not values or None in values else False

    def actual_speed(self):
        state = self._state(self.config["speed_entity"])
        if state is None:
            return None
        enabled = self._boolean(self.config.get("enable_entity")) if self.config.get("enable_entity") else True
        if enabled is False or state.state == "off":
            return 0.0
        if enabled is None:
            return None
        try:
            domain = state.entity_id.split(".")[0]
            if domain == "light":
                value = float(state.attributes["brightness"]) / 255 * 100
            elif domain == "fan":
                value = float(state.attributes["percentage"])
            else:
                value = (float(state.state) - self.config["output_min"]) / (self.config["output_max"] - self.config["output_min"]) * 100
            return min(100.0, max(0.0, value)) if math.isfinite(value) else None
        except (KeyError, TypeError, ValueError):
            return None

    def sample(self):
        units = tuple(UnitReading(
            self._numeric(frequency, "frequency"), self._numeric(flow, "flow"),
            self._numeric(supply, "temperature"), self._numeric(ret, "temperature"))
            for frequency, flow, supply, ret in zip(
                self.config["frequency_entities"], self.config["flow_entities"],
                self.config["supply_entities"], self.config["return_entities"]))
        return Snapshot(self._any_boolean(self.config["demand_entity"]),
                        self._boolean(self.config["dhw_entity"]),
                        self._any_boolean(self.config["defrost_entities"]), units, self.actual_speed())

    def _conflicts(self):
        # unavailable automations also block arming; ownership must be known.
        return [e for e in self.config.get("legacy_automations", []) if self._boolean(e) is not False]

    def _plant_problem(self):
        domain = self.hass.data.get("r290_heatpump", {})
        service = domain.get("_service")
        if service and (service.pending or getattr(service, "starting", False)):
            return "Service test or recovery active / Servicetest oder Rücksetzung aktiv"
        plant = domain.get("_panel", {}).get("settings", {}).get("plant")
        if plant and plant.get("controller_id") == self.entry.entry_id:
            from homeassistant.helpers import entity_registry as er
            from .plant import controller_problem, validate_plant
            try:
                validate_plant(plant, {e.entry_id: e for e in self.hass.config_entries.async_entries("r290_heatpump")}, self.hass.states)
            except ValueError as err:
                return str(err)
            return controller_problem(plant, self.config, er.async_get(self.hass))
        return None

    async def async_set_mode(self, mode, manual_speed=None):
        if mode not in MODES:
            raise HomeAssistantError("Invalid pump control mode")
        async with self._lock:
            if self._stopped:
                raise HomeAssistantError("Pump controller unloaded")
            if manual_speed is not None:
                manual_speed = float(manual_speed)
                if mode != "manual" or not math.isfinite(manual_speed) or not self.config["min_speed"] <= manual_speed <= self.config["max_speed"]:
                    raise HomeAssistantError("Manual speed requires manual mode and a value within limits")
            if mode != "observe":
                problem = self._plant_problem()
                if problem:
                    raise HomeAssistantError(problem)
                if not self.config["commissioned"]:
                    raise HomeAssistantError("Confirm hydraulic limits and control ownership in pump options first")
                if self._conflicts():
                    raise HomeAssistantError("Existing pump automations must be disabled before taking control")
                if self._state(self.config["speed_entity"]) is None:
                    raise HomeAssistantError("Pump actuator is unavailable")
                if self.actual_speed() is None:
                    raise HomeAssistantError("Pump output has no valid percentage feedback")
                sample = self.sample()
                if sample.demand is None or sample.dhw is None or sample.defrost is None or any(u.frequency is None for u in sample.units):
                    raise HomeAssistantError("Valid demand, DHW, defrost and compressor signals are required")
                if self.config.get("enable_entity") and self._boolean(self.config["enable_entity"]) is None:
                    raise HomeAssistantError("Pump enable output is unavailable")
            if manual_speed is not None:
                self.config["manual_speed"] = manual_speed
            self.mode, self.error = mode, None
            self._resume_mode = None
            self.logic = PumpLogic(self.config)
            self._last_write_time = -math.inf
            self._feedback_since = None
            self._record("mode", mode)
            await self._store.async_save(self._storage_state())
        await self.async_evaluate()

    async def async_set_manual_speed(self, speed):
        value = float(speed)
        if not math.isfinite(value) or not self.config["min_speed"] <= value <= self.config["max_speed"]:
            raise HomeAssistantError("Manual speed outside configured limits")
        async with self._lock:
            self.config["manual_speed"] = value
            self.logic.settings["manual_speed"] = value
            self._record("manual_target", "manual_target", speed=value)
        await self.async_evaluate()

    async def async_evaluate(self):
        async with self._lock:
            if self._stopped:
                return
            problem = self._plant_problem()
            if problem and (self.mode != "observe" or self._resume_mode):
                self.mode, self._resume_mode, self.error = "observe", None, problem
                self._record("fault", problem)
                await self._store.async_save(self._storage_state())
            now = time.monotonic()
            sample = self.sample()
            if self._resume_mode:
                if self._conflicts():
                    self._resume_mode = None
                    self.error = "automation_conflict"
                    self._record("fault", self.error)
                    await self._store.async_save(self._storage_state())
                elif (sample.actual_speed is not None and
                      (sample.demand is False or (sample.demand is True and sample.dhw is not None
                       and sample.defrost is not None and all(u.frequency is not None for u in sample.units)))):
                    self.mode, self._resume_mode = self._resume_mode, None
                    self._record("lifecycle", "resumed_control")
            previous = self.decision
            self.decision = self.logic.decide(sample, now, self.mode)
            if previous is None or (previous.phase, previous.speed) != (self.decision.phase, self.decision.speed):
                details = asdict(self.decision)
                details.pop("reason")
                self._record("decision", self.decision.reason, **details)
            if self.mode != "observe":
                if self._conflicts():
                    self.mode = "observe"
                    self.error = "automation_conflict"
                    self._record("fault", self.error)
                    await self._store.async_save(self._storage_state())
                elif self.decision.command_allowed:
                    target = self.decision.speed
                    # Commands are repeated only after feedback grace. Safety
                    # increases (defrost/min-flow) can bypass the normal interval.
                    changed = self._requested_speed is None or abs(target - self._requested_speed) >= 0.5
                    feedback_target = target if changed else self.last_command
                    feedback_wrong = sample.actual_speed is None or abs(sample.actual_speed - feedback_target) > 1.5
                    due = now - self._last_write_time >= self.config["interval"]
                    if not changed and feedback_wrong and self._feedback_since is not None and now - self._feedback_since >= max(30, self.config["interval"] * 2):
                        self.mode, self.error = "observe", "actuator_feedback"
                        self._record("fault", self.error)
                        await self._store.async_save(self._storage_state())
                        self._publish()
                        return
                    if not feedback_wrong:
                        self._feedback_since = None
                    if changed or (feedback_wrong and due):
                        try:
                            effective = await self._apply(target)
                            if changed or self._feedback_since is None:
                                self._feedback_since = now
                            self.last_command = effective
                            self._requested_speed = target
                            self.last_command_at = datetime.now(timezone.utc).isoformat()
                            self._last_write_time = now
                            self._record("command", self.decision.reason, speed=effective, requested_speed=target)
                        except Exception as err:
                            # A service timeout may have applied the write. Latch
                            # observer mode rather than retry an ambiguous write.
                            self.mode = "observe"
                            self.error = str(err)
                            self._record("fault", "write_failed", detail=self.error)
                            await self._store.async_save(self._storage_state())
            self._publish()

    async def _apply(self, speed):
        entity_id = self.config["speed_entity"]
        domain = entity_id.split(".")[0]
        enable = self.config.get("enable_entity")

        async def call(domain, service, entity, **values):
            async with asyncio.timeout(15):
                await self.hass.services.async_call(domain, service, {"entity_id": entity, **values}, blocking=True)

        if speed <= 0:
            if enable:
                await call(enable.split(".")[0], "turn_off", enable)
            if domain in ("fan", "light"):
                await call(domain, "turn_off", entity_id)
            return 0.0
        if domain == "number":
            state = self._state(entity_id)
            if state is None:
                raise HomeAssistantError("Pump output unavailable")
            raw = self.config["output_min"] + speed / 100 * (self.config["output_max"] - self.config["output_min"])
            step = float(state.attributes.get("step", 0.1))
            low, high = float(state.attributes["min"]), float(state.attributes["max"])
            if step > 0:
                raw = low + round((raw - low) / step) * step
            if not low <= raw <= high:
                raise HomeAssistantError("Pump output exceeds actuator range")
            await call("number", "set_value", entity_id, value=round(raw, 6))
            effective = (raw - self.config["output_min"]) / (self.config["output_max"] - self.config["output_min"]) * 100
        elif domain == "light":
            await call("light", "turn_on", entity_id, brightness_pct=round(speed))
            effective = round(speed)
        else:
            await call("fan", "set_percentage", entity_id, percentage=round(speed))
            effective = round(speed)
        if enable:
            await call(enable.split(".")[0], "turn_on", enable)
        return round(effective, 3)

    def diagnostics(self):
        inputs = []
        quantities = {"frequency_entities": "frequency", "flow_entities": "flow",
                      "supply_entities": "temperature", "return_entities": "temperature"}
        for key in ("demand_entity", "dhw_entity", "defrost_entities", *quantities):
            value = self.config.get(key)
            for entity_id in value if isinstance(value, list) else [value] if value else []:
                state = self.hass.states.get(entity_id)
                stamp = (getattr(state, "last_reported", None) or getattr(state, "last_updated", None)) if state else None
                inputs.append({"role": key, "entity_id": entity_id,
                    "state": state.state if state else None,
                    "unit": state.attributes.get("unit_of_measurement") if state else None,
                    "age_seconds": max(0, (datetime.now(timezone.utc) - stamp).total_seconds()) if stamp else None,
                    "valid": self._numeric(entity_id, quantities[key]) is not None if key in quantities else self._boolean(entity_id) is not None,
                    "age_checked": key in quantities})
        return {"entry_id": self.entry.entry_id, "name": self.entry.title, "mode": self.mode,
                "config": self.config, "decision": asdict(self.decision) if self.decision else None,
                "actual_speed": self.actual_speed(), "last_command": self.last_command,
                "last_command_at": self.last_command_at, "error": self.error,
                "pending_mode": self._resume_mode,
                "conflicts": self._conflicts(), "inputs": inputs, "records": list(reversed(self._records))}

    async def async_stop(self):
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            # Preserve explicit ownership, not just the last output. The next
            # controller waits for valid inputs before resuming. Observe/fault
            # states deliberately do not arm the next instance.
            self._record("lifecycle", "controller_suspended")
            await self._store.async_save(self._storage_state())
            self.mode = "observe"
        self._listeners.clear()
