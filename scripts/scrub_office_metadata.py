import os
import sys
import shutil
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


CORE_PROPS_PATH = "docProps/core.xml"


def scrub_core_xml(data: bytes) -> bytes:
    try:
        # Parse XML
        root = ET.fromstring(data)
    except ET.ParseError:
        return data  # If unparsable, leave untouched

    # Namespaces used in Office Open XML core properties
    ns = {
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    # Remove personal name fields
    changed = False
    creator = root.find("dc:creator", ns)
    if creator is not None and (creator.text or "") != "":
        creator.text = ""
        changed = True

    last_mod_by = root.find("cp:lastModifiedBy", ns)
    if last_mod_by is not None and (last_mod_by.text or "") != "":
        last_mod_by.text = ""
        changed = True

    if not changed:
        return data

    # Serialize back to bytes
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def scrub_xlsx(path: Path) -> bool:
    """Scrub author metadata in an .xlsx file in-place.

    Returns True if file was modified, False otherwise.
    """
    modified = False

    with zipfile.ZipFile(path, "r") as zin:
        names = set(zin.namelist())
        if CORE_PROPS_PATH not in names:
            return False

        core_data = zin.read(CORE_PROPS_PATH)
        new_core = scrub_core_xml(core_data)
        if new_core == core_data:
            return False

        # Rebuild archive with updated core.xml
        with tempfile.TemporaryDirectory() as td:
            tmp_zip = Path(td) / path.name
            with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == CORE_PROPS_PATH:
                        zout.writestr(CORE_PROPS_PATH, new_core)
                    else:
                        zout.writestr(item, zin.read(item.filename))
            # Replace original atomically
            shutil.copy2(tmp_zip, path)
            modified = True

    return modified


def ensure_backup(file_paths, backup_root: Path):
    backup_root.mkdir(parents=True, exist_ok=True)
    for f in file_paths:
        rel = f.name
        dest = backup_root / rel
        if not dest.exists():
            shutil.copy2(f, dest)


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("documentation")
    if not base.exists():
        print(f"Path not found: {base}")
        sys.exit(1)

    # Target only .xlsx files for now
    xlsx_files = [p for p in base.glob("*.xlsx")]
    if not xlsx_files:
        print("No .xlsx files found to scrub.")
        return

    backup_dir = base / ".backup_before_metadata_scrub"
    ensure_backup(xlsx_files, backup_dir)

    changed = 0
    for f in xlsx_files:
        try:
            if scrub_xlsx(f):
                changed += 1
                print(f"Scrubbed: {f}")
            else:
                print(f"No changes needed: {f}")
        except Exception as e:
            print(f"Failed to scrub {f}: {e}")

    print(f"Done. Modified {changed} of {len(xlsx_files)} files.")


if __name__ == "__main__":
    main()
