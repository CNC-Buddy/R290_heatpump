from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity import EntityCategory

FIELDS = {
    "queue_depth": ("Polling Queue", None, False),
    "overdue_registers": ("Polling Overdue Registers", None, False),
    "transactions_last_minute": ("Modbus Transactions Last Minute", None, True),
    "errors_last_minute": ("Modbus Errors Last Minute", None, True),
    "latency_p95": ("Modbus Response Time P95", "ms", True),
    "transport_time_fraction": ("Modbus Transport Time", "%", True),
}


class PollingSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = True

    def __init__(self, entry, hub, device, key):
        self.hub = hub
        self.key = key
        self._transport = FIELDS[key][2]
        self._attr_name = FIELDS[key][0]
        self._attr_native_unit_of_measurement = FIELDS[key][1]
        self._attr_unique_id = f"r290_heatpump_{entry.entry_id}_{key}"
        self._attr_device_info = device
        self._attr_native_value = None

    async def async_update(self):
        data = self.hub.polling_diagnostics()
        value = (data["transport"] if self._transport else data).get(self.key)
        if value is not None and self.key == "latency_p95":
            value = round(value * 1000, 1)
        if value is not None and self.key == "transport_time_fraction":
            value = round(value * 100, 1)
        self._attr_native_value = value
        self._attr_available = value is not None
