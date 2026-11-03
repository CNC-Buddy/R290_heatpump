"""One bounded, fair transaction scheduler per shared transport.

All time decisions use an injectable monotonic clock. Wall time is provenance
only. Writes execute once and are verified inside the same scheduler job.
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
import time

from .models import Demand, Job, Sample, RegisterAddressError, WriteVerificationError
from .profiles import ATOMIC_PAIRS, blocks, policy, settings


class Scheduler:
    def __init__(
        self, read, write, config, *, clock=time.monotonic, utc=None, start_worker=True
    ):
        self.read_transport, self.write_transport = read, write
        self.config = settings(config)
        self.clock = clock
        self.utc = utc or (lambda: datetime.now(timezone.utc).isoformat())
        self.block_size = max(2, min(125, int(config.get("block_size", 20))))
        self.pause = max(0, float(config.get("block_pause", 0.05)))
        self.demands = {}
        self.cache = {}
        self.listeners = {}
        self.jobs = []
        self.worker = None
        self._autostart = start_worker
        self._wake = asyncio.Event()
        self.stopping = False
        self._next_io = 0
        self._last_unit = None
        self._active = None
        self.suspended = False
        self._idle = asyncio.Event()
        self._idle.set()
        self.backoff = {}
        self.failures = {}
        self.limits = {}
        self.slowdown = {}
        self.stats = {}
        self.samples = deque(maxlen=500)
        self._healthy = {}
        self.started = clock()
        self.last_error = None
        self.verified_writes = 0

    def start(self):
        if self._autostart and self.worker is None and not self.stopping:
            self.worker = asyncio.create_task(self._run(), name="r290-polling-auto")
        self._wake.set()

    def register(self, owner, unit, address, requested, *, max_age=None):
        if self.stopping or self.suspended:
            raise RuntimeError("Scheduler is stopping or reconfiguring")
        interval, priority, age = policy(address, requested, self.config)
        if max_age is not None:
            priority = min(priority, 1)
        demand = self.demands.setdefault((unit, address), Demand(due=self.clock()))
        demand.owners[owner] = (
            interval,
            priority,
            min(age, max_age) if max_age else age,
        )
        self.start()

    def subscribe(self, owner, callback):
        self.listeners[owner] = callback
        return lambda: self.listeners.pop(owner, None)

    def unregister(self, owner):
        self.listeners.pop(owner, None)
        for key, demand in list(self.demands.items()):
            demand.owners.pop(owner, None)
            if not demand.owners:
                del self.demands[key]
        for job in list(self.jobs):
            job.owners.discard(owner)
            if not job.owners:
                self.jobs.remove(job)
                if not job.future.done():
                    job.future.set_exception(
                        RuntimeError("Entry unloaded before transaction")
                    )
        self._wake.set()

    def _notify(self, keys):
        owners = {
            owner
            for key in keys
            if key in self.demands
            for owner in self.demands[key].owners
        }
        for owner in owners:
            callback = self.listeners.get(owner)
            if callback:
                try:
                    callback()
                except Exception as err:
                    self.last_error = f"Consumer callback failed: {err}"

    def get(self, unit, address):
        if self.stopping:
            return None
        sample = self.cache.get((unit, address))
        demand = self.demands.get((unit, address))
        return (
            sample.value
            if sample
            and sample.available(self.clock(), demand.max_age if demand else 60)
            else None
        )

    def _expire(self):
        keys = []
        for key, demand in self.demands.items():
            sample = self.cache.get(key)
            if (
                sample
                and not sample.expired
                and not sample.available(self.clock(), demand.max_age)
            ):
                sample.expired = True
                keys.append(key)
        self._notify(keys)

    def observations(self, unit):
        result = {}
        for (u, address), s in self.cache.items():
            if u != unit:
                continue
            demand = self.demands.get((u, address))
            result[str(address)] = {
                "value": s.value,
                "received_at": s.received_at,
                "changed_at": s.changed_at,
                "previous": s.previous,
                "error": s.error,
                "attempted_at": s.attempted_at,
                "interval": demand.interval if demand else None,
                "age": (
                    None if s.received is None else max(0, self.clock() - s.received)
                ),
                "quality": (
                    "valid"
                    if s.available(self.clock(), demand.max_age if demand else 60)
                    else "stale"
                ),
            }
        return result

    async def read(self, unit, start, count, *, priority=2, owner="external"):
        return await self._submit(unit, start, count, priority, None, owner)

    async def write(self, unit, address, value, *, owner="external"):
        return await self._submit(unit, address, 1, 0, value, owner)

    async def _submit(self, unit, start, count, priority, value, owner):
        if self.stopping or self.suspended:
            raise RuntimeError("Scheduler is stopping or reconfiguring")
        if (
            not 1 <= int(unit) <= 247
            or not 0 <= int(start) <= 65535
            or not 1 <= int(count) <= 125
            or start + count > 65536
        ):
            raise ValueError("Invalid Modbus request")
        if value is not None and not 0 <= int(value) <= 65535:
            raise ValueError("Invalid register value")
        if value is None:
            for job in self.jobs:
                if (job.unit, job.start, job.count, job.value) == (
                    unit,
                    start,
                    count,
                    None,
                ):
                    job.priority = min(job.priority, priority)
                    job.owners.add(owner)
                    return await asyncio.shield(job.future)
        if len(self.jobs) >= 128:
            raise RuntimeError("Modbus queue is full")
        future = asyncio.get_running_loop().create_future()
        # Consume abandoned callers' errors without cancelling shared reads.
        future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
        job = Job(unit, start, count, priority, self.clock(), future, value, {owner})
        self.jobs.append(job)
        self.start()
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # A cancelled command must not actuate later from the queue. Once
            # started, let the indivisible write/readback job finish instead.
            if value is not None and job in self.jobs:
                self.jobs.remove(job)
                future.cancel()
            raise

    def _poll_job(self):
        now = self.clock()
        due = [
            (key, d)
            for key, d in self.demands.items()
            if d.due <= now
            and d.blocked_until <= now
            and self.backoff.get(key[0], 0) <= now
        ]
        if not due:
            return None
        (unit, address), d = min(
            due,
            key=lambda item: (
                item[1].priority - (now - item[1].due) / 15,
                item[0][0] == self._last_unit,
                item[1].due,
                item[0],
            ),
        )
        eligible = [a for (u, a), v in due if u == unit and v.priority == d.priority]
        for start, count in blocks(eligible, self.limits.get(unit, self.block_size)):
            if start <= address < start + count:
                return Job(unit, start, count, d.priority, d.due, None)

    async def run_once(self):
        """Execute at most one job; exposed for deterministic clock-driven tests."""
        self._expire()
        if self._active is not None or self.suspended:
            return False
        now = self.clock()
        poll = self._poll_job() if not self.stopping else None
        for old in list(self.jobs):
            if now - old.created > (120 if old.priority == 4 else 30):
                self.jobs.remove(old)
                if not old.future.done():
                    old.future.set_exception(
                        TimeoutError("Transaction expired in scheduler queue")
                    )
        candidates = list(self.jobs) + ([poll] if poll else [])
        # Priority aging and slave rotation prevent diagnostics/slow registers
        # being permanently starved. Deadlines never accumulate duplicate jobs.
        candidates = [
            j
            for j in candidates
            if (
                j.priority == 0
                or now >= max(self._next_io, self.backoff.get(j.unit, 0))
            )
        ]
        if not candidates:
            return False
        job = min(
            candidates,
            key=lambda j: (
                j.priority - (now - j.created) / 15,
                j.unit == self._last_unit,
                j.created,
            ),
        )
        if job.future is not None:
            self.jobs.remove(job)
        self._active = job
        self._idle.clear()
        try:
            await self._execute(job)
        finally:
            self._active = None
            self._last_unit = job.unit
            self._idle.set()
        return True

    def _success(self, unit, start, values):
        now = self.clock()
        stamp = self.utc()
        keys = []
        for offset, value in enumerate(values):
            key = (unit, start + offset)
            sample = self.cache.setdefault(key, Sample())
            if sample.value != value:
                sample.previous = sample.value
                sample.changed_at = stamp
            sample.value = value
            sample.received = now
            sample.received_at = stamp
            sample.error = None
            sample.expired = False
            keys.append(key)
        self._notify(keys)

    async def _read(self, unit, start, count):
        values = await self.read_transport(unit, start, count)
        if len(values) != count:
            raise RuntimeError("Incomplete register response")
        self._success(unit, start, values)
        return values

    async def _execute(self, job):
        began = self.clock()
        error = None
        values = None
        try:
            if job.value is not None:
                write_error = None
                try:
                    await self.write_transport(job.unit, job.start, job.value)
                except Exception as err:
                    write_error = err
                # Never repeat a possibly executed write. A read establishes
                # the current value even if the write acknowledgement was lost.
                try:
                    values = await self._read(job.unit, job.start, 1)
                except Exception as err:
                    raise WriteVerificationError(
                        f"Write outcome unconfirmed: {write_error or err}"
                    ) from err
                if values[0] != job.value:
                    raise WriteVerificationError(
                        f"Readback {values[0]} differs from requested {job.value}"
                    )
                self.verified_writes += 1
            else:
                fresh = [
                    self.cache.get((job.unit, a))
                    for a in range(job.start, job.start + job.count)
                ]
                if job.future is not None and all(
                    s
                    and not s.error
                    and s.received is not None
                    and s.received >= job.created
                    for s in fresh
                ):
                    values = [s.value for s in fresh]
                else:
                    values = await self._read(job.unit, job.start, job.count)
            self.failures[job.unit] = 0
            self.backoff.pop(job.unit, None)
            self._healthy[job.unit] = self._healthy.get(job.unit, 0) + 1
            if self._healthy[job.unit] >= 20:
                self.slowdown[job.unit] = max(1, self.slowdown.get(job.unit, 1) * 0.8)
                if job.unit in self.limits:
                    self.limits[job.unit] = min(
                        self.block_size, self.limits[job.unit] + 1
                    )
                self._healthy[job.unit] = 0
            if job.future is not None and not job.future.done():
                job.future.set_result(values)
        except Exception as err:
            error = err
            self.last_error = str(err)
            self._healthy[job.unit] = 0
            if isinstance(err, RegisterAddressError):
                if job.count == 2 and (job.start, job.start + 1) in ATOMIC_PAIRS:
                    for address in (job.start, job.start + 1):
                        demand = self.demands.get((job.unit, address))
                        if demand:
                            demand.blocked_until = self.clock() + 300
                elif job.count > 1:
                    self.limits[job.unit] = max(1, job.count // 2)
                else:
                    demand = self.demands.get((job.unit, job.start))
                    if demand:
                        demand.blocked_until = self.clock() + 300
            else:
                n = self.failures.get(job.unit, 0) + 1
                self.failures[job.unit] = n
                self.backoff[job.unit] = self.clock() + min(120, 2 ** min(n, 7))
                self.slowdown[job.unit] = min(4, self.slowdown.get(job.unit, 1) * 1.25)
            keys = []
            for address in range(job.start, job.start + job.count):
                key = (job.unit, address)
                sample = self.cache.setdefault(key, Sample())
                sample.error = str(err)
                sample.attempted_at = self.utc()
                sample.expired = True
                keys.append(key)
            self._notify(keys)
            if job.future is not None and not job.future.done():
                job.future.set_exception(err)
        finally:
            now = self.clock()
            duration = max(0, now - began)
            stat = self.stats.setdefault(
                job.unit,
                {
                    "requests": 0,
                    "errors": 0,
                    "latency_ewma": 0,
                    "effective_interval": None,
                },
            )
            stat["requests"] += 1
            stat["errors"] += bool(error)
            stat["latency_ewma"] = (
                duration
                if stat["requests"] == 1
                else 0.2 * duration + 0.8 * stat["latency_ewma"]
            )
            self.samples.append(
                (now, duration, bool(error), max(0, began - job.created))
            )
            self._next_io = now + max(
                self.pause, duration * (1 / self.config["poll_budget"] - 1)
            )
            for address in range(job.start, job.start + job.count):
                d = self.demands.get((job.unit, address))
                if d:
                    factor = self.slowdown.get(job.unit, 1) if d.priority >= 3 else 1
                    # Keep control feedback within its consumer age deadline.
                    effective = min(d.interval * factor, d.max_age * 0.8)
                    d.due = now + (
                        1
                        if isinstance(error, RegisterAddressError) and job.count > 1
                        else effective
                    )
                    stat["effective_interval"] = effective

    async def quiesce(self):
        self.suspend()
        await self._idle.wait()

    def suspend(self):
        self.suspended = True
        for job in self.jobs:
            if not job.future.done():
                job.future.set_exception(
                    RuntimeError("Connection configuration changed before transaction")
                )
        self.jobs.clear()

    def resume(self, *, invalidate=False):
        if invalidate:
            for sample in self.cache.values():
                sample.error = "Connection changed; awaiting fresh read"
                sample.expired = True
            for d in self.demands.values():
                d.due = self.clock()
            self.backoff.clear()
            self.failures.clear()
            self._notify(set(self.cache))
        self.suspended = False
        self._wake.set()

    async def _run(self):
        try:
            while not self.stopping:
                self._wake.clear()
                if await self.run_once():
                    continue
                now = self.clock()
                due = [
                    max(d.due, d.blocked_until, self.backoff.get(u, 0), self._next_io)
                    for (u, _), d in self.demands.items()
                ]
                delay = max(0.01, min(1, min(due) - now)) if due else 1
                if self.jobs:
                    delay = min(delay, max(0.01, self._next_io - now))
                try:
                    await asyncio.wait_for(self._wake.wait(), delay)
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.last_error = f"Scheduler stopped: {err}"
            self.stopping = True
            self._notify(set(self.cache))
            for job in self.jobs:
                if not job.future.done():
                    job.future.set_exception(RuntimeError(self.last_error))
            self.jobs.clear()

    async def stop(self):
        self.stopping = True
        self._wake.set()
        for job in self.jobs:
            if not job.future.done():
                job.future.set_exception(
                    RuntimeError("Scheduler stopped before transaction")
                )
        self.jobs.clear()
        # An in-flight transaction, especially a write, completes before shutdown.
        if self.worker:
            await self.worker
        self.worker = None
        self.listeners.clear()

    def diagnostics(self):
        now = self.clock()
        recent = [s for s in self.samples if s[0] >= now - 60]
        overdue = sum(d.due < now for d in self.demands.values())
        return {
            "profile": "auto",
            "running": not self.stopping,
            "queue_depth": len(self.jobs),
            "registered_registers": len(self.demands),
            "overdue_registers": overdue,
            "verified_writes": self.verified_writes,
            "last_error": self.last_error,
            "requests_last_minute": len(recent),
            "error_ratio": sum(s[2] for s in recent) / len(recent) if recent else 0,
            "transport_time_fraction": min(
                1, sum(s[1] for s in recent) / max(1, min(60, now - self.started))
            ),
            "max_queue_wait": max((s[3] for s in recent), default=0),
            "slaves": {
                str(u): {
                    **stat,
                    "backoff_remaining": max(0, self.backoff.get(u, 0) - now),
                    "slowdown": self.slowdown.get(u, 1),
                    "block_limit": self.limits.get(u, self.block_size),
                }
                for u, stat in self.stats.items()
            },
        }
