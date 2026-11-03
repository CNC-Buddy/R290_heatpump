"""Build the shared display-component port catalogue (no device parameters)."""
import json
from pathlib import Path

CATALOG = {}


def port(x, y, side, direction, leg, label, circuit="$", en=None):
    return dict(x=x, y=y, side=side, direction=direction, leg=leg,
                circuit=circuit, label=[label, en or label])


def component(key, de, en, width, height, ports, groups, circuits,
              legs=("supply",), closed=False, all_ports=False):
    CATALOG[key] = dict(label=[de, en], width=width, height=height, ports=ports,
                        groups=groups, circuits=list(circuits), legs=list(legs),
                        closed_loop=closed, require_all=all_ports)


for kind, de, en, fluid in [("heat_pump", "Wärmepumpe", "Heat pump", "wp"),
                            ("heat_source", "Wärmeerzeuger 2", "Heat source 2", "we2")]:
    component(kind, de, en, 180, 120, {
        "supply": port(180, 30, "right", "out", "supply", "Vorlauf", en="Supply"),
        "return": port(180, 90, "right", "in", "return", "Rücklauf", en="Return")},
        [["return", "supply"]], [fluid], closed=True, all_ports=True)

for kind, de, en, legs in [("pump", "Umwälzpumpe", "Circulation pump", ["supply", "return"]),
                            ("heat_meter", "Wärmemengenzähler", "Heat meter", ["return"])]:
    component(kind, de, en, 100, 80, {
        "in": port(0, 40, "left", "in", "$", "Ein", en="In"),
        "out": port(100, 40, "right", "out", "$", "Aus", en="Out")},
        [["in", "out"]], ["wp", "heating", "we2", "warmwater"] if kind == "pump" else ["wp", "heating"],
        legs, closed=kind == "pump", all_ports=True)

component("valve", "3/2-Wege-Ventil", "3/2-way valve", 100, 100, {
    "common": port(0, 50, "left", "in", "supply", "AB · Vorlauf", en="AB · Supply"),
    "a": port(100, 20, "right", "out", "supply", "A · Warmwasser", en="A · Hot water"),
    "b": port(100, 80, "right", "out", "supply", "B · Heizen", en="B · Heating")},
    [["common", "a", "b"]], ["wp", "heating", "we2"], all_ports=True)

component("plate", "Plattenwärmetauscher", "Plate heat exchanger", 100, 140, {
    "primary_in": port(0, 30, "left", "in", "supply", "Primär · VL", "wp", "Primary · supply"),
    "primary_out": port(0, 110, "left", "out", "return", "Primär · RL", "wp", "Primary · return"),
    "secondary_out": port(100, 30, "right", "out", "supply", "Sekundär · VL", "heating", "Secondary · supply"),
    "secondary_in": port(100, 110, "right", "in", "return", "Sekundär · RL", "heating", "Secondary · return")},
    [["primary_in", "primary_out"], ["secondary_in", "secondary_out"]], ["wp"], all_ports=True)

component("dhw_tank", "Warmwasserspeicher", "Hot-water tank", 160, 280, {
    "wp_in": port(0, 60, "left", "in", "supply", "WP-Wendel · VL", "wp", "HP coil · supply"),
    "wp_out": port(0, 110, "left", "out", "return", "WP-Wendel · RL", "wp", "HP coil · return"),
    "we2_in": port(0, 180, "left", "in", "supply", "WE2-Wendel · VL", "we2", "Source 2 coil · supply"),
    "we2_out": port(0, 230, "left", "out", "return", "WE2-Wendel · RL", "we2", "Source 2 coil · return"),
    "hot": port(160, 60, "right", "out", "supply", "Warmwasser", "warmwater", "Hot water"),
    "circulation": port(160, 230, "right", "in", "return", "Zirkulation zurück", "warmwater", "Circulation return")},
    [["wp_in", "wp_out"], ["we2_in", "we2_out"], ["circulation", "hot"]], ["wp"])

component("buffer", "Heizungspuffer", "Heating buffer", 160, 280, {
    "charge_in": port(0, 50, "left", "in", "supply", "Ladung · VL", en="Charge · supply"),
    "charge_out": port(0, 110, "left", "out", "return", "Ladung · RL", en="Charge · return"),
    "heating_out": port(160, 50, "right", "out", "supply", "Heizkreis · VL", en="Heating · supply"),
    "heating_in": port(160, 110, "right", "in", "return", "Heizkreis · RL", en="Heating · return"),
    "we2_in": port(0, 190, "left", "in", "supply", "WE2-Wendel · VL", "we2", "Source 2 coil · supply"),
    "we2_out": port(0, 240, "left", "out", "return", "WE2-Wendel · RL", "we2", "Source 2 coil · return")},
    [["charge_in", "charge_out"], ["heating_in", "heating_out"], ["we2_in", "we2_out"]], ["wp", "heating"])

component("radiator", "Heizkreis", "Heating circuit", 160, 120, {
    "in": port(0, 30, "left", "in", "supply", "Vorlauf", en="Supply"),
    "out": port(0, 90, "left", "out", "return", "Rücklauf", en="Return")},
    [["in", "out"]], ["wp", "heating"], all_ports=True)

component("junction", "T-Stück", "T junction", 40, 40, {
    "a": port(0, 20, "left", "any", "$", "A"),
    "b": port(40, 20, "right", "any", "$", "B"),
    "c": port(20, 40, "bottom", "any", "$", "C")},
    [["a", "b", "c"]], ["wp", "heating", "we2", "warmwater", "electric"], ["supply", "return", "power"], all_ports=True)

component("circulation_end", "Zirkulationsumkehr", "Circulation turnaround", 60, 120, {
    "hot": port(0, 20, "left", "in", "supply", "Warmwasser", "warmwater", "Hot water"),
    "return": port(0, 100, "left", "out", "return", "Zirkulation", "warmwater", "Circulation")},
    [["hot", "return"]], ["warmwater"], all_ports=True)
component("tap", "Warmwasser-Zapfstelle", "Hot-water outlet", 120, 80, {
    "in": port(60, 80, "bottom", "in", "supply", "Abzweig Warmwasser", "warmwater", "Hot-water branch")},
    [["in"]], ["warmwater"], all_ports=True)

for kind, de, en in [("pv", "Photovoltaik", "Photovoltaics"), ("battery", "Batteriespeicher", "Battery"),
                     ("grid", "Stromnetz", "Grid"), ("house", "Hausverbrauch", "Home consumption"),
                     ("heater", "Heizstab", "Immersion heater")]:
    component(kind, de, en, 140, 100, {"power": port(70, 100, "bottom", "any", "power", "Elektrisch", "electric", "Electric")},
              [["power"]], ["electric"], ["power"])

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "custom_components/r290_heatpump/frontend/schematic-catalog.json"
    target.write_text(json.dumps(CATALOG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(CATALOG)} component types written")
