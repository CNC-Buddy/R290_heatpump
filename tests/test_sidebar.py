"""Sidebar settings must preserve panel configuration and survive startup order."""
import types
import unittest
from unittest.mock import patch, AsyncMock

import test_shared_connection as fixture
from r290_under_test.sidebar import (apply_sidebar_visibility, setup_sidebar_visibility,
    PANEL_VISIBILITY, DASHBOARD_VISIBILITY, PANEL_PATH, DASHBOARD_PATH)
import homeassistant.components.frontend as frontend


def panel(name):
    return types.SimpleNamespace(component_name=name, sidebar_title=name, sidebar_icon="mdi:test",
        sidebar_default_visible=True, config={"mode": "storage", "custom": 1},
        require_admin=True, config_panel_domain=None, show_in_sidebar=True)


class SidebarTests(unittest.TestCase):
    def setUp(self):
        self.hass = fixture.Hass([])
        self.hass.data[frontend.DATA_PANELS] = {PANEL_PATH: panel("custom"), DASHBOARD_PATH: panel("lovelace")}
        self.calls = []
        def register(hass, component, **kwargs):
            self.calls.append((component, kwargs))
            p = hass.data[frontend.DATA_PANELS][kwargs["frontend_url_path"]]
            p.show_in_sidebar = kwargs["show_in_sidebar"]
        self.patcher = patch.object(frontend, "async_register_built_in_panel", register)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_independent_reversible_visibility_preserves_config(self):
        apply_sidebar_visibility(self.hass, {PANEL_VISIBILITY: False, DASHBOARD_VISIBILITY: True})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1]["config"], {"mode": "storage", "custom": 1})
        self.assertTrue(self.calls[0][1]["require_admin"])
        apply_sidebar_visibility(self.hass, {PANEL_VISIBILITY: True, DASHBOARD_VISIBILITY: False})
        self.assertEqual([c[1]["show_in_sidebar"] for c in self.calls], [False, True, False])
        self.assertEqual(self.calls[-1][1]["frontend_url_path"], DASHBOARD_PATH)

    def test_saved_options_apply_again_after_lovelace_load(self):
        entry = fixture.Entry("bridge", "modbus_bridge")
        entry.options = {PANEL_VISIBILITY: False, DASHBOARD_VISIBILITY: False}
        events = {}
        self.hass.bus.async_listen = lambda event, handler: events.setdefault(event, handler) or (lambda: None)
        dashboard = self.hass.data[frontend.DATA_PANELS].pop(DASHBOARD_PATH)
        setup_sidebar_visibility(self.hass, entry)
        self.assertFalse(self.hass.data[frontend.DATA_PANELS][PANEL_PATH].show_in_sidebar)
        self.hass.data[frontend.DATA_PANELS][DASHBOARD_PATH] = dashboard
        events["component_loaded"](types.SimpleNamespace(data={"component": "lovelace"}))
        self.assertFalse(dashboard.show_in_sidebar)

    def test_missing_settings_or_dashboard_do_not_change_other_panels(self):
        self.hass.data[frontend.DATA_PANELS].pop(DASHBOARD_PATH)
        apply_sidebar_visibility(self.hass, {})
        apply_sidebar_visibility(self.hass, {DASHBOARD_VISIBILITY: False})
        self.assertEqual(self.calls, [])


class SidebarOptionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_bridge_options_save_both_switches_without_discarding_other_options(self):
        bridge = fixture.Entry("bridge", "modbus_bridge", host="gateway", port=502)
        bridge.options = {"existing": "kept"}
        hass = fixture.Hass([bridge])
        flow = fixture.flow_module.R290HeatPumpOptionsFlow(bridge)
        flow.hass = hass
        with patch.object(fixture.flow_module, "async_update_bridge_connection", new=AsyncMock()), \
             patch.object(fixture.flow_module, "apply_sidebar_visibility") as apply:
            result = await flow.async_step_init({"host": "gateway", "port": 502,
                "connection_type": "rtuovertcp", PANEL_VISIBILITY: False, DASHBOARD_VISIBILITY: True})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], {"existing": "kept", PANEL_VISIBILITY: False, DASHBOARD_VISIBILITY: True})
        apply.assert_called_once_with(hass, result["data"])


if __name__ == "__main__":
    unittest.main()
