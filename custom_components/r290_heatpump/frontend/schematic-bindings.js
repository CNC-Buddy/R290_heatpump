// Display sources are specific to the component; old mappings remain in saved
// graphs for compatibility, but irrelevant readings are neither offered nor drawn.
const labels={
  value:['Messwert','Reading'],supply:['Vorlauftemperatur','Supply temperature'],return:['Rücklauftemperatur','Return temperature'],
  status:['Pumpen-/Betriebsrückmeldung','Pump / operation feedback'],flow:['Gemessener Durchfluss','Measured flow'],
  phase:['Ventilzweig: an = A (WW), aus = B (Heizen)','Valve branch: on = A (DHW), off = B (heating)'],
  fan:['Lüfterrückmeldung / Drehzahl','Fan feedback / speed'],soc:['Ladezustand','State of charge']
};
const powerLabels={grid:['Netzleistung · Bezug / Einspeisung','Grid power · import / export'],pv:['PV-Leistung','PV power'],battery:['Batterieleistung · Laden / Entladen','Battery power · charge / discharge'],house:['Hausverbrauch · Leistung','Home consumption · power'],heater:['Leistungsaufnahme','Power consumption']};
export function bindingsFor(node){
  const keys=node.circuit==='electric'?(node.type==='battery'?['value','soc']:node.type==='heater'?['value','status']:node.type==='junction'?[]:['value']):['fan','value','supply','return','status','flow','phase'].filter(k=>(k!=='fan'||node.type==='heat_pump')&&(k!=='phase'||node.type==='valve'));
  return keys.map(key=>({key,label:node.circuit==='electric'&&key==='value'?powerLabels[node.type]||['Elektrische Leistung','Electrical power']:node.circuit==='electric'&&key==='status'?['Betriebsrückmeldung','Operation feedback']:labels[key],units:key==='soc'?['%']:node.circuit==='electric'&&key==='value'?['W','kW','MW']:['supply','return'].includes(key)?['°C','°F','K']:null}));
}
export function bindingHelp(node,en){
  if(node.circuit==='electric')return en?'Assign electrical readings. Positive/negative power values are shown as supplied by the sensor; check its import/export or charge/discharge convention.':'Elektrische Messwerte zuordnen. Positive und negative Leistungen werden wie vom Sensor geliefert angezeigt; dessen Vorzeichen für Bezug/Einspeisung bzw. Laden/Entladen beachten.';
  if(node.type==='valve')return en?'Choose a clear DHW signal for branch A; off selects heating branch B.':'Ein eindeutiges Warmwassersignal für Zweig A wählen; aus entspricht Heizen über Zweig B.';
  return en?'Assign measured values and feedback. These sources only affect the display.':'Messwerte und Rückmeldungen zuordnen. Diese Quellen dienen ausschließlich der Anzeige.';
}
