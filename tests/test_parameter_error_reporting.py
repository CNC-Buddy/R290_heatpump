"""Execute the actual write methods, isolated from unrelated HA platforms."""
import ast
import logging
from pathlib import Path
import types
import unittest
from unittest.mock import AsyncMock, Mock

import test_shared_connection as fixture
from homeassistant.exceptions import HomeAssistantError

ROOT = Path(__file__).resolve().parents[1] / "custom_components/r290_heatpump"


def method(filename, classname, methodname):
    module = ast.parse((ROOT / filename).read_text(encoding="utf-8-sig"))
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == classname)
    fn = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == methodname)
    fn.decorator_list = []
    namespace = {"HomeAssistantError": HomeAssistantError, "_LOGGER": logging.getLogger(__name__)}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), filename, "exec"), namespace)
    return namespace[methodname]


class WriteErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_number_failure_reaches_caller_and_preserves_previous_value(self):
        entity = types.SimpleNamespace(_name="P099", _scale=1, _data_type="int16", _slave_id=1,
            _address=355, _attr_native_value=3, _batch=None,
            _hub=types.SimpleNamespace(async_pb_write_register=AsyncMock(side_effect=RuntimeError("offline"))))
        setter = method("number.py", "R290HeatPumpModbusNumber", "async_set_native_value")
        with self.assertRaises(HomeAssistantError):
            await setter(entity, 5)
        self.assertEqual(entity._attr_native_value, 3)

    async def test_failed_switch_off_does_not_claim_off_or_schedule_retries(self):
        entity = types.SimpleNamespace(_attr_is_on=True, _off_value=0,
            _cancel_auto_off=Mock(), _write_register=AsyncMock(side_effect=RuntimeError("offline")),
            async_write_ha_state=Mock(), _start_off_enforcer=Mock())
        setter = method("switch.py", "R290HeatPumpWaterCirculationSwitch", "async_turn_off")
        with self.assertRaises(HomeAssistantError):
            await setter(entity)
        self.assertTrue(entity._attr_is_on)
        entity._start_off_enforcer.assert_not_called()

    async def test_failed_switch_on_does_not_claim_on(self):
        entity = types.SimpleNamespace(_attr_is_on=False, _on_value=1,
            _cancel_auto_off=Mock(), _stop_off_enforcer=Mock(),
            _write_register=AsyncMock(side_effect=RuntimeError("offline")),
            _ensure_auto_off_task=AsyncMock(), async_write_ha_state=Mock())
        setter = method("switch.py", "R290HeatPumpWaterCirculationSwitch", "async_turn_on")
        with self.assertRaises(HomeAssistantError):
            await setter(entity)
        self.assertFalse(entity._attr_is_on)
        entity._ensure_auto_off_task.assert_not_awaited()
