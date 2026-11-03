"""Local custom panel and administrator-only, bounded websocket endpoints."""
from __future__ import annotations

import asyncio
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import partial
from pathlib import Path

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .analytics import number, summarize, thin
from . import parameter_access
from .const import DOMAIN
from .panel_diagnostics import catalog, record_for, fault_entity, fault_history, read_registers
from .pump_config import ENTITY_FIELDS
from .curve_workshop import snapshot as curve_snapshot, validate as validate_curve
from .plant import legacy_plant, validate_plant, controller_problem
from .service_tools import ServiceTools, COMMANDS
from .heat_sources import validate as validate_heat_sources, history_entities as heat_source_entities
from .electric_overview import validate as validate_electric, migrate as migrate_electric, history_entities as electric_entities
from .schematic import validate_graph, completeness, history_entities as schematic_entities, catalogue as schematic_catalogue

PANEL_URL = "r290-control"
VERSION = "1.1.0"
STATUS_MAPPING_KEYS = ("dhw_entity", "buffer_charge_entity", "radiator_pump_entity", "dhw_charge_entity")
MAPPING_KEYS = ("pump_power_entity", "heat_energy_entity", "electric_energy_entity",
                "tank_entity", "buffer_entity", "outdoor_entity",
                "radiator_supply_entity", "radiator_return_entity", *STATUS_MAPPING_KEYS)


async def async_setup_panel(hass):
    domain = hass.data.setdefault(DOMAIN, {})
    if "_panel" in domain:
        return
    store = Store(hass, 1, "r290_heatpump.panel")
    saved = await store.async_load() or {}
    domain["_panel"] = {"store": store, "settings": saved.get("settings", {}),
                        "audit": deque(saved.get("audit", []), maxlen=300),
                        "write_lock": asyncio.Lock(), "history_lock": asyncio.Lock()}
    migrated = migrate_electric(domain["_panel"]["settings"])
    if migrated is not domain["_panel"]["settings"]:
        domain["_panel"]["settings"] = migrated
        _save(hass)
    service_store = Store(hass, 1, "r290_heatpump.service")
    domain["_service"] = ServiceTools(hass, service_store, await service_store.async_load())
    async def stop_service(_event):
        for entry_id in list(domain["_service"].pending):
            try:
                await domain["_service"].stop(entry_id)
            except Exception:
                pass  # Durable recovery state remains visible after restart.
    hass.bus.async_listen_once("homeassistant_stop", stop_service)
    await hass.http.async_register_static_paths([
        StaticPathConfig("/r290_heatpump_static", str(Path(__file__).parent / "frontend"), False)
    ])
    await hass.async_add_executor_job(catalog)
    await hass.async_add_executor_job(schematic_catalogue)
    for handler in (ws_panel, ws_settings, ws_charts, ws_schematic, ws_pump, ws_system_access, ws_parameter, ws_curve, ws_history, ws_registers, ws_faults, ws_service):
        websocket_api.async_register_command(hass, handler)
    await async_register_panel(
        hass, frontend_url_path=PANEL_URL, webcomponent_name="r290-control-panel",
        sidebar_title="R290 NextGen", sidebar_icon="mdi:heat-pump-outline",
        module_url=f"/r290_heatpump_static/r290-panel.js?v={VERSION}",
        require_admin=True, config={"version": VERSION},
    )


def _store(hass):
    return hass.data[DOMAIN]["_panel"]


def _save(hass):
    data = _store(hass)
    data["store"].async_delay_save(lambda: {"settings": data["settings"], "audit": list(data["audit"])}, 1)


def _admin(connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Administrator access required")
        return False
    return True


def _entries(hass):
    return {e.entry_id: e for e in hass.config_entries.async_entries(DOMAIN)}


def _entities(hass):
    entries = _entries(hass)
    registry = er.async_get(hass)
    return [e for e in registry.entities.values() if e.config_entry_id in entries and e.platform == DOMAIN]


def _allowed_history(hass):
    allowed = {e.entity_id for e in _entities(hass)}
    for entry in _entries(hass).values():
        config = {**entry.data, **entry.options}
        for key in (*ENTITY_FIELDS, "heat_meter", "power_meter", "outdoor_sensor", "cop_split_sensor"):
            value = config.get(key)
            allowed.update(value if isinstance(value, list) else [value] if isinstance(value, str) and value else [])
    allowed.update(v for k, v in _store(hass)["settings"].items() if k in MAPPING_KEYS and v)
    allowed.update(v for v in _store(hass)["settings"].get("plant", {}).get("valve_entities", {}).values() if v)
    allowed.update(heat_source_entities(_store(hass)["settings"].get("heat_sources", {})))
    allowed.update(electric_entities(_store(hass)["settings"].get("electric", {})))
    allowed.update(schematic_entities(_store(hass)["settings"].get("schematic", {})))
    allowed.update(entity for chart in _store(hass)["settings"].get("charts", {}).values() for entity in chart.get("entity_ids", []))
    return allowed


@websocket_api.websocket_command({vol.Required("type"): "r290_heatpump/panel"})
@websocket_api.async_response
async def ws_panel(hass, connection, msg):
    if not _admin(connection, msg):
        return
    entries = _entries(hass)
    data = _store(hass)
    controllers = [runtime["controller"].diagnostics() for entry_id, runtime in hass.data[DOMAIN].items()
                   if entry_id in entries and isinstance(runtime, dict) and "controller" in runtime]
    plant = data["settings"].get("plant") or legacy_plant(entries)
    plant_issues = []
    if "plant" in data["settings"]:
        try:
            validate_plant(plant, entries, hass.states)
        except ValueError as err:
            plant_issues.append(str(err))
        selected = next((c for c in controllers if c["entry_id"] == plant.get("controller_id")), None)
        if selected:
            problem = controller_problem(plant, selected["config"], er.async_get(hass))
            if problem:
                plant_issues.append(problem)
        elif plant.get("controller_id"):
            plant_issues.append("Assigned controller not loaded / Zugeordneter Regler nicht geladen")
    sources = {}
    heat_source_issues = []
    if "heat_sources" in data["settings"]:
        try:
            validate_heat_sources(data["settings"]["heat_sources"], entries, hass.states, plant)
        except ValueError as err:
            heat_source_issues.append(str(err))
    dhw_sources = set()
    for entry in entries.values():
        if entry.data.get("device_type") == "cop_calculator":
            config = {**entry.data, **entry.options}
            for source, target in (("heat_meter", "heat_energy_entity"), ("power_meter", "electric_energy_entity")):
                if isinstance(config.get(source), str):
                    sources.setdefault(target, config[source])
            if (not getattr(entry, "disabled_by", None) and config.get("cop_split_enabled")
                    and isinstance(config.get("cop_split_sensor"), str) and config["cop_split_sensor"]):
                dhw_sources.add(config["cop_split_sensor"])
    if len(dhw_sources) == 1:
        sources["dhw_entity"] = dhw_sources.pop()
    # Expose HA report times explicitly: frontend state snapshots do not always
    # include last_reported. Do not replace it with last_updated or imply that a
    # HA report confirms reception of a physical WM-Bus packet.
    reports = {}
    for entity_id in _allowed_history(hass):
        state = hass.states.get(entity_id)
        reported = getattr(state, "last_reported", None)
        if isinstance(reported, datetime):
            reports[entity_id] = reported.isoformat()
    connection.send_result(msg["id"], {
        "version": VERSION, "settings": data["settings"], "sources": sources,
        "system_access": parameter_access.status(connection),
        "plant": plant, "plant_issues": plant_issues,
        "heat_source_issues": heat_source_issues,
        "plant_configured": "plant" in data["settings"],
        "service": hass.data[DOMAIN]["_service"].status() if "_service" in hass.data[DOMAIN] else {"tests": {}, "snapshots": {}},
        "reports": reports,
        "polling": [{"entry_id":key[1] if key[0]=="bridge" else None,
                     "title":entries[key[1]].title if key[0]=="bridge" and key[1] in entries else "Modbus",
                     **value["hub"].polling_diagnostics()}
                    for key,value in hass.data[DOMAIN].get("_connections",{}).items()],
        "registers": {key: runtime["batch"].diagnostics() for key, runtime in hass.data[DOMAIN].items()
                      if key in entries and isinstance(runtime, dict) and runtime.get("batch")},
        "curves": [s for e in entries.values() if (s := curve_snapshot(e, _entities(hass)))],
        "entries": [{"id": e.entry_id, "title": e.title, "type": e.data.get("device_type"),
                     "slave": e.data.get("slave"), "disabled": bool(getattr(e, "disabled_by", None)), "state": str(e.state) if hasattr(e, "state") else None}
                    for e in entries.values()],
        "entities": [{"id": e.entity_id, "unique_id": e.unique_id, "entry_id": e.config_entry_id,
                      "name": e.name or e.original_name or e.entity_id,
                      "disabled": bool(e.disabled_by),
                      "register": (record_for(e.unique_id) or {}).get("address"),
                      "section": (record_for(e.unique_id) or {}).get("section"),
                      "fault": fault_entity(e)} for e in _entities(hass)],
        "controllers": controllers, "audit": list(reversed(data["audit"])),
        "recorder": "recorder" in hass.config.components,
    })


@websocket_api.websocket_command({vol.Required("type"): "r290_heatpump/settings", vol.Required("settings"): dict})
@websocket_api.async_response
async def ws_settings(hass, connection, msg):
    if not _admin(connection, msg):
        return
    settings = msg["settings"]
    if set(settings) - {*MAPPING_KEYS, "name", "tank_liters", "buffer_liters", "plant", "heat_sources", "electric"}:
        connection.send_error(msg["id"], "invalid_settings", "Unknown setting")
        return
    for key in MAPPING_KEYS:
        entity_id = settings.get(key)
        domains = {"sensor", "binary_sensor", "switch", "input_boolean"} if key in STATUS_MAPPING_KEYS else {"sensor"}
        if entity_id and (not isinstance(entity_id, str) or entity_id.split(".")[0] not in domains or hass.states.get(entity_id) is None):
            connection.send_error(msg["id"], "invalid_entity", key)
            return
    if not isinstance(settings.get("name", ""), str) or len(settings.get("name", "")) > 100:
        connection.send_error(msg["id"], "invalid_settings", "Name must be at most 100 characters")
        return
    for key in ("tank_liters", "buffer_liters"):
        value = number(settings.get(key, 0))
        if value is None or not 0 <= value <= 50000:
            connection.send_error(msg["id"], "invalid_settings", key)
            return
    # Old clients may save display mappings without knowing about plant settings.
    settings = dict(settings)
    if "electric" not in settings and "electric" in _store(hass)["settings"]:
        settings["electric"] = _store(hass)["settings"]["electric"]
    elif "electric" in settings:
        try:
            settings["electric"] = validate_electric(settings["electric"], hass.states)
        except ValueError as err:
            connection.send_error(msg["id"], "invalid_electric", str(err))
            return
    # The visual editor has its own revision-checked endpoint. Legacy forms must
    # neither erase its graph nor use this endpoint to bypass graph validation.
    if "schematic" in _store(hass)["settings"]:
        settings["schematic"] = _store(hass)["settings"]["schematic"]
    if "charts" in _store(hass)["settings"]:
        settings["charts"] = _store(hass)["settings"]["charts"]
    previous = _store(hass)["settings"].get("plant")
    if "plant" not in settings and previous:
        settings["plant"] = previous
    previous_sources = _store(hass)["settings"].get("heat_sources")
    if "heat_sources" not in settings and previous_sources is not None:
        settings["heat_sources"] = previous_sources
    elif isinstance(settings.get("heat_sources"), dict) and isinstance(previous_sources, dict):
        # A cached b8 client knows this heater, but may not know its new placement.
        source = settings["heat_sources"].get("buffer_heater")
        previous_heater = previous_sources.get("buffer_heater", {})
        if isinstance(source, dict) and "placement" not in source and "placement" in previous_heater:
            settings["heat_sources"] = {**settings["heat_sources"], "buffer_heater": {
                **source, "placement": previous_heater["placement"]}}
    if "plant" in settings:
        try:
            settings["plant"] = validate_plant(settings["plant"], _entries(hass), hass.states)
            if settings["plant"] != previous:
                for runtime in hass.data[DOMAIN].values():
                    controller = runtime.get("controller") if isinstance(runtime, dict) else None
                    if controller and (controller.mode != "observe" or getattr(controller, "_resume_mode", None)):
                        raise ValueError("Set controllers to Observe before changing the plant / Regler vor Umbau auf Beobachten setzen")
                service = hass.data[DOMAIN].get("_service")
                if service and (service.pending or getattr(service, "starting", False)):
                    raise ValueError("Finish service test before changing plant")
        except ValueError as err:
            connection.send_error(msg["id"], "invalid_plant", str(err))
            return
    if "heat_sources" in settings:
        try:
            settings["heat_sources"] = validate_heat_sources(settings["heat_sources"], _entries(hass), hass.states,
                                                            settings.get("plant") or legacy_plant(_entries(hass)))
        except ValueError as err:
            connection.send_error(msg["id"], "invalid_heat_sources", str(err))
            return
    _store(hass)["settings"] = settings
    _save(hass)
    connection.send_result(msg["id"], {"saved": True})


@websocket_api.websocket_command({vol.Required("type"): "r290_heatpump/charts",
    vol.Required("key"): str, vol.Required("expected_revision"): int,
    vol.Required("days"): vol.In([0.25, 0.5, 1, 2, 7, 30]),
    vol.Required("entity_ids"): [str]})
@websocket_api.async_response
async def ws_charts(hass, connection, msg):
    """Persist bounded display preferences without any device writes."""
    if not _admin(connection, msg):
        return
    key, ids, days = msg.get("key"), msg.get("entity_ids"), msg.get("days")
    if (not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", key)
            or type(days) not in (int, float) or days not in (0.25, 0.5, 1, 2, 7, 30)
            or not isinstance(ids, list) or not 1 <= len(ids) <= 24
            or any(not isinstance(e, str) or not re.fullmatch(r"sensor\.[a-z0-9_]+", e) or hass.states.get(e) is None for e in ids)
            or len(set(ids)) != len(ids)):
        connection.send_error(msg["id"], "invalid_chart", "Choose 1–24 existing sensors and a valid period / 1–24 Sensoren und gültigen Zeitraum wählen")
        return
    data = _store(hass)
    charts = data["settings"].get("charts", {})
    previous = charts.get(key, {})
    if key not in charts and len(charts) >= 100:
        connection.send_error(msg["id"], "invalid_chart", "Maximum 100 chart configurations")
        return
    if type(msg.get("expected_revision")) is not int or msg["expected_revision"] != previous.get("revision", 0):
        connection.send_error(msg["id"], "conflict", "Diagramm wurde geändert. Neu laden. / Chart changed; reload.")
        return
    updated = {"revision": previous.get("revision", 0) + 1, "days": days, "entity_ids": list(ids)}
    data["settings"] = {**data["settings"], "charts": {**charts, key: updated}}
    _save(hass)
    connection.send_result(msg["id"], {"chart": updated})


@websocket_api.websocket_command({vol.Required("type"): "r290_heatpump/schematic",
    vol.Required("action"): vol.In(["draft", "publish", "disable"]),
    vol.Required("expected_revision"): int, vol.Optional("graph"): dict})
@websocket_api.async_response
async def ws_schematic(hass, connection, msg):
    """Persist display topology only; deliberately never invokes HA services."""
    if not _admin(connection, msg):
        return
    data = _store(hass)
    previous = data["settings"].get("schematic", {})
    revision = previous.get("revision", 0)
    if type(msg.get("expected_revision")) is not int or msg["expected_revision"] != revision:
        connection.send_error(msg["id"], "conflict", "Schaubild wurde geändert. Entwurf exportieren und neu laden. / Schematic changed; export your draft and reload.")
        return
    action = msg.get("action")
    if action not in {"draft", "publish", "disable"}:
        connection.send_error(msg["id"], "invalid_schematic", "Invalid action")
        return
    try:
        graph = validate_graph(msg.get("graph")) if action != "disable" else previous.get("draft")
        # Legacy imports are validated before migration; electrical nodes do not
        # determine whether the remaining hydraulic circuit is complete.
        proposed = migrate_electric({**data["settings"], "schematic": {**previous, "draft": graph,
                                    "published": graph if action == "publish" else previous.get("published")}})
        graph = proposed["schematic"].get("draft")
        issues = completeness(graph) if graph else []
        if action == "publish" and issues:
            raise ValueError("; ".join(issues[:8]))
    except (ValueError, TypeError) as err:
        connection.send_error(msg["id"], "invalid_schematic", str(err))
        return
    # No awaits between revision check and update: concurrent editors cannot
    # silently replace each other's changes. Drafts keep the published view.
    updated = {**proposed["schematic"], "revision": revision + 1, "draft": graph,
               "published": graph if action == "publish" else None if action == "disable" else proposed["schematic"].get("published")}
    data["settings"] = {**proposed, "schematic": updated}
    _save(hass)
    connection.send_result(msg["id"], {"schematic": updated, "issues": issues, "electric": data["settings"].get("electric")})


@websocket_api.websocket_command({vol.Required("type"): "r290_heatpump/service",
    vol.Required("entry_id"): str, vol.Required("action"): vol.In(["read", "start", "stop"]),
    vol.Optional("component"): vol.In(list(COMMANDS)), vol.Optional("value"): int,
    vol.Optional("seconds"): int, vol.Optional("confirmed"): bool, vol.Optional("qualified"): bool})
@websocket_api.async_response
async def ws_service(hass, connection, msg):
    if not _admin(connection, msg):
        return
    service = hass.data[DOMAIN].get("_service")
    if service is None:
        connection.send_error(msg["id"], "not_loaded", "Service tools not loaded")
        return
    record = {"at": datetime.now(timezone.utc).isoformat(), "user_id": connection.user.id,
              "entity_id": msg["entry_id"], "before": "service", "requested": msg["action"],
              "component": msg.get("component"), "value": msg.get("value"), "seconds": msg.get("seconds")}
    try:
        if msg["action"] == "read":
            result = await service.inspect(msg["entry_id"])
        else:
            async with _store(hass)["write_lock"]:
                if msg["action"] == "start":
                    result = await service.start(msg["entry_id"], msg.get("component"), msg.get("value"),
                        msg.get("seconds"), msg.get("confirmed"), msg.get("qualified"))
                else:
                    await service.stop(msg["entry_id"])
                    result = {"released": True}
            record["result"] = "readback_verified"
        connection.send_result(msg["id"], result)
    except Exception as err:
        record.update(result="failed", error=str(err))
        connection.send_error(msg["id"], "service_failed", str(err))
    finally:
        if msg["action"] != "read":
            _store(hass)["audit"].append(record)
            _save(hass)


@websocket_api.websocket_command({
    vol.Required("type"): "r290_heatpump/pump",
    vol.Required("entry_id"): str,
    vol.Required("mode"): vol.In(["observe", "manual", "auto"]),
    vol.Optional("manual_speed"): vol.Coerce(float),
    vol.Required("confirmed"): bool,
})
@websocket_api.async_response
async def ws_pump(hass, connection, msg):
    if not _admin(connection, msg):
        return
    if not msg["confirmed"]:
        connection.send_error(msg["id"], "confirmation_required", "Confirm the requested pump mode")
        return
    runtime = hass.data[DOMAIN].get(msg["entry_id"], {})
    controller = runtime.get("controller")
    if controller is None:
        connection.send_error(msg["id"], "not_loaded", "Pump entry is not loaded")
        return
    try:
        await controller.async_set_mode(msg["mode"], manual_speed=msg.get("manual_speed"))
        if controller.mode != msg["mode"] and controller.error:
            raise ValueError(controller.error)
    except Exception as err:
        connection.send_error(msg["id"], "pump_control_failed", str(err))
        return
    connection.send_result(msg["id"], controller.diagnostics())


@websocket_api.websocket_command({
    vol.Required("type"): "r290_heatpump/system_access", vol.Required("entry_ids"): [str],
    vol.Required("action"): vol.In(["unlock", "lock"]), vol.Optional("password", default=""): str,
})
@websocket_api.async_response
async def ws_system_access(hass, connection, msg):
    if not _admin(connection, msg):
        return
    entries = _entries(hass)
    ids = msg["entry_ids"]
    if not ids or len(ids) > 16 or len(set(ids)) != len(ids) or any(key not in entries or entries[key].data.get("device_type") != "heat_pump" for key in ids):
        connection.send_error(msg["id"], "invalid_entry", "Wärmepumpen auswählen / Select heat pumps")
        return
    async with _store(hass)["write_lock"]:
        try:
            if msg["action"] == "lock":
                for key in ids:
                    parameter_access.grants(connection).pop(key, None)
            else:
                await parameter_access.unlock(hass, connection, [entries[key] for key in ids], msg["password"])
        except Exception as err:
            connection.send_error(msg["id"], "system_locked", str(err) if isinstance(err, ValueError) else "P183 nicht lesbar / Cannot read P183")
            return
    connection.send_result(msg["id"], {"system_access": parameter_access.status(connection)})


@websocket_api.websocket_command({
    vol.Required("type"): "r290_heatpump/parameter", vol.Required("entity_id"): str,
    vol.Required("expected"): str, vol.Required("value"): vol.Any(str, int, float, bool),
    vol.Required("confirmed"): bool,
})
@websocket_api.async_response
async def ws_parameter(hass, connection, msg):
    if not _admin(connection, msg):
        return
    entity_id = msg["entity_id"]
    meta = next((e for e in _entities(hass) if e.entity_id == entity_id and not e.disabled_by), None)
    entries = _entries(hass)
    if meta is None or entries[meta.config_entry_id].data.get("device_type") == "auxiliary_pump":
        connection.send_error(msg["id"], "invalid_entity", "Use the dedicated pump control for this entity")
        return
    if not msg["confirmed"]:
        connection.send_error(msg["id"], "confirmation_required", "Confirm the parameter change")
        return
    async with _store(hass)["write_lock"]:
        parameter = record_for(meta.unique_id) or {}
        if parameter.get("section") == 4:
            try:
                await parameter_access.verify(hass, connection, entries[meta.config_entry_id])
            except Exception as err:
                connection.send_error(msg["id"], "system_locked", str(err) if isinstance(err, ValueError) else "P183 nicht lesbar / Cannot read P183")
                return
        if hass.data[DOMAIN].get("_service") and hass.data[DOMAIN]["_service"].pending:
            connection.send_error(msg["id"], "service_active", "End service test before parameter changes / Erst Servicetest beenden")
            return
        state = hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            connection.send_error(msg["id"], "unavailable", "Parameter is unavailable")
            return
        if state.state != msg["expected"]:
            connection.send_error(msg["id"], "state_changed", "Value changed since preview; review again")
            return
        domain = entity_id.split(".")[0]
        value = msg["value"]
        payload = {"entity_id": entity_id}
        try:
            if domain == "number":
                parsed = number(value)
                lo, hi = state.attributes.get("min"), state.attributes.get("max")
                if parsed is None or lo is None or hi is None or not float(lo) <= parsed <= float(hi):
                    raise ValueError("Value outside entity limits")
                step = Decimal(str(state.attributes.get("step", 1)))
                if step > 0 and (Decimal(str(value)) - Decimal(str(lo))) % step != 0:
                    raise ValueError("Value does not match entity step")
                service, payload["value"] = "set_value", parsed
            elif domain == "select" and value in state.attributes.get("options", []):
                service, payload["option"] = "select_option", value
            elif domain == "switch" and value in ("on", "off"):
                service = "turn_on" if value == "on" else "turn_off"
            else:
                raise ValueError("Unsupported parameter action")
        except (ValueError, TypeError, ArithmeticError) as err:
            connection.send_error(msg["id"], "invalid_value", str(err))
            return
        record = {"at": datetime.now(timezone.utc).isoformat(), "entity_id": entity_id,
                  "user_id": connection.user.id, "before": state.state, "requested": value}
        is_password = parameter.get("address") == parameter_access.PASSWORD_REGISTER
        if is_password:
            record.update(before="••••", requested="••••")
        try:
            async with asyncio.timeout(30):
                await hass.services.async_call(domain, service, payload, blocking=True, context=connection.context(msg))
            record["result"] = "sent"
            connection.send_result(msg["id"], {"sent": True, "verification_pending": True})
        except Exception as err:
            record["result"], record["error"] = "failed", "Password update failed / Passwortänderung fehlgeschlagen" if is_password else str(err)
            connection.send_error(msg["id"], "write_failed", record["error"])
        finally:
            if is_password:
                parameter_access.grants(connection).pop(meta.config_entry_id, None)
            _store(hass)["audit"].append(record)
            _save(hass)


@websocket_api.websocket_command({
    vol.Required("type"): "r290_heatpump/curve", vol.Required("entry_id"): str,
    vol.Required("revision"): str, vol.Required("changes"): [dict],
    vol.Optional("points"): [dict],
    vol.Required("confirmed"): bool,
})
@websocket_api.async_response
async def ws_curve(hass, connection, msg):
    if not _admin(connection, msg):
        return
    if not msg["confirmed"]:
        connection.send_error(msg["id"], "confirmation_required", "Kurvenänderungen bestätigen")
        return
    async with _store(hass)["write_lock"]:
        if hass.data[DOMAIN].get("_service") and hass.data[DOMAIN]["_service"].pending:
            connection.send_error(msg["id"], "service_active", "End service test before curve changes / Erst Servicetest beenden")
            return
        entry = _entries(hass).get(msg["entry_id"])
        snap = curve_snapshot(entry, _entities(hass)) if entry else None
        if snap is None or snap["revision"] != msg["revision"]:
            connection.send_error(msg["id"], "state_changed", "Konfiguration geändert. Entwurf verwerfen und neu prüfen.")
            return
        try:
            values = validate_curve(entry, snap, msg["changes"], hass.states, msg.get("points"))
        except (ValueError, TypeError, ArithmeticError) as err:
            connection.send_error(msg["id"], "invalid_value", str(err))
            return
        records = [{"at": datetime.now(timezone.utc).isoformat(), "user_id": connection.user.id,
                    "entity_id": c["entity_id"], "before": c["expected"], "requested": c["value"]}
                   for c in msg["changes"]]
        if "points" in msg:
            records.append({"at": datetime.now(timezone.utc).isoformat(), "user_id": connection.user.id,
                            "entity_id": f"curve:{entry.entry_id}", "before": snap["points"],
                            "requested": values["curve_points"]})
        try:
            # One configuration commit: no intermediate curve from sequential
            # number/select services; the existing listener reloads this entry.
            hass.config_entries.async_update_entry(entry, data={**entry.data, **values}, options={**entry.options, **values})
            for record in records:
                record["result"] = "configured"
            connection.send_result(msg["id"], {"configured": True, "verification_pending": True})
        except Exception as err:
            for record in records:
                record.update(result="failed", error=str(err))
            connection.send_error(msg["id"], "write_failed", str(err))
        finally:
            _store(hass)["audit"].extend(records)
            _save(hass)


def _history_result(hass, start, end, ids, metadata):
    from homeassistant.components.recorder import history
    states = history.get_significant_states(hass, start, end, ids,
        include_start_time_state=True, significant_changes_only=False,
        minimal_response=False, no_attributes=False)
    series = {}
    for entity_id in ids:
        values = states.get(entity_id, [])
        points = [[s.last_updated.timestamp(), number(s.state)] for s in values]
        attributes = metadata.get(entity_id, {})
        unit = attributes.get("unit_of_measurement", "")
        kind = "energy" if attributes.get("device_class") == "energy" or unit in ("kWh", "Wh", "MWh", "GJ", "MJ") else "value"
        summary = summarize(points, start.timestamp(), end.timestamp(), kind=kind)
        series[entity_id] = {"points": thin(points), "summary": summary,
                             "unit": unit, "kind": kind, "samples": len(points)}
        # Phase transitions need unthinned frequency and boolean events. Unknown
        # states remain gaps. Other numeric plots keep the compact envelope.
        if unit == "Hz" or not unit:
            events = []
            for state in values:
                if not events or events[-1][1] != state.state:
                    events.append([state.last_updated.timestamp(), state.state])
            series[entity_id].update(states=events[-6000:], states_truncated=len(events) > 6000)

    return {"start": start.isoformat(), "end": end.isoformat(), "series": series}


@websocket_api.websocket_command({
    vol.Required("type"): "r290_heatpump/history", vol.Required("entity_ids"): [str],
    vol.Optional("days", default=1): vol.In([0.25, 0.5, 1, 2, 7, 30]),
})
@websocket_api.async_response
async def ws_history(hass, connection, msg):
    if not _admin(connection, msg):
        return
    ids = list(dict.fromkeys(msg["entity_ids"]))
    if not ids or len(ids) > 24 or not set(ids) <= _allowed_history(hass):
        connection.send_error(msg["id"], "invalid_entities", "Choose 1–24 configured plant entities")
        return
    if "recorder" not in hass.config.components:
        connection.send_error(msg["id"], "recorder_unavailable", "Home Assistant Recorder is required for history")
        return
    from homeassistant.components.recorder import get_instance
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=msg["days"])
    metadata = {e: dict(s.attributes) for e in ids if (s := hass.states.get(e))}
    try:
        async with _store(hass)["history_lock"]:
            result = await get_instance(hass).async_add_executor_job(partial(_history_result, hass, start, end, ids, metadata))
        connection.send_result(msg["id"], result)
    except Exception as err:
        connection.send_error(msg["id"], "history_failed", str(err))

@websocket_api.websocket_command({
    vol.Required("type"): "r290_heatpump/registers", vol.Required("entry_id"): str,
    vol.Required("addresses"): [int],
})
@websocket_api.async_response
async def ws_registers(hass, connection, msg):
    if not _admin(connection, msg):
        return
    try:
        result = await read_registers(hass, msg["entry_id"], msg["addresses"], _entries(hass), DOMAIN)
        connection.send_result(msg["id"], result)
    except Exception as err:
        connection.send_error(msg["id"], "diagnostic_read_failed", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "r290_heatpump/faults",
    vol.Optional("days", default=7): vol.In([1, 7, 30]),
})
@websocket_api.async_response
async def ws_faults(hass, connection, msg):
    if not _admin(connection, msg):
        return
    if "recorder" not in hass.config.components:
        connection.send_error(msg["id"], "recorder_unavailable", "Home Assistant Recorder is required for history")
        return
    ids = [e.entity_id for e in _entities(hass) if fault_entity(e) and not e.disabled_by]
    if not ids:
        connection.send_result(msg["id"], {"events": [], "total": 0, "truncated": False, "entity_ids": [], "recorded_ids": []})
        return
    from homeassistant.components.recorder import get_instance
    end = datetime.now(timezone.utc)
    try:
        async with _store(hass)["history_lock"]:
            result = await get_instance(hass).async_add_executor_job(partial(fault_history, hass, end-timedelta(days=msg["days"]), end, ids))
        connection.send_result(msg["id"], result)
    except Exception as err:
        connection.send_error(msg["id"], "history_failed", str(err))
