export const phaseNames = {
  idle: "Bereit", startup: "Anlauf", heating: "Heizen", dhw: "Warmwasser",
  defrost: "Abtauen", postrun: "Nachlauf", circulation: "Umwälzen",
  flow_guard: "Durchfluss sichern", fallback: "Ersatzbetrieb", initializing: "Initialisierung"
};
export const modeNames = {observe: "Beobachten", manual: "Fester Stellwert", auto: "Automatisch"};
export const reasons = {
  hydraulic_path_closed: "Interne Pumpen aus: Zusatzpumpe stoppen. Kein Nachlauf gegen geschlossene Kugelhähne.",
  demand_unavailable_hold: "Pumpenfreigabe unbekannt: Ausgang unverändert lassen, kein Startbefehl.",
  waiting_to_resume: "Gespeicherte Regelung wartet auf gültige Freigabe und Stellgliedrückmeldung.",
  resumed_control: "Zuvor freigegebene Regelung nach gültigen Eingangssignalen fortgesetzt.",
  controller_suspended: "Regler angehalten. Freigegebene Betriebsart für das Neuladen gespeichert.",
  defrost_priority: "Abtauung aktiv. Der konfigurierte Abtaustellwert hat Vorrang.",
  invalid_inputs: "Betriebsdaten fehlen oder sind veraltet. Keine Absenkung unter den Ersatzstellwert.",
  postrun_timer: "Keine Anforderung mehr. Die konfigurierte Nachlaufzeit läuft.",
  no_demand: "Keine Anforderung, kein Verdichter und keine Abtauung. Nachlauf beendet.",
  flow_unavailable: "Der Durchfluss einer laufenden Wärmepumpe ist nicht verlässlich verfügbar.",
  minimum_flow: "Mindestens eine laufende Wärmepumpe unterschreitet den eingestellten Mindestdurchfluss.",
  settling_timer: "Der Wasserkreis läuft an. Die Regelung wartet die Beruhigungszeit ab.",
  demand_without_compressor: "Umwälzung angefordert, beide Verdichter stehen. Ersatzstellwert bleibt erhalten.",
  temperature_unavailable: "Die Temperaturspreizung ist unvollständig oder unplausibel.",
  manual_target: "Fester Stellwert innerhalb der Grenzen. Durchflussschutz und Abtauung bleiben vorrangig.",
  adjustment_interval: "Wartezeit bis zum nächsten Regelschritt.",
  increase_flow: "Die größte Spreizung liegt über dem Zielband. Ansteuerung schrittweise erhöhen.",
  reduce_flow: "Alle aktiven Spreizungen liegen unter dem Zielband. Ansteuerung schrittweise reduzieren.",
  within_deadband: "Die Spreizung liegt im Zielband. Stellwert halten.",
  automation_conflict: "Eine bestehende Pumpenautomation ist aktiv oder nicht verfügbar. Steuerung abgegeben.",
  write_failed: "Der Stellbefehl ist fehlgeschlagen oder seine Ausführung ist unklar. Erneute Freigabe erforderlich.",
  actuator_feedback: "Die Stellglied-Entität bestätigt den angeforderten Wert nicht. Steuerung angehalten; Ausgang und Kommunikation prüfen.",
  started_in_observe: "Regler gestartet. Beobachtungsmodus aktiv.",
  stopped_without_output_change: "Regler beendet. Ausgang nicht verändert."
};
export const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export const numeric = value => value === null || value === undefined || value === "" || !Number.isFinite(Number(value)) ? null : Number(value);
let locale='de-DE';
export const setLocale = language => {locale=language==='en'?'en-GB':'de-DE';};
export const fmt = (value, digits=1) => numeric(value) === null ? "—" : Number(value).toLocaleString(locale, {maximumFractionDigits:digits});
export const energyFactor = unit => ({Wh:0.001,kWh:1,MWh:1000,MJ:1/3.6,GJ:1000/3.6}[unit] ?? null);
export function ageLabel(seconds) {
  if (!Number.isFinite(seconds)) return "Zeitpunkt unbekannt";
  if (seconds < 60) return "vor weniger als 1 Min.";
  if (seconds < 3600) return `vor ${Math.floor(seconds/60)} Min.`;
  if (seconds < 86400) return `vor ${fmt(seconds/3600,1)} Std.`;
  return `vor ${fmt(seconds/86400,1)} Tagen`;
}
export function parameterRows(entities, entries, states, {query="", group="all", differences=false}={}) {
  const entryMap = new Map(entries.map(e=>[e.id,e]));
  const rows = new Map();
  for (const e of entities) {
    const entry = entryMap.get(e.entry_id);
    if (!entry || entry.type === "auxiliary_pump" || e.disabled || !/^(number|select|switch)\./.test(e.id)) continue;
    if (group !== "all" && entry.type !== group) continue;
    const key = entry.type === "heat_pump" ? e.unique_id.replace(/_slave_\d+(?:_v2)?$/, "") : e.unique_id;
    const row = rows.get(key) || {key, name:e.name.replace(/\s*\(Slave \d+\)/g,""), type:entry.type, cells:[]};
    row.cells.push({...e, entry, state:states[e.id]});
    rows.set(key,row);
  }
  return [...rows.values()].filter(row=>{
    const known = row.cells.map(c=>c.state?.state).filter(v=>v!==undefined && !["unknown","unavailable"].includes(v));
    row.different = known.length > 1 && new Set(known.map(v=>numeric(v)??v)).size > 1;
    return (!differences || row.different) && `${row.name} ${row.cells.map(c=>c.id).join(" ")}`.toLowerCase().includes(query.toLowerCase());
  }).sort((a,b)=>a.name.localeCompare(b.name,"de",{numeric:true}));
}
export function chartPaths(points, start, end, min, max, width=680, height=180) {
  const x=t=>32+(Math.max(start,Math.min(end,t))-start)/Math.max(1,end-start)*(width-48);
  const y=v=>12+(max-v)/Math.max(0.001,max-min)*(height-38);
  let path="", pen=false, previous=null;
  for(const [time, raw] of points) {
    if(time>end) break;
    const value=numeric(raw);
    if(value===null) { if(pen)path+=`H${x(time).toFixed(1)}`;pen=false;previous=null;continue; }
    const px=x(time).toFixed(1), py=y(value).toFixed(1);
    if(!pen) path+=`M${px},${py}`;
    else path+=`H${px}V${py}`;
    pen=true; previous=value;
  }
  if(pen && previous!==null) path+=`H${x(end).toFixed(1)}`;
  return path;
}
