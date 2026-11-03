"""Documented service registers, explicit timed tests, and durable recovery state.

Source: Modbus_protocol_V1.2.9, pages 25–27. No arbitrary register writes.
A HA timer is not a device watchdog: failed restoration remains visible.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone, timedelta

COMMANDS = {
    "compressor": {"address": 0x332, "control": 0x331, "bit": 0, "max": 120, "unit": "Hz"},
    "eev": {"address": 0x336, "control": 0x331, "bit": 1, "max": 500, "unit": "steps"},
    "evi": {"address": 0x33A, "control": 0x331, "bit": 2, "max": 500, "unit": "steps"},
    "fan": {"address": 0x33E, "control": 0x331, "bit": 3, "max": 80, "unit": "Hz"},
    "pump": {"address": 0x344, "control": 0x343, "bit": None, "max": 100, "unit": "raw %"},
}


class ServiceTools:
    def __init__(self, hass, store, saved=None):
        self.hass, self.store = hass, store
        self.pending = deepcopy(saved or {})
        for record in self.pending.values():
            record.update(state="recovery_required", error="Restart interrupted supervision / Neustart hat die Überwachung unterbrochen")
        self.lock = asyncio.Lock()
        self.starting = False
        self.tasks = {}
        self.snapshots = {}
        self.last_read = {}

    async def persist(self):
        await self.store.async_save(deepcopy(self.pending))

    def identity(self, entry_id):
        entries = {e.entry_id: e for e in self.hass.config_entries.async_entries("r290_heatpump")}
        entry = entries.get(entry_id)
        if entry is None:
            raise ValueError("Device entry no longer exists")
        bridge = entries.get(entry.data.get("bridge_entry_id"))
        data = (bridge or entry).data
        return {"host": data.get("host"), "port": int(data.get("port", 502)),
                "connection_type": data.get("connection_type", "rtuovertcp"),
                "slave": int(entry.data.get("slave", 1))}

    def status(self):
        return {"tests": self.pending, "snapshots": self.snapshots}

    def target(self, entry_id):
        pending = self.pending.get(entry_id)
        if pending and pending.get("identity") != self.identity(entry_id):
            raise ValueError("Device address changed / Geräteadresse geändert")
        entry = next((e for e in self.hass.config_entries.async_entries("r290_heatpump")
                      if e.entry_id == entry_id and e.data.get("device_type") == "heat_pump"
                      and not getattr(e, "disabled_by", None)), None)
        runtime = self.hass.data["r290_heatpump"].get(entry_id, {})
        if entry is None or not runtime.get("hub"):
            raise ValueError("Heat pump is not loaded / Wärmepumpe nicht geladen")
        return runtime["hub"], int(entry.data.get("slave", 1))

    async def read(self, entry_id, address, count=1):
        hub, slave = self.target(entry_id)
        async with asyncio.timeout(8):
            values = await hub.async_read_block(slave, address, count, owner=f"service:{entry_id}", priority=0)
        if len(values) != count or any(type(v) is not int or not 0 <= v <= 65535 for v in values):
            raise ValueError("Invalid register response")
        return values

    async def write(self, entry_id, address, value):
        hub, slave = self.target(entry_id)
        async with asyncio.timeout(8):
            await hub.async_pb_write_register(slave, address, value, owner=f"service:{entry_id}")
        if (await self.read(entry_id, address))[0] != value:
            raise ValueError(f"Readback mismatch at 0x{address:04X} / Rückmeldung abweichend")

    async def inspect(self, entry_id):
        async with self.lock:
            if self.pending:
                raise ValueError("End service test before reading info / Erst Servicetest beenden")
            now = datetime.now(timezone.utc)
            if (now - self.last_read.get(entry_id, datetime.min.replace(tzinfo=timezone.utc))).total_seconds() < 5:
                raise ValueError("Wait five seconds before reading again")
            self.last_read[entry_id] = now
            values, errors = {}, {}
            # Isolated reads let older firmware report unsupported registers independently.
            for address in [0x360, 0x361, 0x362, 0x363, 0x331, 0x332, 0x336, 0x33A, 0x33E, 0x343, 0x344]:
                try:
                    async with asyncio.timeout(8):
                        values[str(address)] = (await self.read(entry_id, address))[0]
                except Exception as err:
                    errors[str(address)] = str(err)
            raw = values.get(str(0x360))
            self.snapshots[entry_id] = {"received_at": datetime.now(timezone.utc).isoformat(),
                "values": values, "errors": errors,
                "program_version": f"{raw // 100}.{raw % 100:02}" if raw is not None and 0 < raw < 65535 else None,
                "display_version": None}
            return self.snapshots[entry_id]

    async def start(self, entry_id, component, value, seconds, confirmed, qualified):
        if confirmed is not True or qualified is not True:
            raise ValueError("Confirm service test and on-site supervision / Servicetest vor Ort bestätigen")
        spec = COMMANDS.get(component)
        if spec is None or type(value) is not int or not 0 <= value <= spec["max"]:
            raise ValueError("Invalid component or test value")
        if type(seconds) is not int or not 15 <= seconds <= 120:
            raise ValueError("Choose a test duration of 15–120 seconds")
        async with self.lock:
            self.starting = True
            try:
                return await self._start_locked(entry_id, component, spec, value, seconds)
            finally:
                self.starting = False

    async def _start_locked(self, entry_id, component, spec, value, seconds):
        if self.pending:
            raise ValueError("Finish the active test or recovery first / Erst laufenden Test oder Rücksetzung beenden")
        for runtime in self.hass.data["r290_heatpump"].values():
            controller = runtime.get("controller") if isinstance(runtime, dict) else None
            if controller and (controller.mode != "observe" or controller._resume_mode):
                raise ValueError("Set auxiliary controllers to Observe first / Zusatzpumpenregler zuerst auf Beobachten setzen")
        # An affirmative program reply and documented register bounds are required.
        version = (await self.read(entry_id, 0x360))[0]
        if not 0 < version < 65535:
            raise ValueError("No valid program version")
        status = (await self.read(entry_id, 1))[0]
        frequency = (await self.read(entry_id, 0x40))[0]
        if status & (1 << 10) or frequency != 0:
            raise ValueError("Switch the device off and wait for compressor standstill / Gerät ausschalten und Verdichterstillstand abwarten")
        if (await self.read(entry_id, 0))[0] & 0xE117:
            raise ValueError("Operation or protection function active / Betrieb oder Schutzfunktion aktiv")
        if (await self.read(entry_id, 0x330))[0] & 0x213C:
            raise ValueError("Another service function is active / Andere Servicefunktion aktiv")
        if any(await self.read(entry_id, 2, 8)):
            raise ValueError("Device reports a fault / Gerät meldet einen Fehler")
        forced = (await self.read(entry_id, 0x331))[0]
        pump_mode = (await self.read(entry_id, 0x343))[0]
        if forced & 15 or pump_mode != 0:
            raise ValueError("A manual override already exists / Bereits eine manuelle Übersteuerung aktiv")
        if component == "compressor":
            flow = (await self.read(entry_id, 0x58))[0]
            if not 15 <= flow < 1000:
                raise ValueError("Compressor test requires confirmed water flow >=15 L/min")
        old_value = (await self.read(entry_id, spec["address"]))[0]
        if old_value > spec["max"]:
            raise ValueError("Existing test value is outside documented range")
        control = forced if spec["control"] == 0x331 else pump_mode
        record = {"component": component, "address": spec["address"], "control": spec["control"],
                  "identity": self.identity(entry_id), "program_version": version,
                  "bit": spec["bit"], "old_value": old_value, "value": value,
                  "started_at": datetime.now(timezone.utc).isoformat(),
                  "ends_at": (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(),
                  "state": "starting", "error": None}
        self.pending[entry_id] = record
        await self.persist()  # Write-ahead recovery record, before the first hardware command.
        try:
            await self.write(entry_id, spec["address"], value)
            await self.write(entry_id, spec["control"], control | (1 << spec["bit"]) if spec["bit"] is not None else 1)
            record.update(state="running", started_at=datetime.now(timezone.utc).isoformat(),
                          ends_at=(datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat())
            await self.persist()
        except BaseException:
            await self._restore(entry_id)
            raise
        self.tasks[entry_id] = asyncio.create_task(self._watch(entry_id, seconds))
        return dict(record)

    async def _watch(self, entry_id, seconds):
        try:
            async with asyncio.timeout(seconds):
                while True:
                    await asyncio.sleep(5)
                    record = self.pending.get(entry_id)
                    if record is None:
                        return
                    status = (await self.read(entry_id, 1))[0]
                    if status & (1 << 10) or any(await self.read(entry_id, 2, 8)):
                        break
                    # Frost protection/defrost/oil return must never compete with a test.
                    if (await self.read(entry_id, 0))[0] & 0x117:
                        break
                    frequency = (await self.read(entry_id, 0x40))[0]
                    if record["component"] != "compressor" and frequency != 0:
                        break
                    if record["component"] == "compressor" and not 15 <= (await self.read(entry_id, 0x58))[0] < 1000:
                        break
        except asyncio.CancelledError:
            return  # Explicit stop/unload owns restoration.
        except Exception:
            pass
        finally:
            if not asyncio.current_task().cancelling():
                async with self.lock:
                    await self._restore(entry_id)
                self.tasks.pop(entry_id, None)

    async def _restore(self, entry_id):
        record = self.pending.get(entry_id)
        if not record:
            return
        try:
            if record.get("identity") != self.identity(entry_id):
                raise ValueError("Device address changed; restore original connection before retrying / Geräteadresse geändert; ursprüngliche Verbindung wiederherstellen")
            if (await self.read(entry_id, 0x360))[0] != record.get("program_version"):
                raise ValueError("Firmware changed; check override at device / Firmware geändert; Testmodus am Gerät prüfen")
            # Clear only this test's bit, preserving unrelated external bits.
            control = (await self.read(entry_id, record["control"]))[0]
            value = control & ~(1 << record["bit"]) if record["bit"] is not None else 0
            await self.write(entry_id, record["control"], value)
            await self.write(entry_id, record["address"], record["old_value"])
        except Exception as err:
            record.update(state="recovery_required", error=str(err))
            await self.persist()
            return
        del self.pending[entry_id]
        await self.persist()

    async def stop(self, entry_id):
        task = self.tasks.pop(entry_id, None)
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with self.lock:
            await self._restore(entry_id)
        if entry_id in self.pending:
            raise ValueError("Automatic release failed. Release at device and retry / Rücksetzung fehlgeschlagen. Am Gerät prüfen und erneut versuchen")
