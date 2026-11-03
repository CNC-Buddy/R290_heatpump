"""Loopback transport checks with real pymodbus (no Home Assistant/device needed).

Run separately from the HA-double suite: python tests/proxy_transport_checks.py
Requires the pymodbus version from manifest.json. All traffic stays on 127.0.0.1.
"""
import asyncio
import importlib.util
import logging
from pathlib import Path
import struct
import sys
import types
import unittest


class Coordinator:
    @classmethod
    def __class_getitem__(cls, item):
        return cls


for name, attrs in {
    "homeassistant": {}, "homeassistant.helpers": {},
    "homeassistant.helpers.update_coordinator": {"DataUpdateCoordinator": Coordinator},
    "homeassistant.core": {"HomeAssistant": object},
}.items():
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module

component = Path(__file__).parents[1] / "custom_components/r290_heatpump"
package = types.ModuleType("transport_under_test")
package.__path__ = [str(component)]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location(
    "transport_under_test.hub", component / "hub.py"
)
hub_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub_module)


def crc(data):
    value = 0xffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ 0xa001 if value & 1 else value >> 1
    return struct.pack("<H", value)


class TransportChecks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tasks = set()
        self.writers = set()
        self.requests = []
        self.memory = {}
        self.connection_count = 0
        self.fault = None
        self.fixed_id = True
        self.rtu = False
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.hub = hub_module.R290HeatPumpModbusHub(
            "127.0.0.1", self.server.sockets[0].getsockname()[1], "tcp_proxy",
            connect_retries=0, request_timeout=.15,
        )

    async def asyncTearDown(self):
        await self.hub.async_close()
        self.server.close()
        await self.server.wait_closed()
        for writer in list(self.writers):
            writer.close()
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.writers.add(writer)
        self.connection_count += 1
        connection = self.connection_count
        try:
            while True:
                if self.rtu:
                    frame = await reader.readexactly(8)
                    assert crc(frame[:6]) == frame[6:]
                    data, tid = frame[:6], b"\x00\x00"
                else:
                    header = await reader.readexactly(6)
                    assert header[2:4] == b"\x00\x00"
                    data = await reader.readexactly(int.from_bytes(header[4:6], "big"))
                    tid = header[:2]
                unit, function, address, value = struct.unpack(">BBHH", data)
                self.requests.append((connection, tid, unit, function, address, value))
                if function == 6:
                    self.memory[unit, address] = value
                fault, self.fault = self.fault, None
                if fault == "timeout":
                    continue
                if fault == "delayed":
                    await asyncio.sleep(.3)
                if fault == "exception":
                    payload = bytes([unit, function | 0x80, 2])
                elif fault == "broken_exception":
                    payload = bytes([unit, function | 0x80])
                elif function == 3:
                    count = value - 1 if fault == "short" else value
                    payload = bytes([unit, function, count * 2]) + b"".join(
                        struct.pack(">H", self.memory.get((unit, address+i), address+i)) for i in range(count)
                    )
                elif function == 6:
                    payload = struct.pack(">BBHH", unit, function, address,
                                          value + 1 if fault == "wrong_echo" else value)
                else:
                    raise AssertionError(f"Unexpected function {function}")
                if fault == "wrong_unit":
                    payload = bytes([unit + 1]) + payload[1:]
                if self.rtu:
                    reply = payload + crc(payload)
                else:
                    reply_id = b"\x00\x02" if fault == "wrong_id" else (b"\x00\x01" if self.fixed_id else tid)
                    reply = reply_id + b"\x00\x00" + struct.pack(">H", len(payload)) + payload
                writer.write(reply)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.writers.discard(writer)
            self.tasks.discard(task)

    async def test_fixed_id_proxy_reads_and_writes_multiple_slaves(self):
        for unit, address in ((1, 0), (2, 0x4a), (1, 0x301), (2, 0)):
            self.assertEqual(await self.hub.async_read_block(unit, address, 3),
                             [address, address + 1, address + 2])
        await self.hub.async_pb_write_register(2, 0x301, 35)
        self.assertEqual(len(self.requests), 5)
        self.assertEqual(len({r[0] for r in self.requests}), 5)
        self.assertTrue(all(r[1] == b"\x00\x01" for r in self.requests))
        self.assertIsNone(self.hub._client)
        self.assertEqual(self.hub.communication_status, "Connected")

    async def test_persistent_tcp_still_reuses_socket_and_validates_transaction_ids(self):
        self.hub._mode = "tcp"
        self.fixed_id = False
        for address in (0, 10, 20):
            self.assertEqual(await self.hub.async_read_block(1, address, 1), [address])
        self.assertEqual(self.connection_count, 1)
        self.assertEqual([r[1] for r in self.requests], [b"\x00\x01", b"\x00\x02", b"\x00\x03"])

    async def test_direct_rtu_still_reuses_socket(self):
        self.hub._mode = "rtuovertcp"
        self.rtu = True
        self.assertEqual(await self.hub.async_read_block(1, 0, 3), [0, 1, 2])
        self.assertEqual(await self.hub.async_read_block(2, 74, 1), [74])
        await self.hub.async_pb_write_register(2, 0x301, 35)
        self.assertEqual(self.connection_count, 1)

    async def test_rejects_wrong_ids_short_data_and_broken_exceptions(self):
        for fault in ("wrong_id", "wrong_unit", "short", "exception", "broken_exception"):
            with self.subTest(fault=fault):
                self.fault = fault
                result = await self.hub.async_pb_call(1, 0, 3, "holding")
                self.assertTrue(result.isError())
                self.assertEqual(self.hub.communication_status, "Error")
                self.assertIsNone(self.hub._client)
                self.assertEqual(await self.hub.async_read_block(2, 74, 1), [74])
                self.assertEqual(self.hub.communication_status, "Connected")

    async def test_failed_write_is_not_retried(self):
        for fault in ("timeout", "wrong_echo"):
            with self.subTest(fault=fault):
                before = len(self.requests)
                self.fault = fault
                with self.assertRaises(RuntimeError):
                    await self.hub.async_pb_write_register(1, 0x301, 35)
                self.assertEqual(len(self.requests), before + 1)
                self.assertEqual(self.hub.communication_status, "Error")

    async def test_late_reply_cannot_satisfy_next_request(self):
        self.fault = "delayed"
        result = await self.hub.async_pb_call(1, 0, 1, "holding")
        self.assertTrue(result.isError())
        self.assertEqual(await self.hub.async_read_block(1, 74, 1), [74])
        self.assertEqual(len(self.requests), 2)
        self.assertNotEqual(self.requests[0][0], self.requests[1][0])

    async def test_socket_connect_alone_does_not_report_modbus_success(self):
        await self.hub.async_connect()
        self.assertTrue(self.hub.diagnostics["socket_connected"])
        self.assertEqual(self.hub.communication_status, "Not checked")
        self.assertIsNone(self.hub.diagnostics["last_response"])

    async def test_auto_lost_write_ack_verified_over_new_socket_without_retry(self):
        await self.hub.configure_polling({"polling_profile": "auto", "block_pause": 0})
        self.fault = "timeout"
        await self.hub.async_pb_write_register(2, 0x301, 35)
        self.assertEqual([(r[2], r[3], r[4]) for r in self.requests],
                         [(2, 6, 0x301), (2, 3, 0x301)])
        self.assertEqual(self.connection_count, 2)
        self.assertTrue(all(r[1] == b"\x00\x01" for r in self.requests))
        self.assertEqual(self.hub.scheduler.verified_writes, 1)

    async def test_auto_two_units_and_duplicate_callers_use_single_worker(self):
        await self.hub.configure_polling({"polling_profile": "auto", "block_pause": 0})
        answers = await asyncio.gather(
            self.hub.async_read_block(1, 74, 2),
            self.hub.async_read_block(2, 74, 2),
            self.hub.async_read_block(1, 74, 2),
        )
        self.assertEqual(answers, [[74, 75]] * 3)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.connection_count, 2)

    async def test_auto_persistent_transports_do_not_retry_lost_write_ack(self):
        for mode in ('tcp','rtuovertcp'):
            with self.subTest(mode=mode):
                self.rtu = mode == 'rtuovertcp'
                self.fixed_id = False
                await self.hub.async_reconfigure('127.0.0.1', self.server.sockets[0].getsockname()[1], mode,
                    connect_timeout=1, connect_retries=0, request_timeout=.15)
                await self.hub.configure_polling({'polling_profile':'auto','block_pause':0})
                before = len(self.requests)
                self.fault = 'timeout'
                await self.hub.async_pb_write_register(1, 0x301, 41)
                self.assertEqual([r[3] for r in self.requests[before:]],[6,3])

    async def test_auto_illegal_address_preserves_typed_error(self):
        await self.hub.configure_polling({"polling_profile": "auto", "block_pause": 0})
        self.fault = "exception"
        with self.assertRaises(hub_module.RegisterAddressError):
            await self.hub.async_read_block(1, 0, 4)
        self.assertEqual(self.hub.scheduler.limits[1], 2)

    async def test_reconnect_resets_error_and_checks_a_new_socket_in_every_mode(self):
        for mode in ("rtuovertcp", "tcp", "tcp_proxy"):
            with self.subTest(mode=mode):
                self.hub._mode = mode
                self.rtu = mode == "rtuovertcp"
                self.fixed_id = mode == "tcp_proxy"
                await self.hub.async_reconnect()
                self.fault = "short"
                result = await self.hub.async_pb_call(1, 0, 3, "holding")
                self.assertTrue(result.isError())
                self.assertEqual(self.hub.communication_status, "Error")
                before = self.connection_count
                await self.hub.async_reconnect()
                self.assertEqual(self.hub.communication_status, "Not checked")
                self.assertIsNone(self.hub.diagnostics["last_error"])
                self.assertEqual(await self.hub.async_read_block(2, 74, 1), [74])
                self.assertGreater(self.connection_count, before)
                self.assertEqual(self.hub.communication_status, "Connected")


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)
    unittest.main(verbosity=2)
