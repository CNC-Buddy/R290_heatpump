import logging
from datetime import datetime, timedelta, date
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import UnitOfEnergy
from homeassistant.util import dt as dt_util
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

DOMAIN = "r290_heatpump"

class R290HeatPumpCOPSensorBase(SensorEntity):
    """Base class for R290 Heat Pump COP sensors."""

    _attr_device_class = "power_factor"
    _attr_native_unit_of_measurement = None  # COP ist dimensionslos
    _attr_state_class = "measurement"
    # Show COP as regular sensors (not diagnostic)
    _attr_entity_category = None

    # Evaluate every 5 minutes
    SCAN_INTERVAL = timedelta(minutes=5)

    def __init__(self, hass, entry, device_info, name, unique_id_suffix):
        """Initialize the COP sensor."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"r290_heatpump_cop_{unique_id_suffix}"
        self._attr_device_info = device_info
        self._state = None
        self._heat_meter = entry.data.get("heat_meter")
        # Allow one or multiple power meters (comma/space separated) from config
        cfg_power = entry.data.get("power_meter")
        if isinstance(cfg_power, str):
            parts = [p.strip() for p in cfg_power.replace(";", ",").split(",") if p.strip()]
            self._power_meters = parts if parts else []
        elif isinstance(cfg_power, list):
            self._power_meters = [str(p) for p in cfg_power]
        else:
            self._power_meters = []
        if not self._power_meters:
            _LOGGER.warning("No power meters configured for COP; please set 'power_meter' in entry data (comma separated for multiple meters)")
        self._attr_should_poll = True
        _LOGGER.debug(f"Initialized {self._attr_name} with heat_meter={self._heat_meter}, power_meters={self._power_meters}")

    async def async_added_to_hass(self):
        """Trigger an initial compute on add so values show after setup/reload."""
        try:
            await self.async_update()
        except Exception:
            pass
        self.async_write_ha_state()

    @property
    def state(self):
        """Expose computed COP value to HA state machine."""
        return self._state


def _slugify(src: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in src).strip("_")


class _EnergyAccumulator:
    """In-memory energy accumulator per source starting now (no SQL/statistics)."""

    def __init__(self, hass, power_entity: str, heat_entity: str):
        self._hass = hass
        self._store: Store = Store(hass, 1, f"{DOMAIN}_cop_accumulator")
        self._sources = {
            'energy': { 'last': None, 'buckets': {} },
            'heat':   { 'last': None, 'buckets': {} },
        }
        self._entities = { 'energy': power_entity, 'heat': heat_entity }
        self._loaded = False

    def reconfigure(self, power_entity: str, heat_entity: str) -> None:
        """Update bound entities without losing accumulated buckets.

        If an entity id changes, reset only the corresponding 'last' pointer
        to avoid mixing deltas across sensors, but keep the daily buckets.
        """
        try:
            old_power = self._entities.get('energy')
            old_heat = self._entities.get('heat')
        except Exception:
            old_power = None
            old_heat = None
        if power_entity != old_power:
            self._sources['energy']['last'] = None
        if heat_entity != old_heat:
            self._sources['heat']['last'] = None
        self._entities = { 'energy': power_entity, 'heat': heat_entity }

    def _today(self) -> str:
        return dt_util.now().date().isoformat()

    def _add_delta(self, kind: str, delta: float) -> bool:
        if delta <= 0:
            return False
        today = self._today()
        buckets = self._sources[kind]['buckets']
        buckets[today] = float(buckets.get(today, 0.0) + delta)
        # keep buckets bounded (e.g., 500 days)
        if len(buckets) > 520:
            try:
                for d in sorted(buckets.keys())[:-520]:
                    buckets.pop(d, None)
            except Exception:
                pass
        return True

    async def async_load(self):
        if self._loaded:
            return
        try:
            data = await self._store.async_load()
        except Exception:
            data = None
        if isinstance(data, dict):
            try:
                srcs = data.get('sources') or {}
                for kind in ('energy', 'heat'):
                    if kind in srcs:
                        ksrc = srcs[kind]
                        # restore buckets
                        self._sources[kind]['buckets'] = {str(k): float(v) for k, v in (ksrc.get('buckets') or {}).items()}
                        # restore last to capture offline delta on next update (monotonic meters)
                        try:
                            self._sources[kind]['last'] = float(ksrc.get('last')) if ksrc.get('last') is not None else None
                        except Exception:
                            self._sources[kind]['last'] = None
                # If entity ids changed since save, reset last accordingly via reconfigure
                ent = data.get('entities') or {}
                self.reconfigure(ent.get('energy', self._entities['energy']), ent.get('heat', self._entities['heat']))
            except Exception:
                pass
        self._loaded = True

    async def async_save(self):
        try:
            payload = {
                'sources': {
                    'energy': {
                        'buckets': self._sources['energy']['buckets'],
                        'last': self._sources['energy']['last'],
                    },
                    'heat': {
                        'buckets': self._sources['heat']['buckets'],
                        'last': self._sources['heat']['last'],
                    },
                },
                'entities': dict(self._entities),
            }
            await self._store.async_save(payload)
        except Exception:
            pass

    async def async_update(self) -> None:
        if not self._loaded:
            await self.async_load()
        changed = False
        for kind, ent_id in self._entities.items():
            if not ent_id:
                continue
            st = self._hass.states.get(ent_id)
            if not st or st.state in (None, 'unknown', 'unavailable'):
                continue
            try:
                current = float(st.state)
            except Exception:
                continue
            last = self._sources[kind]['last']
            if last is None:
                self._sources[kind]['last'] = current
                continue
            delta = current - last
            if delta < 0:
                # For monotonic meters: ignore spurious negative deltas, keep last
                continue
            if self._add_delta(kind, delta):
                changed = True
            self._sources[kind]['last'] = current
        if changed:
            await self.async_save()

    def _sum_days(self, kind: str, days: int) -> float:
        buckets = self._sources[kind]['buckets']
        if not buckets:
            return 0.0
        today = dt_util.now().date()
        total = 0.0
        for dstr, val in buckets.items():
            try:
                d = date.fromisoformat(dstr)
            except Exception:
                continue
            if (today - d).days < days:
                total += float(val)
        return total

    def get_value(self, kind: str, period: str):
        buckets = self._sources[kind]['buckets']
        if period == 'today':
            return float(buckets.get(self._today(), 0.0))
        if period == 'yesterday':
            y = (dt_util.now().date() - timedelta(days=1)).isoformat()
            return float(buckets.get(y, 0.0))
        if period == '7d':
            return self._sum_days(kind, 7)
        if period == '30d':
            return self._sum_days(kind, 30)
        if period == '365d':
            return self._sum_days(kind, 365)
        if period == 'overall':
            return sum(float(v) for v in buckets.values())
        return None

    


 

class R290HeatPumpCOPOverallSensor(R290HeatPumpCOPSensorBase):
    """Sensor for overall COP since beginning."""

    def __init__(self, hass, entry, device_info):
        super().__init__(hass, entry, device_info, "COP Overall", "overall")

    async def async_update(self):
        """Fetch overall COP using in-memory accumulator (no state dependency)."""
        try:
            if not self._power_meters or not self._heat_meter:
                self._state = None
                return
            acc = self._hass.data.get(DOMAIN, {}).get('_cop_acc')
            if not acc:
                self._state = None
                return
            try:
                await acc.async_update()
            except Exception:
                pass
            cons = acc.get_value('energy', 'overall')
            outp = acc.get_value('heat', 'overall')
            self._state = round(float(outp) / float(cons), 2) if cons and float(cons) > 0 else None
        except Exception:
            self._state = None

class R290HeatPumpCOPTimeRangeSensor(R290HeatPumpCOPSensorBase):
    """Sensor for COP over a specific time range."""

    def __init__(self, hass, entry, device_info, name, unique_id_suffix, days):
        super().__init__(hass, entry, device_info, name, unique_id_suffix)
        self._days = days

    async def async_update(self):
        """Fetch COP for the specified time range."""
        now = datetime.now()
        start_time = now - timedelta(days=self._days) if self._days > 0 else now.replace(hour=0, minute=0, second=0, microsecond=0)
        _LOGGER.debug(f"Updating {self._attr_name} for range {start_time} to {now}, power_meters={self._power_meters}, heat_meter={self._heat_meter}")

        # Try computing from in-memory accumulator first
        try:
            if self._power_meters and self._heat_meter:
                acc = self._hass.data.get(DOMAIN, {}).get('_cop_acc')
                if acc is not None:
                    try:
                        await acc.async_update()
                    except Exception:
                        pass
                    if self._days == 0:
                        period = 'today'
                    elif self._days == 7:
                        period = '7d'
                    elif self._days == 30:
                        period = '30d'
                    elif self._days == 365:
                        period = '365d'
                    else:
                        period = None
                    if period:
                        cons = acc.get_value('energy', period)
                        outp = acc.get_value('heat', period)
                        if cons and float(cons) > 0:
                            self._state = round(float(outp) / float(cons), 2)
                            return
        except Exception:
            pass

        # Try helper sensors first
        try:
            pslug = _slugify(self._power_meters[0]) if self._power_meters else None
            hslug = _slugify(self._heat_meter) if self._heat_meter else None
            if pslug is None or hslug is None:
                self._state = None
                return
            if self._days == 0:
                p_id = "sensor.r290_heatpump_energy_today"
                h_id = "sensor.r290_heatpump_heat_today"
            elif self._days == 7:
                p_id = "sensor.r290_heatpump_energy_7d"
                h_id = "sensor.r290_heatpump_heat_7d"
            elif self._days == 30:
                p_id = "sensor.r290_heatpump_energy_30d"
                h_id = "sensor.r290_heatpump_heat_30d"
            elif self._days == 365:
                p_id = "sensor.r290_heatpump_energy_365d"
                h_id = "sensor.r290_heatpump_heat_365d"
            else:
                raise RuntimeError("no helper sensor for this period")

            ps = self._hass.states.get(p_id)
            hs = self._hass.states.get(h_id)
            if ps and hs:
                try:
                    cons = float(ps.state)
                    outp = float(hs.state)
                    if cons > 0:
                        self._state = round(outp / cons, 2)
                        return
                except Exception:
                    pass
        except Exception as e:
            _LOGGER.debug("Helper-based COP failed for %s: %s", self._attr_name, e)

        # Use current state values as fallback
        # No fallback when helper values are not ready
        self._state = None

class R290HeatPumpCOPYesterdaySensor(R290HeatPumpCOPSensorBase):
    """Sensor for COP over yesterday (00:00..24:00)."""

    async def async_update(self):
        try:
            # Prefer in-memory accumulator to avoid state ordering issues
            if self._power_meters and self._heat_meter:
                acc = self._hass.data.get(DOMAIN, {}).get('_cop_acc')
                if acc is not None:
                    try:
                        await acc.async_update()
                    except Exception:
                        pass
                    cons = acc.get_value('energy', 'yesterday')
                    outp = acc.get_value('heat', 'yesterday')
                    if cons and float(cons) > 0:
                        self._state = round(float(outp) / float(cons), 2)
                        return
            pslug = _slugify(self._power_meters[0]) if self._power_meters else None
            hslug = _slugify(self._heat_meter) if self._heat_meter else None
            if pslug is None or hslug is None:
                self._state = None
                return
            p_id = "sensor.r290_heatpump_energy_yesterday"
            h_id = "sensor.r290_heatpump_heat_yesterday"
            ps = self._hass.states.get(p_id)
            hs = self._hass.states.get(h_id)
            if not ps or not hs:
                self._state = None
                return
            cons = float(ps.state)
            outp = float(hs.state)
            self._state = round(outp / cons, 2) if cons > 0 else None
        except Exception:
            self._state = None

def setup_cop_sensors(hass, entry, device_info):
    """Set up COP sensors (pure in-memory helpers, no SQL)."""
    heat = entry.data.get("heat_meter")
    power = entry.data.get("power_meter")
    sensors = [
        R290HeatPumpCOPOverallSensor(hass, entry, device_info),
        R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, "COP Last 365 Days", "last_365_days", 365),
        R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, "COP Last 30 Days", "last_30_days", 30),
        R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, "COP Last 7 Days", "last_7_days", 7),
        R290HeatPumpCOPYesterdaySensor(hass, entry, device_info, "COP Yesterday", "yesterday"),
        R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, "COP Today", "today", 0),

    ]

    try:
        start_ts = entry.data.get("cop_start_ts")
        if not start_ts:
            start_ts = int(dt_util.now().timestamp())
            new_data = dict(entry.data)
            new_data["cop_start_ts"] = start_ts
            try:
                hass.config_entries.async_update_entry(entry, data=new_data)
            except Exception:
                pass
    except Exception:
        start_ts = int(dt_util.now().timestamp())

    class _CopAgeSensor(SensorEntity):
        _attr_device_class = None
        _attr_entity_category = EntityCategory.DIAGNOSTIC
        _attr_native_unit_of_measurement = "d"
        SCAN_INTERVAL = timedelta(minutes=5)
        def __init__(self):
            super().__init__()
            self._attr_name = "Days Since Setup"
            self._attr_unique_id = f"r290_heatpump_cop_days_since_setup_{entry.entry_id}"
            self.entity_id = "sensor.r290_heatpump_cop_days_since_setup"
            self._attr_device_info = device_info
            self._state = None
        @property
        def state(self):
            return self._state
        async def async_update(self):
            ts = entry.data.get("cop_start_ts") or start_ts
            try:
                days = int(max(0, (int(dt_util.now().timestamp()) - int(ts)) // 86400))
            except Exception:
                days = 0
            self._state = days

    sensors.append(_CopAgeSensor())

    # Create or reuse accumulator to avoid losing buckets on reloads
    dstore = hass.data.setdefault(DOMAIN, {})
    acc = dstore.get('_cop_acc')
    if isinstance(acc, _EnergyAccumulator):
        try:
            acc.reconfigure(power, heat)
        except Exception:
            pass
    else:
        acc = _EnergyAccumulator(hass, power, heat)
        dstore['_cop_acc'] = acc
    # Ensure state is loaded before first use and persist on shutdown
    async def _ensure_loaded():
        try:
            await acc.async_load()
        except Exception:
            pass
    hass.async_create_task(_ensure_loaded())
    def _on_stop(_):
        hass.async_create_task(acc.async_save())
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)

    async def _acc_update_now():
        try:
            await acc.async_update()
        except Exception:
            pass

    # No scheduler: we support event-driven updates via sensor changes

    class _AccumulatorSensor(SensorEntity):
        _attr_device_class = None
        _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        _attr_state_class = 'measurement'
        _attr_entity_category = EntityCategory.DIAGNOSTIC
        _attr_entity_registry_enabled_default = True
        SCAN_INTERVAL = timedelta(minutes=5)
        def __init__(self, name: str, unique_id: str, entity_id: str, kind: str, period: str):
            super().__init__()
            self._attr_name = name
            self._attr_unique_id = unique_id
            self.entity_id = entity_id
            self._kind = kind
            self._period = period
            self._attr_device_info = device_info
            self._state = None
        @property
        def state(self):
            return self._state
        async def async_update(self):
            acc = self.hass.data.get(DOMAIN, {}).get('_cop_acc')
            if not acc:
                self._state = None
                return
            try:
                await acc.async_update()
            except Exception:
                pass
            val = acc.get_value(self._kind, self._period)
            self._state = round(float(val), 3) if val is not None else None

    if isinstance(power, str) and power:
        sensors.extend([
            _AccumulatorSensor('Energy Overall', f"r290_heatpump_energy_overall_{_slugify(power)}", 'sensor.r290_heatpump_energy_overall', 'energy', 'overall'),
            _AccumulatorSensor('Energy Today',   f"r290_heatpump_energy_today_{_slugify(power)}",   'sensor.r290_heatpump_energy_today',   'energy', 'today'),
            _AccumulatorSensor('Energy Yesterday', f"r290_heatpump_energy_yesterday_{_slugify(power)}", 'sensor.r290_heatpump_energy_yesterday', 'energy', 'yesterday'),
            _AccumulatorSensor('Energy Last 7 Days', f"r290_heatpump_energy_7d_{_slugify(power)}", 'sensor.r290_heatpump_energy_7d', 'energy', '7d'),
            _AccumulatorSensor('Energy Last 30 Days', f"r290_heatpump_energy_30d_{_slugify(power)}", 'sensor.r290_heatpump_energy_30d', 'energy', '30d'),
            _AccumulatorSensor('Energy Last 365 Days', f"r290_heatpump_energy_365d_{_slugify(power)}", 'sensor.r290_heatpump_energy_365d', 'energy', '365d'),
        ])
    if isinstance(heat, str) and heat:
        sensors.extend([
            _AccumulatorSensor('Heat Overall', f"r290_heatpump_heat_overall_{_slugify(heat)}", 'sensor.r290_heatpump_heat_overall', 'heat', 'overall'),
            _AccumulatorSensor('Heat Today',   f"r290_heatpump_heat_today_{_slugify(heat)}",   'sensor.r290_heatpump_heat_today',   'heat', 'today'),
            _AccumulatorSensor('Heat Yesterday', f"r290_heatpump_heat_yesterday_{_slugify(heat)}", 'sensor.r290_heatpump_heat_yesterday', 'heat', 'yesterday'),
            _AccumulatorSensor('Heat Last 7 Days', f"r290_heatpump_heat_7d_{_slugify(heat)}", 'sensor.r290_heatpump_heat_7d', 'heat', '7d'),
            _AccumulatorSensor('Heat Last 30 Days', f"r290_heatpump_heat_30d_{_slugify(heat)}", 'sensor.r290_heatpump_heat_30d', 'heat', '30d'),
            _AccumulatorSensor('Heat Last 365 Days', f"r290_heatpump_heat_365d_{_slugify(heat)}", 'sensor.r290_heatpump_heat_365d', 'heat', '365d'),
        ])
    # Configure event-driven triggers based on options
    try:
        trig_heat = bool(entry.options.get("cop_trigger_on_heat", entry.data.get("cop_trigger_on_heat", False)))
        trig_power = bool(entry.options.get("cop_trigger_on_power", entry.data.get("cop_trigger_on_power", False)))
    except Exception:
        trig_heat = False
        trig_power = False

    if trig_heat or trig_power:
        for s in sensors:
            try:
                s._attr_should_poll = False
            except Exception:
                pass

        async def _on_source_change(event):
            await _acc_update_now()
            try:
                for ent in sensors:
                    ent.async_schedule_update_ha_state(True)
            except Exception:
                pass

        try:
            if trig_power and isinstance(power, str) and power:
                async_track_state_change_event(hass, [power], _on_source_change)
        except Exception:
            pass
        try:
            if trig_heat and isinstance(heat, str) and heat:
                async_track_state_change_event(hass, [heat], _on_source_change)
        except Exception:
            pass

    _LOGGER.debug(f"Created COP sensors: {[s.name for s in sensors]} (event_triggers heat={trig_heat}, power={trig_power})")
    return sensors









