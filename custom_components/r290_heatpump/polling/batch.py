"""Existing entity batch API backed by the shared scheduler in auto mode."""


class ScheduledBatchManager:
    def __init__(self, hass, hub, unit, *, config_entry=None, **kwargs):
        self._hub = hub
        self._unit = unit
        self._scheduler = hub.scheduler
        self._owner = config_entry.entry_id if config_entry else f"unit:{unit}"
        self._requests = {}
        self._listeners = []
        self._stopped = False
        self._unsubscribe = self._scheduler.subscribe(self._owner, self._updated)

    def register(self, address, interval_seconds):
        if self._stopped:
            return
        self._requests.setdefault(interval_seconds, set()).add(address)
        # Different intervals under one owner still share the fastest demand.
        requested = min(
            interval
            for interval, addresses in self._requests.items()
            if address in addresses
        )
        self._scheduler.register(self._owner, self._unit, address, requested)

    def subscribe(self, entity, interval_seconds):
        last = object()

        def update():
            nonlocal last
            sample = self._scheduler.cache.get(
                (self._unit, getattr(entity, "_address", None))
            )
            token = (
                (sample.received_at, sample.error, sample.expired) if sample else None
            )
            if not self._stopped and token != last:
                last = token
                entity.async_schedule_update_ha_state(True)

        self._listeners.append(update)

        def remove():
            if update in self._listeners:
                self._listeners.remove(update)

        entity.async_on_remove(remove)
        update()

    def _updated(self):
        for listener in list(self._listeners):
            listener()

    def get_cached(self, address, interval_seconds):
        return None if self._stopped else self._scheduler.get(self._unit, address)

    def diagnostics(self):
        return self._scheduler.observations(self._unit)

    def reconnect_probe(self):
        addresses = {a for group in self._requests.values() for a in group}
        return (self._unit, min(addresses)) if addresses and not self._stopped else None

    def request_refresh_soon(self):
        if self._stopped:
            return
        for key, d in self._scheduler.demands.items():
            if self._owner in d.owners:
                d.due = self._scheduler.clock()
        self._scheduler.start()

    async def request_refresh(self, interval_seconds):
        # Writes were already individually verified. Refresh the normal plan
        # without blocking on every configuration register after one change.
        self.request_refresh_soon()

    def update_batch_params(self, **kwargs):
        pass  # The owning hub configures the single scheduler.

    async def async_shutdown(self):
        self._stopped = True
        self._unsubscribe()
        self._scheduler.unregister(self._owner)
        self._listeners.clear()
