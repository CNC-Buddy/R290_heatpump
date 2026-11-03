"""Execute the actual register sensor class with an isolated HA base-class double.

No device or HA services are involved. Definitions come from the shipped source;
AST isolation avoids importing unrelated COP/recorder platforms into this test.
"""
import ast
from enum import Enum
import importlib.util
import logging
from pathlib import Path
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/r290_heatpump"
spec = importlib.util.spec_from_file_location("sensor_catalog_fixture", ROOT / "scripts/register_catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)
DEFINITIONS = catalog.definitions()


class EntityCategory(str, Enum):
    DIAGNOSTIC = "diagnostic"
    CONFIG = "config"


tree = ast.parse((COMPONENT / "sensor.py").read_text(encoding="utf-8-sig"))
sensor_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "R290HeatPumpModbusSensor")
namespace = {
    "SensorEntity": object,
    "SensorStateClass": types.SimpleNamespace(MEASUREMENT="measurement", TOTAL="total", TOTAL_INCREASING="total_increasing"),
    "EntityCategory": EntityCategory, "STATE_ON": "on", "STATE_OFF": "off",
    "slugify": lambda name: name.lower().replace(" ", "_"),
    "_LOGGER": logging.getLogger(__name__),
}
exec(compile(ast.Module(body=[sensor_class], type_ignores=[]), str(COMPONENT / "sensor.py"), "exec"), namespace)
Sensor = namespace["R290HeatPumpModbusSensor"]


def definition(suffix):
    return next(dict(d) for d in DEFINITIONS if d.get("unique_id") == "r290_heatpump_" + suffix)


class RegisterSensorTests(unittest.IsolatedAsyncioTestCase):
    def sensor(self, info=None, **changes):
        data = {"device_class": None, "unit": "°C", **(info or definition("low_pressure_saturation_temperature")), **changes}
        cache = Mock()
        entity = Sensor(None, None, data, 1, 30, None, {}, cache)
        return entity, cache

    async def test_temperature_crosses_zero_without_unsigned_spikes(self):
        for suffix in ("low_pressure_saturation_temperature", "high_pressure_saturation_temperature"):
            entity, cache = self.sensor(definition(suffix))
            for raw, expected in [(5, 5), (0, 0), (65535, -1), (65531, -5), (65486, -50), (1, 1)]:
                with self.subTest(sensor=suffix, raw=raw):
                    cache.get_cached.return_value = raw
                    await entity.async_update()
                    self.assertEqual(entity.state, expected)
                    self.assertTrue(entity._attr_available)
                    self.assertEqual(cache.get_cached.return_value, raw)

    async def test_signed_boundaries_and_scaling_order(self):
        entity, cache = self.sensor(scale=.1)
        for raw, expected in [(0x7FFF, 3276.7), (0x8000, -3276.8), (0xFFFF, -.1), (-1, -.1)]:
            with self.subTest(raw=raw):
                cache.get_cached.return_value = raw
                await entity.async_update()
                self.assertEqual(entity.state, expected)

    async def test_unsigned_and_unspecified_datatypes_keep_unsigned_values(self):
        for specified in (True, False):
            data = definition("low_pressure_saturation_temperature")
            if specified:
                data["data_type"] = "uint16"
            else:
                del data["data_type"]
            entity, cache = self.sensor(data)
            cache.get_cached.return_value = 65535
            await entity.async_update()
            self.assertEqual(entity.state, 65535)

    async def test_bit_sensors_ignore_numeric_transformations(self):
        for changes, expected in [({"bit": 15}, "on"), ({"bit_labels": {15: "Alarm"}}, "Alarm"), ({"bitfield": True}, "Bits: 15")]:
            with self.subTest(changes=changes):
                entity, cache = self.sensor(scale=-1, offset=100, **changes)
                cache.get_cached.return_value = 0x8000
                await entity.async_update()
                self.assertEqual(entity.state, expected)

    async def test_missing_cache_marks_unavailable_and_recovers(self):
        entity, cache = self.sensor()
        for raw, expected, available in [(65535, -1, True), (None, -1, False), (3, 3, True)]:
            cache.get_cached.return_value = raw
            await entity.async_update()
            self.assertEqual(entity.state, expected)
            self.assertEqual(entity._attr_available, available)

    async def test_pump_percent_endpoints_and_midpoint_preserve_pwm(self):
        percent, cache = self.sensor(definition("pump_speed_percent"))
        raw_sensor, _ = self.sensor(definition("pump_speed_pwm"))
        raw_sensor._batch = cache
        for raw, expected in [(100, 0), (35, 65), (50, 50), (0, 100)]:
            with self.subTest(raw=raw):
                cache.get_cached.return_value = raw
                await percent.async_update()
                await raw_sensor.async_update()
                self.assertEqual(percent.state, expected)
                self.assertEqual(raw_sensor.state, raw)
                self.assertTrue(percent._attr_available)
        self.assertEqual(percent.unit_of_measurement, "%")
        self.assertIsNone(percent._attr_device_class)
        self.assertIsNone(raw_sensor._attr_device_class)
        self.assertNotEqual(percent.unique_id, raw_sensor.unique_id)
        self.assertNotEqual(percent.entity_id, raw_sensor.entity_id)
        self.assertEqual(raw_sensor._attr_entity_category, EntityCategory.DIAGNOSTIC)

    async def test_invalid_pwm_is_unavailable_not_a_fabricated_off_or_full_speed(self):
        entity, cache = self.sensor(definition("pump_speed_percent"))
        for raw in (101, 65535, -1):
            with self.subTest(raw=raw):
                cache.get_cached.return_value = raw
                await entity.async_update()
                self.assertFalse(entity._attr_available)
                self.assertIsNone(entity.state)
        cache.get_cached.return_value = 35
        await entity.async_update()
        self.assertTrue(entity._attr_available)
        self.assertEqual(entity.state, 65)

    async def test_both_pump_displays_subscribe_to_same_existing_register(self):
        for suffix in ("pump_speed_pwm", "pump_speed_percent"):
            entity, cache = self.sensor(definition(suffix))
            await entity.async_added_to_hass()
            cache.register.assert_called_once_with(0x0057, 30)
            cache.subscribe.assert_called_once_with(entity, 30)


if __name__ == "__main__":
    unittest.main()
