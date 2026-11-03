# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import asyncio
import inspect
import logging
from .polling.scheduler import Scheduler
from .polling.models import RegisterAddressError
from .polling.profiles import settings as polling_settings
from .polling.metrics import TransportMetrics
from typing import Optional, Dict, List, Set
from datetime import datetime, timedelta, timezone

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant

from pymodbus.client import AsyncModbusTcpClient
try:
    from pymodbus.exceptions import ModbusIOException, ConnectionException, ModbusException  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - fallback if API differs
    class ModbusException(Exception):
        pass
    class ConnectionException(ModbusException):
        pass
    class ModbusIOException(ModbusException):
        pass
try:
    from pymodbus.framer import FramerType  # type: ignore[attr-defined]
    _FRAMER_STYLE = "type"
except Exception:  # pragma: no cover - fallback for other pymodbus variants
    try:
        from pymodbus.framer.rtu_framer import ModbusRtuFramer  # type: ignore[attr-defined]
        from pymodbus.framer.socket_framer import ModbusSocketFramer  # type: ignore[attr-defined]
        _FRAMER_STYLE = "class"
    except Exception:
        FramerType = None  # type: ignore[misc]
        ModbusRtuFramer = None  # type: ignore[misc]
        ModbusSocketFramer = None  # type: ignore[misc]
        _FRAMER_STYLE = "none"

_LOGGER = logging.getLogger(__name__)
CONNECTION_TYPES = ("rtuovertcp", "tcp", "tcp_proxy")


class _ResultWrapper:
    """Wrapper for Modbus results or errors."""

    def __init__(self, registers=None, error: Optional[Exception] = None):
        self.registers = registers or []
        self._error = error

    def isError(self) -> bool:
        return self._error is not None

    def __repr__(self) -> str:
        if self.isError():
            return f"Result(error={self._error})"
        return f"Result(registers={self.registers})"


class R290HeatPumpModbusHub:
    """Async Modbus hub with robust unit/slave handling."""

    _UNIT_ATTR_CANDIDATES = (
        "unit_id",
        "_unit_id",
        "slave_id",
        "_slave_id",
        "unit",
        "_unit",
        "device_id",
        "_device_id",
    )

    def __init__(
        self,
        host: str,
        port: int = 502,
        mode: str = "rtuovertcp",
        *,
        connect_timeout: float = 8.0,  # seconds
        connect_retries: int = 2,
        request_timeout: float = 5.0,  # seconds
    ):
        self._host = host
        self._port = port
        self._mode = mode
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()
        self._connect_timeout = float(connect_timeout)
        self._connect_retries = int(connect_retries)
        self._request_timeout = float(request_timeout)
        self._closed = False
        self._last_request_success: Optional[bool] = None
        self._last_response_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self.scheduler = None
        self.polling_config = polling_settings({})
        self.metrics = TransportMetrics()

    @property
    def communication_status(self) -> str:
        """Describe the last Modbus request, not just an open TCP socket."""
        if self._closed:
            return "Disconnected"
        if self._last_request_success is None:
            return "Not checked"
        return "Connected" if self._last_request_success else "Error"

    @property
    def diagnostics(self) -> dict:
        return {
            "polling": self.polling_diagnostics(),
            "socket_connected": bool(self._client and self._client.connected),
            "last_request_success": self._last_request_success,
            "last_response": self._last_response_at.isoformat() if self._last_response_at else None,
            "last_error": self._last_error,
        }

    def polling_diagnostics(self):
        result = self.scheduler.diagnostics() if self.scheduler else {"profile":"legacy", "running":not self._closed}
        return {**result, "transport":self.metrics.snapshot(), "settings":dict(self.polling_config)}

    async def configure_polling(self, settings):
        config = polling_settings(settings)
        changed = config != self.polling_config
        transport_policy_changed = config["polling_profile"] != self.polling_config["polling_profile"]
        if changed and self.scheduler:
            await self.scheduler.stop()
            self.scheduler = None
        self.polling_config = config
        if transport_policy_changed:
            # A client created by legacy mode may still have protocol retries.
            # Recreate it with the auto profile's single-attempt policy.
            async with self._lock:
                await self._async_close_client_locked()
        if config["polling_profile"] == "auto" and self.scheduler is None:
            self.scheduler = Scheduler(self._read_transport, self._write_transport, settings)
        if self.scheduler:
            self.scheduler.block_size = max(2, min(125, int(settings.get("block_size",49))))
            self.scheduler.pause = float(settings.get("block_pause",.05))
        return changed

    def _apply_unit(self, base: object, unit: Optional[int]) -> None:
        """Propagate unit/slave id to client/protocol objects."""
        if unit is None:
            return
        seen: List[object] = []
        for target in (base, getattr(base, "protocol", None), self._client):
            if target is None or target in seen:
                continue
            seen.append(target)
            for attr in self._UNIT_ATTR_CANDIDATES:
                if hasattr(target, attr):
                    try:
                        setattr(target, attr, unit)
                    except Exception:
                        pass
            for attr_name in ("defaults", "params"):
                sub_target = getattr(target, attr_name, None)
                if sub_target is None or sub_target in seen:
                    continue
                seen.append(sub_target)
                for attr in self._UNIT_ATTR_CANDIDATES:
                    if hasattr(sub_target, attr):
                        try:
                            setattr(sub_target, attr, unit)
                        except Exception:
                            pass

    async def async_connect(self) -> None:
        """Serialize connection establishment with every read and write."""
        async with self._lock:
            await self._async_connect_locked()

    async def _async_close_client_locked(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            result = client.close()
            if inspect.isawaitable(result):
                await result

    async def _async_connect_locked(self) -> None:
        if self._closed:
            raise ConnectionError("Modbus hub has been unloaded")
        if self._mode not in CONNECTION_TYPES:
            raise ValueError(f"Unsupported Modbus connection type: {self._mode}")
        if self._client is not None and getattr(self._client, "connected", False):
            return
        await self._async_close_client_locked()

        primary_framer = None
        if _FRAMER_STYLE == "type":
            primary_framer = FramerType.RTU if self._mode == "rtuovertcp" else FramerType.SOCKET
        elif _FRAMER_STYLE == "class":
            primary_framer = ModbusRtuFramer if self._mode == "rtuovertcp" else ModbusSocketFramer

        last_err: Optional[Exception] = None
        for attempt in range(self._connect_retries + 1):
            try:
                kwargs = {"port": self._port, "timeout": self._request_timeout}
                if self._mode == "tcp_proxy" or self.polling_config["polling_profile"] == "auto":
                    # The scheduler owns retries in auto, for every transport.
                    # In particular a possibly executed write is never replayed.
                    kwargs.update(retries=0, reconnect_delay=0)
                if primary_framer is not None:
                    kwargs["framer"] = primary_framer
                elif self._mode == "rtuovertcp":
                    raise RuntimeError("No RTU framer available")
                self._client = AsyncModbusTcpClient(self._host, **kwargs)
                log_connect = _LOGGER.debug if self._mode == "tcp_proxy" else _LOGGER.info
                log_connect("Connecting Modbus client %s:%s mode=%s (attempt %s)",
                            self._host, self._port, self._mode, attempt + 1)
                ret = await asyncio.wait_for(self._client.connect(), self._connect_timeout)
                if ret or getattr(self._client, "connected", False):
                    return
            except asyncio.CancelledError:
                await self._async_close_client_locked()
                raise
            except Exception as err:
                last_err = err
            await self._async_close_client_locked()
            if attempt < self._connect_retries:
                await asyncio.sleep(0.8)

        raise ConnectionError(
            f"Failed to connect {self._host}:{self._port} mode={self._mode}; last_err={last_err}"
        )

    async def async_close(self) -> None:
        """Retire the hub so stale callbacks cannot reconnect it."""
        if self.scheduler:
            await self.scheduler.stop()
        async with self._lock:
            self._closed = True
            await self._async_close_client_locked()

    async def async_reconnect(self) -> None:
        scheduler = self.scheduler
        try:
            if scheduler:
                await scheduler.quiesce()
            await self._async_reconnect_transport()
        finally:
            if scheduler:
                scheduler.resume(invalidate=True)

    async def _async_reconnect_transport(self) -> None:
        """Reconnect the active shared hub without retiring it."""
        async with self._lock:
            # A new socket has not yet confirmed any Modbus operation. Retain
            # last_response as history, but do not retain an old success/error.
            self._last_request_success = None
            self._last_error = None
            try:
                await self._async_close_client_locked()
                await self._async_connect_locked()
            except asyncio.CancelledError:
                self._last_request_success = False
                self._last_error = "Reconnect cancelled"
                raise
            except Exception as err:
                self._last_request_success = False
                self._last_error = str(err)
                raise

    async def async_reconfigure(self, host, port, mode, *, connect_timeout,
                                connect_retries, request_timeout, validate=False):
        changed=(host,int(port),mode,float(connect_timeout),int(connect_retries),float(request_timeout)) != (self._host,self._port,self._mode,self._connect_timeout,self._connect_retries,self._request_timeout)
        scheduler=self.scheduler if changed else None
        committed=False
        try:
            if scheduler:await scheduler.quiesce()
            result=await self._async_reconfigure_transport(host,port,mode,connect_timeout=connect_timeout,
                connect_retries=connect_retries,request_timeout=request_timeout,validate=validate)
            committed=True
            return result
        finally:
            if scheduler:scheduler.resume(invalidate=committed)

    async def _async_reconfigure_transport(self, host, port, mode, *, connect_timeout,
                                connect_retries, request_timeout, validate=False) -> None:
        """Change the destination for all users while holding the I/O lock."""
        attrs = ("_host", "_port", "_mode", "_connect_timeout", "_connect_retries", "_request_timeout")
        updated = (host, int(port), mode, float(connect_timeout), int(connect_retries), float(request_timeout))
        async with self._lock:
            if self._closed:
                raise ConnectionError("Modbus hub has been unloaded")
            previous = tuple(getattr(self, attr) for attr in attrs)
            if previous == updated:
                if validate:
                    await self._async_connect_locked()
                return
            await self._async_close_client_locked()
            for attr, value in zip(attrs, updated):
                setattr(self, attr, value)
            try:
                if validate:
                    await self._async_connect_locked()
            except BaseException:
                await self._async_close_client_locked()
                for attr, value in zip(attrs, previous):
                    setattr(self, attr, value)
                raise
            self._last_request_success = None
            self._last_response_at = None
            self._last_error = None

    async def async_pb_call(self, unit: int, address: int, count: int, kind: str, *, owner="external", priority=2) -> _ResultWrapper:
        if self.scheduler:
            try:
                if kind == "holding":
                    values = await self.scheduler.read(unit, address, count, priority=priority, owner=owner)
                elif kind == "write_register":
                    values = await self.scheduler.write(unit, address, count, owner=owner)
                else:
                    raise ValueError("Unsupported Modbus operation")
                return _ResultWrapper(registers=values)
            except Exception as err:
                return _ResultWrapper(error=err)
        return await self._async_transport_call(unit, address, count, kind)

    async def _async_transport_call(self, unit: int, address: int, count: int, kind: str) -> _ResultWrapper:
        """Unified Modbus read/write call with extensive fallbacks."""
        began = self.metrics.clock()
        async with self._lock:
            acquired = self.metrics.clock()
            try:
                # Fresh client AND socket: its first TCP transaction ID is 1.
                # This works around proxies returning ID 1 for every reply
                # without disabling ID validation or accepting delayed replies
                # from a previous client connection. RTU address 0 is avoided
                # on the client-facing link by using the TCP framer.
                if self._mode == "tcp_proxy":
                    await self._async_close_client_locked()
                await self._async_connect_locked()
                base = getattr(self._client, "protocol", self._client)
                unit_id = int(unit) if unit is not None else None

                if kind == "holding":
                    self._apply_unit(base, unit_id)
                    call_variants = (
                        ((address,), {"count": count, "unit": unit_id}),
                        ((address,), {"count": count, "slave": unit_id}),
                        ((address,), {"count": count, "device_id": unit_id}),
                        ((address,), {"count": count}),
                        ((address, count), {"unit": unit_id}),
                        ((address, count), {"slave": unit_id}),
                        ((address, count), {"device_id": unit_id}),
                        ((address, count), {}),
                    )
                    result = None
                    last_err: Optional[Exception] = None
                    for args, kwargs in call_variants:
                        try:
                            result = await base.read_holding_registers(*args, **kwargs)
                            break
                        except TypeError as err:
                            last_err = err
                            continue
                    if result is None:
                        raise last_err or TypeError("No compatible read_holding_registers signature")
                    if hasattr(result, "isError") and result.isError():
                        if kind == "holding" and getattr(result, "exception_code", None) == 2:
                            raise RegisterAddressError(str(result))
                        raise ModbusException(str(result))
                    regs = getattr(result, "registers", None)
                    if regs is None or len(regs) != count:
                        raise ModbusException(f"Expected {count} registers, received {len(regs or [])}")
                    self._record_success()
                    return _ResultWrapper(registers=regs)

                if kind == "write_register":
                    self._apply_unit(base, unit_id)
                    call_variants = (
                        ((address,), {"value": count, "unit": unit_id}),
                        ((address,), {"value": count, "slave": unit_id}),
                        ((address,), {"value": count, "device_id": unit_id}),
                        ((address,), {"value": count}),
                        ((address, count), {"unit": unit_id}),
                        ((address, count), {"slave": unit_id}),
                        ((address, count), {"device_id": unit_id}),
                        ((address, count), {}),
                    )
                    result = None
                    last_err = None
                    for args, kwargs in call_variants:
                        try:
                            result = await base.write_register(*args, **kwargs)
                            break
                        except TypeError as err:
                            last_err = err
                            continue
                    if result is None:
                        raise last_err or TypeError("No suitable write_register signature")
                    if hasattr(result, "isError") and result.isError():
                        if kind == "holding" and getattr(result, "exception_code", None) == 2:
                            raise RegisterAddressError(str(result))
                        raise ModbusException(str(result))
                    if self._mode == "tcp_proxy" and (
                        getattr(result, "address", None) != address
                        or getattr(result, "registers", None) != [count]
                    ):
                        raise ModbusException("Write response does not echo the requested register/value")
                    self._record_success()
                    return _ResultWrapper(registers=[count])

                raise ValueError(f"Unsupported kind: {kind}")

            except asyncio.CancelledError:
                self._last_request_success = False
                self._last_error = "Request cancelled; outcome unknown"
                raise
            except Exception as err:
                self._last_request_success = False
                self._last_error = str(err)
                _LOGGER.debug("Modbus call failed: %s", err)
                return _ResultWrapper(error=err)
            finally:
                self.metrics.record(unit, kind, began, acquired, self._last_request_success is True)
                if self._mode == "tcp_proxy":
                    await self._async_close_client_locked()

    def _record_success(self) -> None:
        self._last_request_success = True
        self._last_response_at = datetime.now(timezone.utc)
        self._last_error = None

    async def _write_transport(self, unit, address, value):
        result = await self._async_transport_call(unit, address, value, "write_register")
        if result.isError():
            raise result._error

    async def _read_transport(self, unit, start, count):
        result = await self._async_transport_call(unit, start, count, "holding")
        if result.isError():
            raise result._error
        return result.registers

    async def async_pb_write_register(self, unit: int, address: int, value: int, kind: str = "holding", *, owner="external") -> None:
        result = await self.async_pb_call(unit, address, value, "write_register", owner=owner)
        if result.isError():
            if isinstance(result._error, RuntimeError):
                raise result._error
            raise RuntimeError(str(result)) from result._error

    async def async_read_block(self, unit: int, start: int, count: int, *, owner="external", priority=2) -> List[int]:
        result = await self.async_pb_call(unit, start, count, "holding", owner=owner, priority=priority)
        if result.isError():
            if isinstance(result._error, RuntimeError):
                raise result._error
            raise RuntimeError(str(result)) from result._error
        return result.registers


class ModbusBatchCoordinator(DataUpdateCoordinator[Dict[int, int]]):
    """Coordinate batched reads per unit and interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: R290HeatPumpModbusHub,
        unit: int,
        interval_seconds: int,
        *,
        block_size: int = 20,
        block_pause: float = 0.1,  # seconds
        config_entry=None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"r290_heatpump_batch_{unit}_{interval_seconds}",
            update_interval=timedelta(seconds=interval_seconds),
            config_entry=config_entry,
        )
        self._hub = hub
        self._unit = unit
        self._addresses: Set[int] = set()
        self.data: Dict[int, int] = {}
        self._max_count = max(1, min(125, int(block_size)))
        self._pause = max(0.0, float(block_pause))
        self._stopped = False
        self.observations = {}
        self._interval_seconds = interval_seconds

    async def async_shutdown(self) -> None:
        self._stopped = True
        await super().async_shutdown()

    def add_addresses(self, addrs: List[int]) -> None:
        before = len(self._addresses)
        self._addresses.update(addrs)
        after = len(self._addresses)
        if after > before and self.last_update_success is not None:
            self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> Dict[int, int]:
        if self._stopped or not self._addresses:
            return {}
        addresses = sorted(self._addresses)
        result: Dict[int, int] = {}
        i = 0
        while i < len(addresses) and not self._stopped:
            start = addresses[i]
            end = start
            j = i + 1
            while j < len(addresses) and addresses[j] == end + 1 and (addresses[j] - start + 1) <= self._max_count:
                end = addresses[j]
                j += 1
            count = end - start + 1
            try:
                regs = await self._hub.async_read_block(self._unit, start, count)
                received_at = datetime.now(timezone.utc).isoformat()
                for offset, addr in enumerate(range(start, end + 1)):
                    result[addr] = regs[offset]
                    old = self.observations.get(addr, {})
                    self.observations[addr] = {
                        "value": regs[offset], "received_at": received_at,
                        "changed_at": old.get("changed_at") if old.get("value") == regs[offset] else received_at,
                        "previous": old.get("previous") if old.get("value") == regs[offset] else old.get("value"),
                        "error": None, "interval": self._interval_seconds,
                    }
            except Exception as err:
                for addr in range(start, end + 1):
                    self.observations[addr] = {**self.observations.get(addr, {}),
                        "error": str(err), "attempted_at": datetime.now(timezone.utc).isoformat()}
                _LOGGER.debug("Batch read failed for %s..%s: %s", start, end, err)
            await asyncio.sleep(self._pause)
            i = j
        return result


class ModbusBatchManager:
    """Manage coordinators per unit and interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: R290HeatPumpModbusHub,
        unit: int,
        *,
        block_size: int = 20,
        block_pause: float = 0.1,  # seconds
        config_entry=None,
    ):
        self._hass = hass
        self._hub = hub
        self._unit = unit
        self._coordinators: Dict[int, ModbusBatchCoordinator] = {}
        self._block_size = max(1, min(125, int(block_size)))
        self._block_pause = max(0.0, float(block_pause))
        self._config_entry = config_entry
        self._startup_tasks = set()
        self._listeners = []
        self._stopped = False

    def register(self, address: int, interval_seconds: int) -> None:
        if self._stopped:
            return
        coord = self._coordinators.get(interval_seconds)
        if coord is None:
            coord = ModbusBatchCoordinator(
                self._hass,
                self._hub,
                self._unit,
                interval_seconds,
                block_size=self._block_size,
                block_pause=self._block_pause,
                config_entry=self._config_entry,
            )
            self._coordinators[interval_seconds] = coord
            self._listeners.append(coord.async_add_listener(lambda: None))

            async def _delayed_first_refresh() -> None:
                try:
                    delay = 0.5 if interval_seconds <= 60 else 3.0
                    await asyncio.sleep(delay)
                    if not self._stopped:
                        await coord.async_request_refresh()
                except Exception:
                    pass

            task = self._hass.async_create_task(_delayed_first_refresh())
            self._startup_tasks.add(task)
            task.add_done_callback(self._startup_tasks.discard)

        coord.add_addresses([address])

    def get_cached(self, address: int, interval_seconds: int) -> Optional[int]:
        coord = self._coordinators.get(interval_seconds)
        if not coord:
            return None
        return coord.data.get(address)

    def diagnostics(self):
        """Only received observations; inspecting them never initiates a read."""
        result = {}
        for coord in self._coordinators.values():
            for address, sample in coord.observations.items():
                old = result.get(str(address), {})
                if max(sample.get("received_at", ""), sample.get("attempted_at", "")) >= max(old.get("received_at", ""), old.get("attempted_at", "")):
                    result[str(address)] = dict(sample)
        return result

    def reconnect_probe(self):
        """Use an already configured register from the fastest active group."""
        if not self._stopped:
            for interval in sorted(self._coordinators):
                coord = self._coordinators[interval]
                if coord._addresses:
                    return self._unit, min(coord._addresses)
        return None

    def request_refresh_soon(self) -> None:
        """Refresh the fastest active group; cancel this task on entry unload."""
        if self._stopped or not self._coordinators:
            return
        interval = min(self._coordinators)
        task = self._hass.async_create_task(self.request_refresh(interval))
        self._startup_tasks.add(task)
        task.add_done_callback(self._startup_tasks.discard)

    def subscribe(self, entity, interval_seconds: int) -> None:
        """Publish each completed batch directly; do not wait for entity polling."""
        coord = self._coordinators[interval_seconds]
        active = True

        def updated():
            if active and not self._stopped:
                # async_update only decodes this entity's cached register.
                entity.async_schedule_update_ha_state(True)

        unsubscribe = coord.async_add_listener(updated)

        def remove():
            nonlocal active
            if active:
                active = False
                unsubscribe()
                self._listeners.remove(remove)

        self._listeners.append(remove)
        entity.async_on_remove(remove)
        updated()

    def replace_hub(self, new_hub: R290HeatPumpModbusHub) -> None:
        self._hub = new_hub
        for coord in self._coordinators.values():
            coord._hub = new_hub

    def update_batch_params(self, *, block_size: Optional[int] = None, block_pause: Optional[float] = None) -> None:
        if block_size is not None:
            self._block_size = max(1, min(125, int(block_size)))
        if block_pause is not None:
            self._block_pause = max(0.0, float(block_pause))
        for coord in self._coordinators.values():
            if block_size is not None:
                coord._max_count = self._block_size
            if block_pause is not None:
                coord._pause = self._block_pause

    async def request_refresh(self, interval_seconds: int) -> None:
        if self._stopped:
            return
        coord = self._coordinators.get(interval_seconds)
        if coord is not None:
            try:
                await coord.async_request_refresh()
            except Exception:
                pass

    async def async_shutdown(self) -> None:
        """Stop this entry's polling without closing other entries' connection."""
        self._stopped = True
        tasks = list(self._startup_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for unsub in list(self._listeners):
            unsub()
        self._listeners.clear()
        for coord in self._coordinators.values():
            await coord.async_shutdown()
