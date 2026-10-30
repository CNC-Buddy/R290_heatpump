"""Check existing local COP additions before including them in the release."""
import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import test_shared_connection as fixture


class Store:
    def __init__(self, *args):
        self.async_load = AsyncMock(return_value=None)
        self.async_save = AsyncMock()


class Clock:
    current = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


const = sys.modules["homeassistant.const"]
const.STATE_OFF = "off"
const.EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"
const.UnitOfEnergy = types.SimpleNamespace(KILO_WATT_HOUR="kWh")
fixture.module("homeassistant.helpers.entity", EntityCategory=types.SimpleNamespace(DIAGNOSTIC="diagnostic"))
fixture.module("homeassistant.helpers.storage", Store=Store)
fixture.module("homeassistant.util", dt=types.SimpleNamespace(
    now=lambda: Clock.current, utcnow=lambda: Clock.current, as_local=lambda value: value,
))
cop = importlib.import_module("r290_under_test.cop_calculator")


class CopAccumulatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Clock.current = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
        self.hass = fixture.Hass([])
        self.acc = cop._EnergyAccumulator(self.hass, "sensor.energy", "sensor.heat", True, "binary_sensor.hotwater")

    def meters(self, energy, heat, mode="off"):
        for key, value in (("sensor.energy", energy), ("sensor.heat", heat), ("binary_sensor.hotwater", mode)):
            self.hass.states[key] = types.SimpleNamespace(state=str(value), attributes={})

    async def test_split_deltas_and_overall_totals(self):
        self.meters(100, 200)
        await self.acc.async_update()
        Clock.current += timedelta(minutes=5)
        self.meters(102, 206)
        await self.acc.async_update()
        Clock.current += timedelta(minutes=5)
        self.meters(103, 209, "on")
        await self.acc.async_update()
        for kind, expected in (("energy", 3), ("heat", 9), ("energy_heating", 2),
                               ("heat_heating", 6), ("energy_hotwater", 1), ("heat_hotwater", 3)):
            self.assertEqual(self.acc.get_value(kind, "overall"), expected)

    async def test_old_storage_keeps_existing_totals(self):
        self.acc._store.async_load.return_value = {"sources": {
            "energy": {"last": 100, "buckets": {"2026-10-29": 5}},
            "heat": {"last": 200, "buckets": {"2026-10-29": 15}},
        }}
        self.meters(101, 203)
        await self.acc.async_update()
        self.assertEqual(self.acc.get_value("energy", "overall"), 6)
        self.assertEqual(self.acc.get_value("heat", "overall"), 18)
        self.assertEqual(self.acc.get_value("heat", "yesterday"), 15)

    async def test_delayed_heat_delta_is_distributed_across_midnight(self):
        Clock.current = datetime(2026, 10, 29, 23, tzinfo=timezone.utc)
        self.meters(100, 200)
        await self.acc.async_update()
        Clock.current += timedelta(hours=2)
        self.meters(101, 204)
        await self.acc.async_update()
        self.assertEqual(self.acc.get_value("heat", "yesterday"), 2)
        self.assertEqual(self.acc.get_value("heat", "today"), 2)
        self.assertEqual(self.acc.get_value("heat_heating", "overall"), 4)

    async def test_storage_round_trip_preserves_split_buckets(self):
        self.meters(100, 200, "on")
        await self.acc.async_update()
        Clock.current += timedelta(minutes=5)
        self.meters(101, 203, "on")
        await self.acc.async_update()
        saved = self.acc._store.async_save.call_args.args[0]
        restored = cop._EnergyAccumulator(self.hass, "sensor.energy", "sensor.heat", True, "binary_sensor.hotwater")
        restored._store.async_load.return_value = saved
        await restored.async_update()
        self.assertEqual(restored.get_value("energy_hotwater", "overall"), 1)
        self.assertEqual(restored.get_value("heat_hotwater", "overall"), 3)


if __name__ == "__main__":
    unittest.main()
