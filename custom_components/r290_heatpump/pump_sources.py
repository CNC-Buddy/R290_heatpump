"""Existing, read-only register signals required by auxiliary-pump control."""

# MAIN_SENSORS decodes these bits from registers already read by the integration.
# 0x0019 bit 6: internal circulation pump, including operation without compressor.
# 0x0000 bit 8: defrost status. Each cascade slave supplies its own two signals.
PUMP_STATUS_SOURCES = {
    "demand_entity": "relay_output_status_1_main_engine_circulating_water_pump_status",
    "defrost_entities": "running_status_1_system_defrost_status",
}
PUMP_STATUS_REGISTERS = {
    PUMP_STATUS_SOURCES["demand_entity"]: (0x0019, 6),
    PUMP_STATUS_SOURCES["defrost_entities"]: (0x0000, 8),
}


def normalize_pump_sources(values):
    """Accept a saved single demand entity, but expose a multi-select everywhere."""
    result = dict(values or {})
    if isinstance(result.get("demand_entity"), str):
        result["demand_entity"] = [result["demand_entity"]] if result["demand_entity"] else []
    return result


def async_enable_default_pump_sources(hass, entry, slave):
    """Upgrade former integration-disabled defaults; preserve user disables.

    Called on the sensor platform's setup, never on opening the config flow.
    This only enables two read-only entity views per unit, with unchanged IDs.
    No relay, device parameter or auxiliary-controller mode is written.
    """
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    required = {
        f"r290_heatpump_{fragment}_slave_{slave}"
        for fragment in PUMP_STATUS_SOURCES.values()
    }
    for meta in tuple(registry.entities.values()):
        if (meta.config_entry_id == entry.entry_id
                and meta.platform == "r290_heatpump"
                and meta.unique_id in required
                and meta.disabled_by == er.RegistryEntryDisabler.INTEGRATION):
            registry.async_update_entity(meta.entity_id, disabled_by=None)
