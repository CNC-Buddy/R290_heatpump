"""Graph invariants and the real display-only websocket handler."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import unittest

import test_panel_api as panel_fixture

panel = panel_fixture.panel

model = importlib.import_module("r290_under_test.schematic")
FIXTURES = json.loads(Path(__file__).with_name("schematic-fixtures.json").read_text(encoding="utf-8"))


class GraphTests(unittest.TestCase):
    def test_all_presets_are_complete(self):
        for graph in FIXTURES.values():
            self.assertEqual(model.completeness(model.validate_graph(graph)), [])

    def test_valve_has_exactly_three_supply_ports(self):
        node = next(n for n in FIXTURES["full"]["nodes"] if n["id"] == "we2_valve")
        ports = model.ports(node)
        self.assertEqual(len(ports), 3)
        self.assertEqual({p["leg"] for p in ports.values()}, {"supply"})

    def test_crossed_exchanger_and_double_ports_rejected(self):
        for mutation in ("secondary", "duplicate", "fourth_valve_port", "wrong_direction"):
            graph = deepcopy(FIXTURES["full"])
            if mutation == "secondary":
                e = next(e for e in graph["edges"] if e["to"] == {"node": "ww", "port": "wp_in"})
                e["to"] = {"node": "plate", "port": "secondary_in"}
            elif mutation == "duplicate":
                graph["edges"].append({**graph["edges"][0], "id": "duplicate"})
            elif mutation == "fourth_valve_port":
                graph["edges"][0]["to"] = {"node": "we2_valve", "port": "return"}
            else:
                e = graph["edges"][0]
                e["from"], e["to"] = e["to"], e["from"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                model.validate_graph(graph)

    def test_unknown_schema_nonfinite_and_limits_rejected(self):
        for key, value in (("version", True), ("version", 9), ("unexpected", 1)):
            graph = deepcopy(FIXTURES["direct"]); graph[key] = value
            with self.assertRaises(ValueError): model.validate_graph(graph)
        for value in (float("nan"), float("inf"), True, -1, 3601):
            graph = deepcopy(FIXTURES["direct"]); graph["nodes"][0]["x"] = value
            with self.assertRaises(ValueError): model.validate_graph(graph)

    def test_missing_circulation_return_detected(self):
        graph = deepcopy(FIXTURES["full"])
        graph["edges"] = [e for e in graph["edges"] if e["from"]["node"] != "turn"]
        model.validate_graph(graph)
        self.assertTrue(any("circulation" in issue for issue in model.completeness(graph)))

    def test_saved_automatic_routes_and_electrical_soc(self):
        graph = deepcopy(FIXTURES["full_pv"])
        graph["edges"][0]["route"] = [[-30, 0], [3900, 0], [3900, 3880]]
        next(n for n in graph["nodes"] if n["type"] == "battery")["bindings"]["soc"] = "sensor.battery_soc"
        self.assertEqual(model.validate_graph(graph), graph)
        self.assertEqual(model.completeness(graph), [])
        for route in (None, [], [[0, 0]], [[0, 0], [1, 1]], [[0, 0], [True, 0]],
                      [[0, 0], [float("inf"), 0]], [[0, 0], [4001, 0]], [[0, 0]] * 257):
            graph["edges"][0]["route"] = route
            with self.subTest(route=route), self.assertRaises(ValueError):
                model.validate_graph(graph)


class SchematicEndpointTests(unittest.IsolatedAsyncioTestCase):
    setUp = panel_fixture.PanelTests.setUp
    error_code = panel_fixture.PanelTests.error_code
    async def send(self, action="draft", revision=0, graph=None):
        await panel.ws_schematic(self.hass, self.connection, dict(id=1, action=action,
            expected_revision=revision, graph=graph or deepcopy(FIXTURES["full"])))

    async def test_display_save_no_hardware_calls_and_conflict_protection(self):
        graph = deepcopy(FIXTURES["full"])
        graph["edges"][0]["route"] = [[30, 40], [400, 40]]
        await self.send("publish", graph=graph)
        self.connection.send_error.assert_not_called()
        stored = self.hass.data["r290_heatpump"]["_panel"]["settings"]["schematic"]
        self.assertEqual(stored["revision"], 1)
        self.assertIsNotNone(stored["published"])
        self.assertEqual(stored["published"]["edges"][0]["route"], graph["edges"][0]["route"])
        self.hass.services.async_call.assert_not_awaited()
        await self.send("draft", 0)
        self.assertEqual(self.error_code(), "conflict")
        self.assertEqual(stored["revision"], 1)

    async def test_incomplete_draft_keeps_published_graph(self):
        await self.send("publish")
        old = self.hass.data["r290_heatpump"]["_panel"]["settings"]["schematic"]["published"]
        draft = deepcopy(FIXTURES["full"]); draft["edges"].pop()
        await self.send("draft", 1, draft)
        stored = self.hass.data["r290_heatpump"]["_panel"]["settings"]["schematic"]
        self.assertEqual(stored["published"], old)
        await self.send("publish", 2, draft)
        self.assertEqual(self.error_code(), "invalid_schematic")

    async def test_admin_and_disabled_view(self):
        self.connection.user.is_admin = False
        await self.send()
        self.assertEqual(self.error_code(), "unauthorized")
        self.connection.user.is_admin = True
        await self.send("publish")
        await self.send("disable", 1)
        stored = self.hass.data["r290_heatpump"]["_panel"]["settings"]["schematic"]
        self.assertIsNone(stored["published"])
        self.assertIsNotNone(stored["draft"])
        self.hass.services.async_call.assert_not_awaited()

    async def test_legacy_settings_preserve_graph_and_mapped_history(self):
        await self.send("publish")
        expected = deepcopy(self.hass.data["r290_heatpump"]["_panel"]["settings"]["schematic"])
        await panel.ws_settings(self.hass, self.connection, {"id": 2, "settings": {"name": "Test"}})
        self.assertEqual(self.hass.data["r290_heatpump"]["_panel"]["settings"]["schematic"], expected)
        self.assertIn("binary_sensor.wp1", panel._allowed_history(self.hass))
