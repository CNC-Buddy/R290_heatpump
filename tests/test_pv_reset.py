"""Regression coverage for the published PV reset behavior after merging."""
import asyncio
import types
import unittest

import test_shared_connection as fixture


class PvResetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.entry = fixture.Entry("curve", "heating_curve", outdoor_sensor="sensor.out")
        self.entry.options = {
            "pv_enabled": True,
            "pv_power_sensor": "sensor.export",
            "pv_offset_reset_kw": 0.6,
            "pv_grid_threshold_min_kw": 2.0,
            "pv_grid_threshold_max_kw": 3.0,
            "pv_grid_offset_min": 2.0,
            "pv_grid_offset_max": 5.0,
            "pv_hold_minutes": 2,
        }
        self.hass = fixture.Hass([self.entry])
        self.curve = fixture.curve_module.R290HeatPumpTemperatureCurveSensor(
            self.hass, self.entry, {}, None
        )

    def export(self, kw, unit="kW"):
        self.hass.states["sensor.export"] = types.SimpleNamespace(
            state=str(kw), attributes={"unit_of_measurement": unit}
        )

    def offset(self, *, commit=True):
        return self.curve._compute_pv_offset(35.0, 25.0, 50.0, commit=commit)

    def expire_hold(self):
        self.curve._pv_candidate_since = asyncio.get_running_loop().time() - 121

    async def asyncTearDown(self):
        await self.curve.async_will_remove_from_hass()

    async def test_custom_reset_threshold_and_watts_conversion(self):
        self.curve._pv_current_offset = 4.0
        self.export(500, "W")
        self.assertEqual(self.offset(commit=False), 0.0)
        self.assertEqual(self.curve._pv_current_offset, 4.0)
        self.export(0.6)
        self.assertEqual(self.offset(commit=False), 4.0)
        self.export(1.5)
        self.assertEqual(self.offset(commit=False), 4.0)
        self.export(2.5)
        self.assertEqual(self.offset(commit=False), 3.5)

    async def test_positive_and_negative_offsets_reset_only_after_hold(self):
        for current in (4.0, -4.0):
            with self.subTest(current=current):
                self.curve._pv_current_offset = current
                self.curve._pv_last_candidate = None
                self.export(0.5)
                self.assertEqual(self.offset(), current)
                self.assertEqual(self.curve._pv_pending_offset, 0.0)
                self.assertGreater(self.curve._pv_hold_remaining, 0)
                self.expire_hold()
                self.assertEqual(self.offset(), 0.0)
                self.assertIsNone(self.curve._pv_pending_offset)

    async def test_recovering_export_cancels_pending_reset(self):
        self.curve._pv_current_offset = 5.0
        self.export(0.1)
        self.assertEqual(self.offset(), 5.0)
        self.expire_hold()
        self.export(3.5)
        self.assertEqual(self.offset(), 5.0)
        self.assertIsNone(self.curve._pv_pending_offset)
        self.export(0.1)
        self.assertEqual(self.offset(), 5.0)
        self.assertGreater(self.curve._pv_hold_remaining, 119)

    async def test_zero_hold_resets_immediately_and_disabled_pv_clears_pending(self):
        self.curve._pv_current_offset = 5.0
        self.entry.options["pv_hold_minutes"] = 0
        self.export(0.1)
        self.assertEqual(self.offset(), 0.0)
        self.entry.options["pv_hold_minutes"] = 2
        self.curve._pv_current_offset = 5.0
        self.curve._pv_last_candidate = None
        self.assertEqual(self.offset(), 5.0)
        self.entry.options["pv_enabled"] = False
        self.assertEqual(self.offset(), 0.0)
        self.assertIsNone(self.curve._pv_pending_offset)

    async def test_battery_rule_remains_active_when_grid_offset_resets(self):
        self.entry.options.update(pv_battery_sensor="sensor.battery", pv_battery_offset=-3)
        self.hass.states["sensor.battery"] = types.SimpleNamespace(state="20", attributes={})
        self.export(0.1)
        self.assertEqual(self.offset(), -3.0)


if __name__ == "__main__":
    unittest.main()
