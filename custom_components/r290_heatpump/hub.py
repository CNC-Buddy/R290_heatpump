# Version: 1.0.1
# Last modified: 2025-10-24 17:33 by CNC-Buddy
import asyncio
import logging
from typing import Optional, Dict, List, Set
from datetime import timedelta

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
        """Ensure a connected client exists."""
        if self._client is not None:
            try:
                if getattr(self._client, "connected", False):
                    return
                await self._client.close()
            except Exception:
                pass
            self._client = None

        primary_framer = None
        if _FRAMER_STYLE == "type":
            primary_framer = FramerType.RTU if self._mode == "rtuovertcp" else FramerType.SOCKET
        elif _FRAMER_STYLE == "class":
            primary_framer = ModbusRtuFramer if self._mode == "rtuovertcp" else ModbusSocketFramer

        framer_candidates = []
        if primary_framer is not None:
            framer_candidates.append(primary_framer)
        framer_candidates.append(None)

        last_err: Optional[Exception] = None
        for fr in framer_candidates:
            for attempt in range(self._connect_retries + 1):
                try:
                    self._client = AsyncModbusTcpClient(
                        self._host,
                        port=self._port,
                        framer=fr,  # type: ignore[arg-type]
                        timeout=self._request_timeout,
                    )
                except Exception:
                    self._client = AsyncModbusTcpClient(
                        self._host,
                        port=self._port,
                        framer=fr,  # type: ignore[arg-type]
                    )
                _LOGGER.info(
                    "Connecting Modbus client %s:%s mode=%s framer=%s (attempt %s)",
                    self._host,
                    self._port,
                    self._mode,
                    getattr(fr, "__name__", str(fr)),
                    attempt + 1,
                )

                ok = False
                try:
                    ret = await self._client.connect()
                    ok = bool(ret) if ret is not None else bool(getattr(self._client, "connected", False))
                    if not ok:
                        deadline = asyncio.get_running_loop().time() + self._connect_timeout
                        while asyncio.get_running_loop().time() < deadline:
                            await asyncio.sleep(0.2)
                            if getattr(self._client, "connected", False):
                                ok = True
                                break
                except Exception as err:
                    last_err = err
                    ok = False

                if ok:
                    return

                try:
                    await self._client.close()
                except Exception:
                    pass
                self._client = None
                await asyncio.sleep(0.8)

        raise ConnectionError(
            f"Failed to connect {self._host}:{self._port} mode={self._mode}; last_err={last_err}"
        )

    async def async_close(self) -> None:
        """Close the underlying client."""
        try:
            if self._client:
                await self._client.close()
        except Exception:
            pass
        finally:
            self._client = None

    async def async_pb_call(self, unit: int, address: int, count: int, kind: str) -> _ResultWrapper:
        """Unified Modbus read/write call with extensive fallbacks."""
        if self._client is None:
            try:
                await self.async_connect()
            except Exception as err:
                return _ResultWrapper(error=err)

        if self._client is None:
            return _ResultWrapper(error=RuntimeError("Client not available"))

        async with self._lock:
            try:
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
                        return _ResultWrapper(error=Exception(str(result)))
                    regs = getattr(result, "registers", None)
                    return _ResultWrapper(registers=regs or [])

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
                        return _ResultWrapper(error=Exception(str(result)))
                    return _ResultWrapper(registers=[count])

                return _ResultWrapper(error=ValueError(f"Unsupported kind: {kind}"))

            except Exception as err:
                _LOGGER.debug("Modbus call failed: %s", err)
                return _ResultWrapper(error=err)

    async def async_pb_write_register(self, unit: int, address: int, value: int, kind: str = "holding") -> None:
        if self._client is None:
            await self.async_connect()
        if self._client is None:
            raise RuntimeError("Client not available")

        async with self._lock:
            base = getattr(self._client, "protocol", self._client)
            unit_id = int(unit) if unit is not None else None
            self._apply_unit(base, unit_id)
            call_variants = (
                ((address,), {"value": value, "unit": unit_id}),
                ((address,), {"value": value, "slave": unit_id}),
                ((address,), {"value": value, "device_id": unit_id}),
                ((address,), {"value": value}),
                ((address, value), {"unit": unit_id}),
                ((address, value), {"slave": unit_id}),
                ((address, value), {"device_id": unit_id}),
                ((address, value), {}),
            )
            last_err: Optional[Exception] = None
            for args, kwargs in call_variants:
                try:
                    result = await base.write_register(*args, **kwargs)
                    if hasattr(result, "isError") and result.isError():
                        raise Exception(str(result))
                    return
                except TypeError as err:
                    last_err = err
                    continue
            if last_err:
                raise last_err

    async def async_read_block(self, unit: int, start: int, count: int) -> List[int]:
        res = await self.async_pb_call(unit, start, count, "holding")
        if res.isError():
            raise RuntimeError(str(res))
        return res.registers


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
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"r290_heatpump_batch_{unit}_{interval_seconds}",
            update_interval=timedelta(seconds=interval_seconds),
        )
        self._hub = hub
        self._unit = unit
        self._addresses: Set[int] = set()
        self.data: Dict[int, int] = {}
        self._max_count = max(1, min(125, int(block_size)))
        self._pause = max(0.0, float(block_pause))

    def add_addresses(self, addrs: List[int]) -> None:
        before = len(self._addresses)
        self._addresses.update(addrs)
        after = len(self._addresses)
        if after > before and self.last_update_success is not None:
            self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> Dict[int, int]:
        if not self._addresses:
            return {}
        addresses = sorted(self._addresses)
        result: Dict[int, int] = {}
        i = 0
        while i < len(addresses):
            start = addresses[i]
            end = start
            j = i + 1
            while j < len(addresses) and addresses[j] == end + 1 and (addresses[j] - start + 1) <= self._max_count:
                end = addresses[j]
                j += 1
            count = end - start + 1
            try:
                regs = await self._hub.async_read_block(self._unit, start, count)
                for offset, addr in enumerate(range(start, end + 1)):
                    result[addr] = regs[offset]
            except Exception as err:
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
    ):
        self._hass = hass
        self._hub = hub
        self._unit = unit
        self._coordinators: Dict[int, ModbusBatchCoordinator] = {}
        self._block_size = max(1, min(125, int(block_size)))
        self._block_pause = max(0.0, float(block_pause))

    def register(self, address: int, interval_seconds: int) -> None:
        coord = self._coordinators.get(interval_seconds)
        if coord is None:
            coord = ModbusBatchCoordinator(
                self._hass,
                self._hub,
                self._unit,
                interval_seconds,
                block_size=self._block_size,
                block_pause=self._block_pause,
            )
            self._coordinators[interval_seconds] = coord
            try:
                coord.async_add_listener(lambda: None)
            except Exception:
                pass

            async def _delayed_first_refresh() -> None:
                try:
                    delay = 0.5 if interval_seconds <= 60 else 3.0
                    await asyncio.sleep(delay)
                    await coord.async_request_refresh()
                except Exception:
                    pass

            self._hass.async_create_task(_delayed_first_refresh())

        coord.add_addresses([address])

    def get_cached(self, address: int, interval_seconds: int) -> Optional[int]:
        coord = self._coordinators.get(interval_seconds)
        if not coord:
            return None
        return coord.data.get(address)

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
        coord = self._coordinators.get(interval_seconds)
        if coord is not None:
            try:
                await coord.async_request_refresh()
            except Exception:
                pass
