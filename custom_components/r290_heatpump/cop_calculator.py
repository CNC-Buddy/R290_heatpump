# Version: 1.0.2
# Last modified: 2025-11-11 14:11 by CNC-Buddy
import logging
from datetime import datetime, timedelta, date, timezone
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import UnitOfEnergy, STATE_ON, STATE_OFF, EVENT_HOMEASSISTANT_STOP
from homeassistant.util import dt as dt_util
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_state_change_event

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

    def __init__(self, hass, entry, device_info, name, unique_id_suffix, segment: Optional[str] = None):
        """Initialize the COP sensor."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._attr_name = name
        suffix = unique_id_suffix if not segment else f"{unique_id_suffix}_{segment}"
        self._attr_unique_id = f"r290_heatpump_cop_{suffix}"
        self._attr_device_info = device_info
        self._state = None
        self._segment = segment
        self._energy_kind = "energy" if not segment else f"energy_{segment}"
        self._heat_kind = "heat" if not segment else f"heat_{segment}"
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

    def __init__(self, hass, power_entity: str, heat_entity: str, split_enabled: bool = False, split_sensor: Optional[str] = None):
        self._hass = hass
        self._store: Store = Store(hass, 1, f"{DOMAIN}_cop_accumulator")
        self._sources = {
            'energy': {'last': None, 'last_ts': None, 'buckets': {}},
            'heat': {'last': None, 'last_ts': None, 'buckets': {}},
        }
        self._split_buckets = {
            'energy': {'heating': {}, 'hotwater': {}},
            'heat': {'heating': {}, 'hotwater': {}},
        }
        self._entities = {'energy': power_entity, 'heat': heat_entity}
        self._loaded = False
        self._split_enabled = False
        self._split_sensor = None
        self._heat_window_start: Optional[float] = None
        self.configure_split(split_enabled, split_sensor)

    def configure_split(self, enabled: bool, sensor: Optional[str]) -> None:
        self._split_enabled = bool(enabled and sensor)
        self._split_sensor = sensor if self._split_enabled else None

    def reconfigure(self, power_entity: str, heat_entity: str, split_enabled: Optional[bool] = None, split_sensor: Optional[str] = None) -> None:
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
        self._entities = {'energy': power_entity, 'heat': heat_entity}
        if split_enabled is not None or split_sensor is not None:
            enabled = self._split_enabled if split_enabled is None else split_enabled
            sensor = self._split_sensor if split_sensor is None else split_sensor
            self.configure_split(enabled, sensor)

    def _today(self) -> str:
        return dt_util.now().date().isoformat()

    def _bucket_from_ts(self, ts: float) -> str:
        try:
            utc_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            local_dt = dt_util.as_local(utc_dt)
            return local_dt.date().isoformat()
        except Exception:
            return self._today()

    def _add_delta_to_bucket(self, buckets: dict, delta: float, bucket_key: Optional[str] = None) -> bool:
        if delta <= 0:
            return False
        key = bucket_key or self._today()
        buckets[key] = float(buckets.get(key, 0.0) + delta)
        if len(buckets) > 520:
            try:
                for d in sorted(buckets.keys())[:-520]:
                    buckets.pop(d, None)
            except Exception:
                pass
        return True

    def _add_delta(self, kind: str, delta: float, bucket_key: Optional[str] = None) -> bool:
        return self._add_delta_to_bucket(self._sources[kind]['buckets'], delta, bucket_key)

    def _current_segment(self) -> Optional[str]:
        if not self._split_enabled or not self._split_sensor:
            return None
        st = self._hass.states.get(self._split_sensor)
        if not st or st.state in (None, 'unknown', 'unavailable'):
            return None
        state = str(st.state).lower()
        if state == STATE_ON:
            return 'hotwater'
        if state == STATE_OFF:
            return 'heating'
        return None

    def _add_split_delta(self, kind: str, delta: float, bucket_key: Optional[str] = None, mode: Optional[str] = None) -> None:
        if not self._split_enabled:
            return
        if mode is None:
            mode = self._current_segment()
        if mode is None:
            return
        try:
            self._add_delta_to_bucket(self._split_buckets[kind][mode], delta, bucket_key)
        except Exception:
            pass

    def _distribute_heat_delta(self, delta: float, start_ts: Optional[float], end_ts: float) -> bool:
        if delta <= 0:
            return False
        if start_ts is None or start_ts >= end_ts:
            bucket = self._bucket_from_ts(end_ts)
            changed = self._add_delta('heat', delta, bucket)
            self._add_split_delta('heat', delta, bucket_key=bucket)
            return changed
        try:
            start_utc = datetime.fromtimestamp(float(start_ts), tz=timezone.utc)
            end_utc = datetime.fromtimestamp(float(end_ts), tz=timezone.utc)
        except Exception:
            bucket = self._bucket_from_ts(end_ts)
            changed = self._add_delta('heat', delta, bucket)
            self._add_split_delta('heat', delta, bucket_key=bucket)
            return changed
        start_local = dt_util.as_local(start_utc)
        end_local = dt_util.as_local(end_utc)
        if end_local <= start_local:
            bucket = self._bucket_from_ts(end_ts)
            changed = self._add_delta('heat', delta, bucket)
            self._add_split_delta('heat', delta, bucket_key=bucket)
            return changed
        total_seconds = (end_local - start_local).total_seconds()
        if total_seconds <= 0:
            bucket = self._bucket_from_ts(end_ts)
            changed = self._add_delta('heat', delta, bucket)
            self._add_split_delta('heat', delta, bucket_key=bucket)
            return changed
        segments = []
        cursor = start_local
        while cursor < end_local:
            day_end = datetime(
                cursor.year,
                cursor.month,
                cursor.day,
                tzinfo=cursor.tzinfo,
            ) + timedelta(days=1)
            seg_end = min(day_end, end_local)
            seconds = max(0.0, (seg_end - cursor).total_seconds())
            segments.append((seconds, cursor.date().isoformat()))
            cursor = seg_end
        allocated = 0.0
        changed = False
        for idx, (seconds, bucket_key) in enumerate(segments):
            if idx == len(segments) - 1:
                share = max(0.0, delta - allocated)
            else:
                share = delta * (seconds / total_seconds) if total_seconds > 0 else 0.0
                allocated += share
            if share <= 0:
                continue
            if self._add_delta('heat', share, bucket_key):
                changed = True
            self._add_split_delta('heat', share, bucket_key=bucket_key)
        return changed

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
                        self._sources[kind]['buckets'] = {str(k): float(v) for k, v in (ksrc.get('buckets') or {}).items()}
                        try:
                            self._sources[kind]['last'] = float(ksrc.get('last')) if ksrc.get('last') is not None else None
                        except Exception:
                            self._sources[kind]['last'] = None
                        try:
                            self._sources[kind]['last_ts'] = float(ksrc.get('last_ts')) if ksrc.get('last_ts') is not None else None
                        except Exception:
                            self._sources[kind]['last_ts'] = None
                split = data.get('split') or {}
                buckets = split.get('buckets') or {}
                for kind in ('energy', 'heat'):
                    per_kind = buckets.get(kind, {})
                    for mode in ('heating', 'hotwater'):
                        kb = per_kind.get(mode, {})
                        self._split_buckets[kind][mode] = {str(k): float(v) for k, v in kb.items()}
                ent = data.get('entities') or {}
                self.reconfigure(ent.get('energy', self._entities['energy']), ent.get('heat', self._entities['heat']))
                if 'enabled' in split or 'sensor' in split:
                    self.configure_split(split.get('enabled', False), split.get('sensor'))
                meta = data.get('meta') or {}
                try:
                    self._heat_window_start = float(meta.get('heat_window_start')) if meta.get('heat_window_start') is not None else None
                except Exception:
                    self._heat_window_start = None
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
                        'last_ts': self._sources['energy']['last_ts'],
                    },
                    'heat': {
                        'buckets': self._sources['heat']['buckets'],
                        'last': self._sources['heat']['last'],
                        'last_ts': self._sources['heat']['last_ts'],
                    },
                },
                'entities': dict(self._entities),
                'split': {
                    'buckets': self._split_buckets,
                    'enabled': self._split_enabled,
                    'sensor': self._split_sensor,
                },
                'meta': {
                    'heat_window_start': self._heat_window_start,
                },
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
            now_ts = dt_util.utcnow().timestamp()
            last = self._sources[kind]['last']
            last_ts = self._sources[kind].get('last_ts')
            if last is None:
                self._sources[kind]['last'] = current
                self._sources[kind]['last_ts'] = now_ts
                if kind == 'heat' and self._heat_window_start is None:
                    self._heat_window_start = now_ts
                continue
            delta = current - last
            if delta < 0:
                self._sources[kind]['last'] = current
                self._sources[kind]['last_ts'] = now_ts
                continue
            if kind == 'heat' and delta > 0:
                if self._distribute_heat_delta(delta, self._heat_window_start or last_ts, now_ts):
                    changed = True
                self._heat_window_start = now_ts
            elif delta > 0:
                bucket_key = self._today()
                if self._add_delta(kind, delta, bucket_key):
                    changed = True
                    self._add_split_delta(kind, delta, bucket_key=bucket_key)
            self._sources[kind]['last'] = current
            self._sources[kind]['last_ts'] = now_ts
        if changed:
            await self.async_save()

    def _resolve_buckets(self, kind: str):
        if kind in self._sources:
            return self._sources[kind]['buckets']
        if '_' in kind:
            base, mode = kind.split('_', 1)
            if base in self._split_buckets and mode in self._split_buckets[base]:
                return self._split_buckets[base][mode]
        return {}

    def _sum_days(self, kind: str, days: int) -> float:
        buckets = self._resolve_buckets(kind)
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
        buckets = self._resolve_buckets(kind)
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

    def __init__(self, hass, entry, device_info, name="COP Overall", unique_id_suffix="overall", segment: Optional[str] = None):
        super().__init__(hass, entry, device_info, name, unique_id_suffix, segment)

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
            cons = acc.get_value(self._energy_kind, 'overall')
            outp = acc.get_value(self._heat_kind, 'overall')
            self._state = round(float(outp) / float(cons), 2) if cons and float(cons) > 0 else None
        except Exception:
            self._state = None

class R290HeatPumpCOPTimeRangeSensor(R290HeatPumpCOPSensorBase):
    """Sensor for COP over a specific time range."""

    def __init__(self, hass, entry, device_info, name, unique_id_suffix, days, segment: Optional[str] = None):
        super().__init__(hass, entry, device_info, name, unique_id_suffix, segment)
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
                        cons = acc.get_value(self._energy_kind, period)
                        outp = acc.get_value(self._heat_kind, period)
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
                base = "today"
            elif self._days == 7:
                base = "7d"
            elif self._days == 30:
                base = "30d"
            elif self._days == 365:
                base = "365d"
            else:
                raise RuntimeError("no helper sensor for this period")
            suffix = ""
            if self._segment == "heating":
                suffix = "_heating"
            elif self._segment == "hotwater":
                suffix = "_hotwater"
            p_id = f"sensor.r290_heatpump_energy_{base}{suffix}"
            h_id = f"sensor.r290_heatpump_heat_{base}{suffix}"

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
                    cons = acc.get_value(self._energy_kind, 'yesterday')
                    outp = acc.get_value(self._heat_kind, 'yesterday')
                    if cons and float(cons) > 0:
                        self._state = round(float(outp) / float(cons), 2)
                        return
            pslug = _slugify(self._power_meters[0]) if self._power_meters else None
            hslug = _slugify(self._heat_meter) if self._heat_meter else None
            if pslug is None or hslug is None:
                self._state = None
                return
            suffix = ""
            if self._segment == "heating":
                suffix = "_heating"
            elif self._segment == "hotwater":
                suffix = "_hotwater"
            p_id = f"sensor.r290_heatpump_energy_yesterday{suffix}"
            h_id = f"sensor.r290_heatpump_heat_yesterday{suffix}"
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
    split_sensor = entry.options.get("cop_split_sensor", entry.data.get("cop_split_sensor"))
    split_flag = bool(entry.options.get("cop_split_enabled", entry.data.get("cop_split_enabled", False)))
    if not isinstance(split_sensor, str) or not split_sensor:
        split_sensor = None
    split_enabled = bool(split_flag and split_sensor)

    def _mode_label(segment: Optional[str]) -> str:
        if segment == "heating":
            return " (Heating)"
        if segment == "hotwater":
            return " (Warm Water)"
        return ""

    segments = [None]
    if split_enabled:
        segments.extend(["heating", "hotwater"])

    sensors = []
    for segment in segments:
        label = _mode_label(segment)
        sensors.append(R290HeatPumpCOPOverallSensor(hass, entry, device_info, f"COP Overall{label}", "overall", segment=segment))
        sensors.append(R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, f"COP Last 365 Days{label}", "last_365_days", 365, segment))
        sensors.append(R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, f"COP Last 30 Days{label}", "last_30_days", 30, segment))
        sensors.append(R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, f"COP Last 7 Days{label}", "last_7_days", 7, segment))
        sensors.append(R290HeatPumpCOPYesterdaySensor(hass, entry, device_info, f"COP Yesterday{label}", "yesterday", segment=segment))
        sensors.append(R290HeatPumpCOPTimeRangeSensor(hass, entry, device_info, f"COP Today{label}", "today", 0, segment))

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
            acc.reconfigure(power, heat, split_enabled=split_enabled, split_sensor=split_sensor)
        except Exception:
            pass
    else:
        acc = _EnergyAccumulator(hass, power, heat, split_enabled=split_enabled, split_sensor=split_sensor)
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
        def __init__(self, name: str, unique_id: str, entity_id: str, kind: str, period: str, segment: Optional[str] = None):
            super().__init__()
            self._attr_name = name
            self._attr_unique_id = unique_id
            self.entity_id = entity_id
            self._kind = kind if not segment else f"{kind}_{segment}"
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

    diag_segments = segments
    if isinstance(power, str) and power:
        slug = _slugify(power)
        energy_defs = [
            ("Energy Overall", f"r290_heatpump_energy_overall_{slug}", "sensor.r290_heatpump_energy_overall", "overall"),
            ("Energy Today", f"r290_heatpump_energy_today_{slug}", "sensor.r290_heatpump_energy_today", "today"),
            ("Energy Yesterday", f"r290_heatpump_energy_yesterday_{slug}", "sensor.r290_heatpump_energy_yesterday", "yesterday"),
            ("Energy Last 7 Days", f"r290_heatpump_energy_7d_{slug}", "sensor.r290_heatpump_energy_7d", "7d"),
            ("Energy Last 30 Days", f"r290_heatpump_energy_30d_{slug}", "sensor.r290_heatpump_energy_30d", "30d"),
            ("Energy Last 365 Days", f"r290_heatpump_energy_365d_{slug}", "sensor.r290_heatpump_energy_365d", "365d"),
        ]
        for name, unique_id, entity_id, period in energy_defs:
            for segment in diag_segments:
                label = f"{name}{_mode_label(segment)}"
                suffix = "" if not segment else f"_{segment}"
                sensors.append(
                    _AccumulatorSensor(
                        label,
                        f"{unique_id}{suffix}",
                        f"{entity_id}{suffix}",
                        'energy',
                        period,
                        segment,
                    )
                )
    if isinstance(heat, str) and heat:
        slug = _slugify(heat)
        heat_defs = [
            ("Heat Overall", f"r290_heatpump_heat_overall_{slug}", "sensor.r290_heatpump_heat_overall", "overall"),
            ("Heat Today", f"r290_heatpump_heat_today_{slug}", "sensor.r290_heatpump_heat_today", "today"),
            ("Heat Yesterday", f"r290_heatpump_heat_yesterday_{slug}", "sensor.r290_heatpump_heat_yesterday", "yesterday"),
            ("Heat Last 7 Days", f"r290_heatpump_heat_7d_{slug}", "sensor.r290_heatpump_heat_7d", "7d"),
            ("Heat Last 30 Days", f"r290_heatpump_heat_30d_{slug}", "sensor.r290_heatpump_heat_30d", "30d"),
            ("Heat Last 365 Days", f"r290_heatpump_heat_365d_{slug}", "sensor.r290_heatpump_heat_365d", "365d"),
        ]
        for name, unique_id, entity_id, period in heat_defs:
            for segment in diag_segments:
                label = f"{name}{_mode_label(segment)}"
                suffix = "" if not segment else f"_{segment}"
                sensors.append(
                    _AccumulatorSensor(
                        label,
                        f"{unique_id}{suffix}",
                        f"{entity_id}{suffix}",
                        'heat',
                        period,
                        segment,
                    )
                )
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
        try:
            if split_enabled and split_sensor:
                async_track_state_change_event(hass, [split_sensor], _on_source_change)
        except Exception:
            pass

    _LOGGER.debug(f"Created COP sensors: {[s.name for s in sensors]} (event_triggers heat={trig_heat}, power={trig_power}, split={split_enabled})")
    return sensors
