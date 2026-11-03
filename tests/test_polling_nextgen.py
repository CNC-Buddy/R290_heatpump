"""Deterministic scheduler tests: no hardware, sockets or wall-clock sleeps."""

import asyncio
import importlib
import unittest
from unittest.mock import AsyncMock
import test_shared_connection as base

Scheduler = importlib.import_module("r290_under_test.polling.scheduler").Scheduler
profiles = importlib.import_module("r290_under_test.polling.profiles")
models = importlib.import_module("r290_under_test.polling.models")


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, n=1):
        self.now += n


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.memory = {}
        self.calls = []
        self.read_error = None
        self.write_fail = False

        async def read(unit, start, count):
            self.calls.append(("read", unit, start, count))
            self.clock.advance(0.05)
            if self.read_error:
                raise self.read_error
            return [self.memory.get((unit, a), 0) for a in range(start, start + count)]

        async def write(unit, address, value):
            self.calls.append(("write", unit, address, value))
            self.memory[unit, address] = value
            self.clock.advance(0.05)
            if self.write_fail:
                raise TimeoutError("ack lost")

        self.s = Scheduler(
            read,
            write,
            {"polling_profile": "auto", "block_size": 10, "block_pause": 0},
            clock=self.clock,
            utc=lambda: str(self.clock()),
            start_worker=False,
        )

    async def asyncTearDown(self):
        await self.s.stop()

    async def execute(self, awaitable):
        task = asyncio.create_task(awaitable)
        await asyncio.sleep(0)
        self.clock.advance(5)
        await self.s.run_once()
        return await task

    async def test_deduplicates_owners_intervals_without_reading_holes(self):
        self.s.register("a", 1, 0x40, 30)
        self.s.register("b", 1, 0x40, 10)
        self.s.register("a", 1, 0x42, 30)
        await self.s.run_once()
        self.assertEqual(self.calls, [("read", 1, 0x40, 1)])
        self.assertEqual(self.s.demands[1, 0x40].interval, 10)
        self.assertEqual(self.s.get(1, 0x40), 0)
        self.s.unregister("b")
        self.assertEqual(self.s.demands[1, 0x40].interval, 10)

    async def test_duplicate_pending_reads_share_one_request(self):
        tasks = [
            asyncio.create_task(self.s.read(1, 0x40, 2, owner=o)) for o in ("a", "b")
        ]
        await asyncio.sleep(0)
        self.assertEqual(len(self.s.jobs), 1)
        self.s.unregister("a")
        await self.s.run_once()
        self.assertEqual(await asyncio.gather(*tasks), [[0, 0], [0, 0]])
        self.assertEqual(len(self.calls), 1)

    async def test_fairness_between_units_and_aging_for_diagnostics(self):
        for unit in (1, 2):
            for addr in range(0, 15):
                self.s.register(str(unit), unit, addr, 10)
        await self.s.run_once()
        self.clock.advance(1)
        await self.s.run_once()
        self.assertEqual([c[1] for c in self.calls], [1, 2])
        task = asyncio.create_task(self.s.read(2, 0xE0, 1, priority=4))
        await asyncio.sleep(0)
        self.clock.advance(80)
        await self.s.run_once()
        for _ in range(8):
            if task.done():
                break
            self.clock.advance(1)
            await self.s.run_once()
        self.assertIn(("read", 2, 0xE0, 1), self.calls)
        await asyncio.wait_for(task, 0.1)

    async def test_successful_constant_sample_is_fresh_and_failure_is_not(self):
        self.s.register("a", 1, 0x40, 10, max_age=30)
        await self.s.run_once()
        first = self.s.observations(1)["64"].copy()
        self.clock.advance(10)
        await self.s.run_once()
        second = self.s.observations(1)["64"].copy()
        self.assertNotEqual(first["received_at"], second["received_at"])
        self.assertEqual(first["changed_at"], second["changed_at"])
        self.read_error = TimeoutError("offline")
        self.clock.advance(10)
        await self.s.run_once()
        third = self.s.observations(1)["64"]
        self.assertEqual(third["received_at"], second["received_at"])
        self.assertIsNone(self.s.get(1, 0x40))

    async def test_idle_expiration_notifies_consumers(self):
        changed = []
        self.s.subscribe("a", lambda: changed.append(self.clock()))
        self.s.register("a", 1, 0x40, 10, max_age=15)
        await self.s.run_once()
        self.s.demands[1, 0x40].due = 1000
        self.clock.advance(16)
        await self.s.run_once()
        self.assertEqual(len(changed), 2)
        self.assertIsNone(self.s.get(1, 0x40))

    async def test_illegal_address_splits_but_timeout_does_not(self):
        for addr in range(0x42, 0x46):
            self.s.register("a", 1, addr, 10)
        self.read_error = TimeoutError("offline")
        await self.s.run_once()
        self.assertNotIn(1, self.s.limits)
        self.assertGreater(self.s.backoff[1], self.clock())
        self.clock.advance(20)
        self.read_error = models.RegisterAddressError("02")
        await self.s.run_once()
        self.assertEqual(self.s.limits[1], 2)
        self.clock.advance(20)
        await self.s.run_once()
        self.assertEqual(self.s.limits[1], 1)
        self.clock.advance(20)
        await self.s.run_once()
        self.assertEqual(self.calls[-1][-1], 1)
        self.assertGreater(
            self.s.demands[1, self.calls[-1][2]].blocked_until, self.clock()
        )

    async def test_writes_have_readback_and_lost_ack_is_never_retried(self):
        self.write_fail = True
        self.assertEqual(await self.execute(self.s.write(1, 0x301, 44)), [44])
        self.assertEqual(self.calls, [("write", 1, 0x301, 44), ("read", 1, 0x301, 1)])
        self.assertEqual(self.s.verified_writes, 1)

    async def test_failed_verification_does_not_claim_success(self):
        self.read_error = TimeoutError("readback offline")
        with self.assertRaises(models.WriteVerificationError):
            await self.execute(self.s.write(1, 0x301, 40))
        self.assertEqual(self.s.verified_writes, 0)
        self.assertEqual(len([c for c in self.calls if c[0] == "write"]), 1)

    async def test_unload_rejects_queued_write_before_transport(self):
        task = asyncio.create_task(self.s.write(1, 0x301, 40, owner="curve"))
        await asyncio.sleep(0)
        self.s.unregister("curve")
        with self.assertRaisesRegex(RuntimeError, "unloaded"):
            await task
        await self.s.run_once()
        self.assertEqual(self.calls, [])

    async def test_cancelled_queued_write_never_actuates(self):
        task = asyncio.create_task(self.s.write(1, 0x301, 40, owner="curve"))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await self.s.run_once()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.s.jobs, [])

    async def test_expired_write_never_actuates(self):
        task = asyncio.create_task(self.s.write(1, 0x301, 40))
        await asyncio.sleep(0)
        self.clock.advance(31)
        await self.s.run_once()
        with self.assertRaises(TimeoutError):
            await task
        self.assertEqual(self.calls, [])

    async def test_queue_bound_and_shutdown_resolve_all_callers(self):
        tasks = [asyncio.create_task(self.s.read(1, a, 1)) for a in range(129)]
        await asyncio.sleep(0)
        self.assertEqual(len(self.s.jobs), 128)
        await self.s.stop()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self.assertTrue(all(isinstance(r, RuntimeError) for r in results))
        self.assertTrue(any("full" in str(r) for r in results))

    async def test_budget_causes_idle_time_and_control_deadlines_do_not_expand(self):
        self.s.register("a", 1, 0x40, 10, max_age=30)
        await self.s.run_once()
        self.assertGreater(self.s._next_io, self.clock())
        self.s.slowdown[1] = 4
        self.assertEqual(self.s.demands[1, 0x40].interval, 10)
        self.assertEqual(self.s.demands[1, 0x40].max_age, 30)

    def test_known_word_pairs_and_gaps(self):
        self.assertEqual(list(profiles.blocks([0xE5, 0xE6], 1)), [(0xE5, 2)])
        self.assertEqual(
            list(profiles.blocks([0xEB, 0xEC, 0xED, 0xF0], 2)),
            [(0xEB, 1), (0xEC, 2), (0xF0, 1)],
        )
        self.assertEqual(list(profiles.blocks([10, 11], 1)), [(10, 1), (11, 1)])

    def test_invalid_config_is_rejected(self):
        for values in (
            {"poll_fast": float("nan")},
            {"poll_budget": 1},
            {"poll_fast": 50, "poll_normal": 10},
            {"polling_profile": "turbo"},
        ):
            with self.assertRaises(ValueError):
                profiles.settings(values)

    async def test_unsupported_word_pair_is_quarantined_together(self):
        self.s.register("a", 1, 0xE5, 30)
        self.s.register("a", 1, 0xE6, 30)
        self.read_error = models.RegisterAddressError("02")
        await self.s.run_once()
        self.assertEqual(self.calls, [("read", 1, 0xE5, 2)])
        for address in (0xE5, 0xE6):
            self.assertGreater(self.s.demands[1, address].blocked_until, self.clock())


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_switch_recreates_legacy_client_without_protocol_retries(
        self,
    ):
        hub = base.hub_module.R290HeatPumpModbusHub(
            "gateway", mode="tcp", connect_retries=0
        )
        await hub.async_connect()
        old = hub._client
        await hub.configure_polling({"polling_profile": "auto"})
        self.assertTrue(old.closed)
        await hub.async_connect()
        self.assertEqual(hub._client.kwargs["retries"], 0)
        self.assertEqual(hub._client.kwargs["reconnect_delay"], 0)
        await hub.async_close()

    async def test_legacy_default_and_auto_routing_share_transport(self):
        hub = base.hub_module.R290HeatPumpModbusHub(
            "gateway", mode="tcp_proxy", connect_retries=0
        )
        self.assertIsNone(hub.scheduler)
        await hub.configure_polling({"polling_profile": "auto", "block_pause": 0})
        hub._read_transport = AsyncMock(return_value=[12])
        # The scheduler captured the bound transport function: exercise actual
        # proxy transport using Client's predictable zero-register response.
        await hub.async_pb_write_register(1, 0x301, 0)
        self.assertEqual(hub.scheduler.verified_writes, 1)
        self.assertEqual(hub._client, None)
        self.assertGreaterEqual(hub.metrics.snapshot()["transactions_last_minute"], 2)
        await hub.async_close()
        self.assertIsNone(hub.scheduler.worker)

    async def test_migration_is_additive_and_idempotent(self):
        entry = base.Entry(
            "bridge",
            "modbus_bridge",
            host="proxy",
            scan_interval=30,
            long_scan_interval=600,
        )
        entry.version = 1
        entry.minor_version = 1
        hass = base.Hass([entry])
        calls = []

        def update(e, **values):
            calls.append(values)
            for k, v in values.items():
                setattr(e, k, v)

        hass.config_entries.async_update_entry = update
        await base.integration.async_migrate_entry(hass, entry)
        await base.integration.async_migrate_entry(hass, entry)
        self.assertEqual(len(calls), 1)
        self.assertEqual(entry.data["polling_profile"], "legacy")
        self.assertEqual(
            (entry.data["scan_interval"], entry.data["long_scan_interval"]), (30, 600)
        )
