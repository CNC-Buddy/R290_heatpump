"""Read the five source workbooks without modifying them; audit static definitions.

Run with openpyxl available. Generated JSON is shipped; HA does not need openpyxl.
"""
import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
try:
    from scripts.parameter_translations import apply as translate_parameters
except ModuleNotFoundError:
    from parameter_translations import apply as translate_parameters

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/r290_heatpump"
EN_DESCRIPTIONS = {
    "P012": "The value must be less than or equal to P11.",
    "P022": "If ambient temperature is equal to or below P22, the unit does not start; start defrosting.",
    "P023": "Alarm when the value is exceeded.",
    "P165": "Determines when the next unit is switched on.",
    "P166": "Determines when the next unit is switched off.",
    "P167": "Determines whether the unit is switched off.",
    "P168": "Limits the total number of units that can start.",
    "P170": "Delay before activating the next unit.",
    "P179": "Enabling power mode increases the compressor frequency by the selected number of Hz each time.",
    "P180": "Enabling power mode increases the maximum compressor frequency by the selected number of Hz above the original maximum operating frequency.",
}


def definitions():
    result = []
    for filename in ("main.py", "realtimedata.py", "unit_system_parameters.py", "user_parameters.py"):
        tree = ast.parse((COMPONENT / filename).read_text(encoding="utf-8-sig"))
        constants = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                try:
                    constants[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
        for assignment in tree.body:
            if not isinstance(assignment, ast.Assign) or not isinstance(assignment.value, ast.List):
                continue
            group = assignment.targets[0].id
            for node in assignment.value.elts:
                if not isinstance(node, ast.Dict):
                    continue
                values = {}
                for key, value in zip(node.keys, node.values):
                    try:
                        values[ast.literal_eval(key)] = ast.literal_eval(value)
                    except (ValueError, TypeError):
                        if isinstance(value, ast.Name) and value.id in constants:
                            values[ast.literal_eval(key)] = constants[value.id]
                if isinstance(values.get("address"), int):
                    values.update(source=filename, group=group)
                    result.append(values)
    return result


def build():
    import openpyxl
    defs = definitions()
    help_path = ROOT / "Documentation/system-parameter-help.json"
    supplementary = json.loads(help_path.read_text(encoding="utf-8"))["parameters"] if help_path.exists() else {}
    records, sources = [], []
    for index, pattern in enumerate(("1.*xlsx", "2.*xlsx", "3.*xlsx", "4 *xlsx", "5 *xlsx"), 1):
        path = next((ROOT / "Documentation").glob(pattern))
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = book.active
        sources.append(dict(file=path.name, sheet=sheet.title, sha256=sha256(path.read_bytes()).hexdigest()))
        for rownum, row in enumerate(sheet.iter_rows(values_only=True), 1):
            address = row[1] if index == 4 else row[0]
            if not isinstance(address, str) or not re.fullmatch(r"0[xX][0-9a-fA-F]{4}", address.strip()):
                continue
            address = int(address, 16)
            record = dict(section=index, file=path.name, sheet=sheet.title, row=rownum,
                          address=address, hex=f"0x{address:04X}", kind="coil" if address >= 0x1000 else "holding")
            if index == 4:
                record.update(code=row[0], name=row[3], name_de=row[4], min=row[5], max=row[6],
                              default_manual=row[7], default_observed=row[8], unit=row[9],
                              description=row[12], description_de=row[13])
                if not row[12] and row[13] and row[0] in EN_DESCRIPTIONS:
                    record["description_en"] = EN_DESCRIPTIONS[row[0]]
                    record["description_en_origin"] = "Translation of description_de"
            elif index == 2:
                record.update(name=row[5], use=row[3], range=row[6], unit=row[7], default_manual=row[8], access=row[9], description=row[10])
                if address == 0x0057:
                    record.update(
                        name_de="Pumpendrehzahl",
                        display_name_en="Pump speed",
                        description_de="Pump speed zeigt die umgerechnete Ansteuerung der internen Umwälzpumpe: 100 minus PWM-Rohwert, in %. PWM 100 ergibt 0 % (aus), PWM 0 ergibt 100 % (maximale Ansteuerung). Keine gemessene Drehzahl oder elektrische Leistung; eine Pumpenkennlinie wird nicht nachgebildet. Der separate Diagnosesensor Pump speed PWM und die Rohregister behalten die ursprünglichen Werte. Werte außerhalb 0–100 werden für die Prozentanzeige als nicht verfügbar behandelt.",
                        description_en="Pump speed displays normalized internal circulation-pump demand: 100 minus raw PWM, in %. PWM 100 becomes 0% (off), PWM 0 becomes 100% (maximum demand). Not measured RPM or electrical power; no pump characteristic curve is modeled. The separate Pump speed PWM diagnostic sensor and raw registers retain the original values. Values outside 0–100 make the percentage sensor unavailable.",
                    )
            elif index == 1:
                record.update(name=row[1], range=row[2], default_manual=row[3], access=row[4], description=row[5], bits=row[6])
            elif index == 3:
                record.update(name=row[1], description=row[2], access=row[3])
            else:
                record.update(name=row[1], range=row[2], access=row[3], description=row[4])
            name = record.get("name")
            if index == 4 and record.get("code") in supplementary:
                help_record = supplementary[record["code"]]
                if help_record["address"] != address:
                    raise ValueError(f"Explanation address mismatch: {record['code']}")
                record.update(description_de=help_record["de"], description_en=help_record["en"],
                              explanation_level=help_record["level"], explanation_sources=help_record["sources"])
            record["unknown"] = not isinstance(name, str) or not name.strip() or bool(re.fullmatch(r"[?？\s]+|unknown|reserved", name.strip(), re.I))
            matches = [d for d in defs if d["address"] == address and record["kind"] == "holding"]
            record["entities"] = [{k: d[k] for k in ("unique_id", "name", "group", "enabled_by_default", "min_value", "max_value", "scale", "offset", "valid_raw_range", "data_type") if k in d} for d in matches]
            record["coverage"] = "defined" if matches else "undocumented" if record["unknown"] else "missing"
            record["issues"] = []
            if index == 4 and matches:
                for field, source in (("min", "min_value"), ("max", "max_value")):
                    actual = matches[0].get(source)
                    if isinstance(record.get(field), (int, float)) and actual is not None and actual != record[field]:
                        record["issues"].append(f"{field}: Excel {record[field]}, Integration {actual}")
            if index == 1 and record.get("bits"):
                known_bits = set().union(*(set(d.get("bit_labels", {})) for d in matches))
                for bit, label in re.findall(r"Bit(\d+)\s*:?\t([^\n]*)", record["bits"]):
                    if label.strip(' \"') and label.strip(' \"').lower() not in ("reserved", "na") and int(bit) not in known_bits:
                        record["issues"].append(f"Bit {bit} nicht einzeln beschriftet: {label.strip()}")
            if address == 0x080B:
                record["issues"].append("Nur Schalter 0/1 implementiert; Modi 2 und 3 aus Excel fehlen.")
            records.append(record)
        book.close()
    translate_parameters(records)
    counts = [{"section": i, **dict(Counter(r["coverage"] for r in records if r["section"] == i))} for i in range(1, 6)]
    payload = dict(sources=sources, counts=counts, records=records,
                   notes=["Abgleich der Registerdefinitionen, kein Beleg für live aktivierte Entitäten oder Datenempfang.",
                          "User-Parameter-Entitäten (lesend und schreibend) werden nur für Slave 1 angelegt; Main-Sensoren weiterer Slaves sind meist standardmäßig deaktiviert.",
                          "System-Tabelle: Überschrift 0x0200–0x03FF widerspricht den Zeilenadressen 0x0100–0x0206; maßgeblich sind die Zeilen.",
                          "Default laut Handbuch (H), Real Default (I) und My Value (K/L) sind verschiedene Quellen. My Value wird nicht importiert.",
                          "0x00ED enthält den numerischen Namen 1: als unbekannt behandelt. Coils werden getrennt von Holding-Registern geprüft."])
    target = COMPONENT / "frontend/register-catalog.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    catalog = build()
    print(json.dumps(catalog["counts"], ensure_ascii=False))
    for section in range(1, 6):
        missing = [r["hex"] + " " + str(r["name"]) for r in catalog["records"] if r["section"] == section and r["coverage"] == "missing"]
        print(section, "missing:", "; ".join(missing))
