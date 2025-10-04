"""Register a Lovelace dashboard shipped with the R290 Heat Pump integration."""
from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from homeassistant.components import frontend
from homeassistant.components.lovelace import const as lovelace_const
from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_LOVELACE_TEMPLATE = Path(__file__).parent / "lovelace_dashboard.yaml"
_DASHBOARD_DIR = "dashboards"
_DASHBOARD_FILENAME = "r290_heatpump.yaml"
_DASHBOARD_URL_PATH = "r290-heatpump"
_DASHBOARD_TITLE = "R290 Heat Pump"
_DASHBOARD_ICON = "mdi:heat-wave"


async def async_setup_dashboard(hass: HomeAssistant) -> None:
    """Ensure the packaged Lovelace dashboard is available in Home Assistant."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_dashboard_ready"):
        return

    template_text = await _read_template(hass)
    if template_text is None:
        return

    if await _synchronize_packaged_file(hass, template_text) is None:
        return

    template_config = await _parse_lovelace_config(hass, template_text)
    if template_config is None:
        return

    async def _finalize_setup() -> None:
        success = await _register_storage_dashboard(hass, template_config)
        if success:
            domain_data["_dashboard_ready"] = True

    if lovelace_const.DOMAIN in hass.config.components:
        await _finalize_setup()
        return

    @callback
    def _on_component_loaded(event) -> None:
        if event.data.get("component") != lovelace_const.DOMAIN:
            return
        unsubscribe()
        hass.async_create_task(_finalize_setup())

    unsubscribe = hass.bus.async_listen(EVENT_COMPONENT_LOADED, _on_component_loaded)


def _read_text_with_encoding(path: Path, encoding: str) -> str:
    return path.read_text(encoding=encoding)


async def _read_template(hass: HomeAssistant) -> str | None:
    if not _LOVELACE_TEMPLATE.is_file():
        _LOGGER.warning(
            "Dashboard template missing at %s; skipping dashboard creation",
            _LOVELACE_TEMPLATE,
        )
        return None

    try:
        return await hass.async_add_executor_job(
            _read_text_with_encoding,
            _LOVELACE_TEMPLATE,
            "utf-8",
        )
    except UnicodeDecodeError:
        template_text = await hass.async_add_executor_job(
            _read_text_with_encoding,
            _LOVELACE_TEMPLATE,
            "cp1252",
        )
        await hass.async_add_executor_job(
            _LOVELACE_TEMPLATE.write_text,
            template_text,
            "utf-8",
        )
        return template_text
    except Exception as err:  # pragma: no cover - filesystem error
        _LOGGER.error("Failed to read packaged dashboard template: %s", err)
        return None


async def _synchronize_packaged_file(hass: HomeAssistant, template_text: str) -> Path | None:
    dashboards_path = Path(hass.config.path(_DASHBOARD_DIR))
    try:
        await hass.async_add_executor_job(dashboards_path.mkdir, 0o777, True, True)
    except Exception as err:  # pragma: no cover - filesystem error
        _LOGGER.error("Failed to prepare dashboards directory %s: %s", dashboards_path, err)
        return None

    target_path = dashboards_path / _DASHBOARD_FILENAME
    try:
        needs_write = not await hass.async_add_executor_job(target_path.exists)
        if not needs_write:
            existing = await hass.async_add_executor_job(target_path.read_text, "utf-8")
            needs_write = existing != template_text
        if needs_write:
            await hass.async_add_executor_job(target_path.write_text, template_text, "utf-8")
            _LOGGER.debug("Synchronized Lovelace dashboard file at %s", target_path)
    except Exception as err:  # pragma: no cover - filesystem error
        _LOGGER.error("Failed to synchronize dashboard file %s: %s", target_path, err)
        return None

    return target_path


async def _parse_lovelace_config(hass: HomeAssistant, template_text: str) -> dict[str, Any] | None:
    try:
        data = await hass.async_add_executor_job(partial(yaml.safe_load, template_text))
    except Exception as err:  # pragma: no cover - yaml error
        _LOGGER.error("Failed to parse Lovelace template: %s", err)
        return None

    if not isinstance(data, dict):
        _LOGGER.error("Lovelace template must define a mapping at the root")
        return None

    data.setdefault("views", [])
    return data


async def _register_storage_dashboard(
    hass: HomeAssistant,
    template_config: dict[str, Any],
) -> bool:
    lovelace_data = hass.data.get(lovelace_const.LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.warning("Lovelace not fully initialized; dashboard registration postponed")
        return False

    dashboards_collection = lovelace_dashboard.DashboardsCollection(hass)
    try:
        await dashboards_collection.async_load()
    except Exception as err:  # pragma: no cover - storage error
        _LOGGER.error("Failed to load Lovelace dashboards collection: %s", err)
        return False

    existing_id: str | None = None
    existing_item: dict[str, Any] | None = None
    for item_id, item in dashboards_collection.data.items():
        if item.get(lovelace_const.CONF_URL_PATH) == _DASHBOARD_URL_PATH:
            existing_id = item_id
            existing_item = item
            break

    base_item: dict[str, Any] = {
        lovelace_const.CONF_TITLE: _DASHBOARD_TITLE,
        lovelace_const.CONF_ICON: _DASHBOARD_ICON,
        lovelace_const.CONF_URL_PATH: _DASHBOARD_URL_PATH,
        lovelace_const.CONF_REQUIRE_ADMIN: False,
        lovelace_const.CONF_SHOW_IN_SIDEBAR: True,
    }

    item: dict[str, Any]
    if existing_item is None:
        _LOGGER.info("Creating storage-backed Lovelace dashboard '%s'", _DASHBOARD_URL_PATH)
        try:
            item = await dashboards_collection.async_create_item(
                {**base_item, lovelace_const.CONF_MODE: lovelace_const.MODE_STORAGE}
            )
        except Exception as err:  # pragma: no cover - runtime safety
            _LOGGER.error("Failed to create Lovelace dashboard metadata: %s", err)
            return False
    else:
        updates = {}
        for key, value in (
            (lovelace_const.CONF_TITLE, _DASHBOARD_TITLE),
            (lovelace_const.CONF_ICON, _DASHBOARD_ICON),
            (lovelace_const.CONF_SHOW_IN_SIDEBAR, True),
            (lovelace_const.CONF_REQUIRE_ADMIN, False),
        ):
            if existing_item.get(key) != value:
                updates[key] = value

        if updates:
            _LOGGER.info("Updating Lovelace dashboard metadata for '%s'", _DASHBOARD_URL_PATH)
            try:
                item = await dashboards_collection.async_update_item(existing_id, updates)
            except Exception as err:  # pragma: no cover - runtime safety
                _LOGGER.error("Failed to update Lovelace dashboard metadata: %s", err)
                item = existing_item
        else:
            item = existing_item

    lovelace_config = lovelace_data.dashboards.get(_DASHBOARD_URL_PATH)
    if not isinstance(lovelace_config, lovelace_dashboard.LovelaceStorage):
        lovelace_config = lovelace_dashboard.LovelaceStorage(hass, item)
        lovelace_data.dashboards[_DASHBOARD_URL_PATH] = lovelace_config
    else:
        lovelace_config.config = {**item, lovelace_const.CONF_URL_PATH: _DASHBOARD_URL_PATH}

    try:
        await lovelace_config.async_save(template_config)
    except Exception as err:  # pragma: no cover - runtime safety
        _LOGGER.error("Failed to store Lovelace dashboard layout: %s", err)
        return False

    frontend.async_register_built_in_panel(
        hass,
        lovelace_const.DOMAIN,
        frontend_url_path=_DASHBOARD_URL_PATH,
        sidebar_title=_DASHBOARD_TITLE,
        sidebar_icon=_DASHBOARD_ICON,
        require_admin=False,
        config={"mode": lovelace_config.mode},
        update=True,
    )

    return True

async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Remove the Lovelace dashboard for the integration."""
    hass.data.setdefault(DOMAIN, {}).pop("_dashboard_ready", None)
    lovelace_data = hass.data.get(lovelace_const.LOVELACE_DATA)
    if lovelace_data is not None:
        dashboards_collection = lovelace_dashboard.DashboardsCollection(hass)
        try:
            await dashboards_collection.async_load()
        except Exception as err:  # pragma: no cover - storage error
            _LOGGER.warning("Failed to load Lovelace dashboards collection for removal: %s", err)
        else:
            for item_id, item in list(dashboards_collection.data.items()):
                if item.get(lovelace_const.CONF_URL_PATH) == _DASHBOARD_URL_PATH:
                    try:
                        await dashboards_collection.async_delete_item(item_id)
                    except Exception as err:  # pragma: no cover - storage error
                        _LOGGER.warning("Failed to remove Lovelace dashboard metadata: %s", err)
                    break
        lovelace_data.dashboards.pop(_DASHBOARD_URL_PATH, None)
    target_path = Path(hass.config.path(_DASHBOARD_DIR)) / _DASHBOARD_FILENAME
    try:
        await hass.async_add_executor_job(target_path.unlink)
    except FileNotFoundError:
        pass
    except Exception as err:  # pragma: no cover - filesystem error
        _LOGGER.debug("Failed to remove synchronized dashboard file %s: %s", target_path, err)
    frontend.async_remove_panel(hass, _DASHBOARD_URL_PATH)



__all__ = ["async_setup_dashboard", "async_remove_dashboard"]
