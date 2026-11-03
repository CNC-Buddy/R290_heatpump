"""Standard HA entities for the auxiliary pump (also usable without the panel)."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.number import NumberEntity

from .pump_logic import MODES


class PumpEntity:
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller, key, name):
        self.controller = controller
        self._attr_unique_id = f"r290_pump_{controller.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {("r290_heatpump", f"pump_{controller.entry.entry_id}")},
            "name": controller.entry.title, "manufacturer": "R290 Heat Pump",
            "model": "Auxiliary pump controller",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.async_add_listener(self.async_write_ha_state))


class PumpStatus(PumpEntity, SensorEntity):
    _attr_icon = "mdi:pump"

    def __init__(self, controller):
        super().__init__(controller, "status", "Operating phase")

    @property
    def native_value(self):
        return self.controller.decision.phase if self.controller.decision else "initializing"

    @property
    def extra_state_attributes(self):
        c = self.controller
        d = c.decision
        return {"mode": c.mode, "reason": d.reason if d else None, "error": c.error,
                "active_units": d.active_units if d else 0,
                "target_delta": d.target_delta if d else None,
                "deltas": list(d.deltas) if d else [],
                "last_command": c.last_command, "last_command_at": c.last_command_at}


class PumpSpeed(PumpEntity, SensorEntity):
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:speedometer"

    def __init__(self, controller):
        super().__init__(controller, "suggested_speed", "Suggested speed")

    @property
    def native_value(self):
        return self.controller.decision.speed if self.controller.decision else None


class PumpActualSpeed(PumpEntity, SensorEntity):
    """Normalized actuator feedback, recordable even for light/voltage outputs."""
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:speedometer"

    def __init__(self, controller):
        super().__init__(controller, "actual_speed", "Actual control output")

    @property
    def native_value(self):
        return self.controller.actual_speed()


class PumpTargetDelta(PumpEntity, SensorEntity):
    _attr_native_unit_of_measurement = "K"
    _attr_state_class = "measurement"

    def __init__(self, controller):
        super().__init__(controller, "target_delta", "Target temperature difference")

    @property
    def native_value(self):
        return self.controller.decision.target_delta if self.controller.decision else None


class PumpMode(PumpEntity, SelectEntity):
    _attr_options = list(MODES)
    _attr_icon = "mdi:tune-variant"

    def __init__(self, controller):
        super().__init__(controller, "control_mode", "Control mode")

    @property
    def current_option(self):
        return self.controller.mode

    async def async_select_option(self, option):
        await self.controller.async_set_mode(option)


class PumpManualSpeed(PumpEntity, NumberEntity):
    _attr_native_unit_of_measurement = "%"
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(self, controller):
        super().__init__(controller, "manual_speed", "Manual speed")
        self._attr_native_min_value = controller.config["min_speed"]
        self._attr_native_max_value = controller.config["max_speed"]

    @property
    def native_value(self):
        return self.controller.config["manual_speed"]

    async def async_set_native_value(self, value):
        await self.controller.async_set_manual_speed(value)
