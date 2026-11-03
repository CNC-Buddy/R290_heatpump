"""Build a local install archive, excluding caches, tests and environment files."""
from hashlib import sha256
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "r290_heatpump"
manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
version = manifest["version"]
destination = ROOT / "artifacts" / f"r290_heatpump-{version}.zip"
destination.parent.mkdir(exist_ok=True)
files = sorted(p for p in COMPONENT.rglob("*") if p.is_file()
               and "__pycache__" not in p.parts
               and p.suffix in {".py", ".json", ".yaml", ".js", ".css", ".png", ".svg"})
files.extend([ROOT / "README.md", ROOT / "docs" / "auxiliary-pump.md",
              ROOT / "docs" / "nextgen.md", ROOT / "docs" / "validation.md",
              ROOT / "brands" / "r290_heatpump" / "README.md", ROOT / "license.txt"])
with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for source in files:
        archive.write(source, source.relative_to(ROOT).as_posix())
with zipfile.ZipFile(destination) as archive:
    assert archive.testzip() is None
    expected = {
        "custom_components/r290_heatpump/electric_overview.py",
        "custom_components/r290_heatpump/frontend/electric-overview.js",
        "custom_components/r290_heatpump/frontend/electric-art.js",
        "custom_components/r290_heatpump/frontend/electric-overview.css",
        "license.txt",
        "brands/r290_heatpump/README.md",
        "custom_components/r290_heatpump/frontend/branding.js",
        "custom_components/r290_heatpump/brand/icon.png",
        "custom_components/r290_heatpump/brand/icon@2x.png",
        "custom_components/r290_heatpump/brand/dark_icon.png",
        "custom_components/r290_heatpump/brand/dark_icon@2x.png",
        "custom_components/r290_heatpump/brand/logo.png",
        "custom_components/r290_heatpump/brand/logo@2x.png",
        "custom_components/r290_heatpump/brand/dark_logo.png",
        "custom_components/r290_heatpump/brand/dark_logo@2x.png",
        "custom_components/r290_heatpump/parameter_access.py",
        "custom_components/r290_heatpump/frontend/operating-data.js",
        "custom_components/r290_heatpump/schematic.py",
        "custom_components/r290_heatpump/frontend/schematic-catalog.json",
        "custom_components/r290_heatpump/frontend/schematic-editor.js",
        "custom_components/r290_heatpump/frontend/schematic-model.js",
        "custom_components/r290_heatpump/frontend/schematic-bindings.js",
        "custom_components/r290_heatpump/frontend/schematic-presets.js",
        "custom_components/r290_heatpump/frontend/schematic-svg.js",
        "custom_components/r290_heatpump/frontend/schematic-art.js",
        "custom_components/r290_heatpump/frontend/schematic-routing.js",
        "custom_components/r290_heatpump/frontend/schematic-tanks.js",
        "custom_components/r290_heatpump/frontend/chart-ui.js",
        "custom_components/r290_heatpump/heat_sources.py",
        "custom_components/r290_heatpump/frontend/heat-sources.js",
        "custom_components/r290_heatpump/plant.py",
        "custom_components/r290_heatpump/service_tools.py",
        "custom_components/r290_heatpump/frontend/plant.js",
        "custom_components/r290_heatpump/frontend/plant-schematic.js",
        "custom_components/r290_heatpump/frontend/service.js",
        "custom_components/r290_heatpump/polling/scheduler.py",
        "custom_components/r290_heatpump/polling/batch.py",
        "custom_components/r290_heatpump/polling/consumers.py",
        "custom_components/r290_heatpump/polling/entities.py",
        "custom_components/r290_heatpump/frontend/bus-health.js",
        "docs/nextgen.md",
        "docs/validation.md",
        "custom_components/r290_heatpump/pump_controller.py",
        "custom_components/r290_heatpump/pump_logic.py",
        "custom_components/r290_heatpump/pump_config.py",
        "custom_components/r290_heatpump/pump_suggestions.py",
        "custom_components/r290_heatpump/pump_sources.py",
        "custom_components/r290_heatpump/pump_entities.py",
        "custom_components/r290_heatpump/panel.py",
        "custom_components/r290_heatpump/panel_diagnostics.py",
        "custom_components/r290_heatpump/frontend/data-browser.js",
        "custom_components/r290_heatpump/frontend/dom.js",
        "custom_components/r290_heatpump/analytics.py",
        "custom_components/r290_heatpump/frontend/r290-panel.js",
        "custom_components/r290_heatpump/frontend/model.js",
        "custom_components/r290_heatpump/frontend/panel.css",
        "custom_components/r290_heatpump/frontend/theme.css",
        "custom_components/r290_heatpump/frontend/overview.js",
        "custom_components/r290_heatpump/frontend/overview.css",
        "custom_components/r290_heatpump/frontend/visuals.js",
        "custom_components/r290_heatpump/frontend/entity-picker.js",
        "custom_components/r290_heatpump/frontend/parameters.js",
        "custom_components/r290_heatpump/frontend/parameters.css",
        "custom_components/r290_heatpump/frontend/i18n.js",
        "custom_components/r290_heatpump/frontend/register-catalog.json",
        "custom_components/r290_heatpump/curve_workshop.py",
        "custom_components/r290_heatpump/curve_math.py",
        "custom_components/r290_heatpump/frontend/curve-model.js",
        "docs/auxiliary-pump.md",
    }
    assert expected <= set(archive.namelist())
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in archive.namelist())
digest = sha256(destination.read_bytes()).hexdigest()
destination.with_suffix(".zip.sha256").write_text(f"{digest}  {destination.name}\n", encoding="ascii")
print(json.dumps({"path": str(destination), "version": version, "files": len(files),
                  "bytes": destination.stat().st_size, "sha256": digest}, indent=2))
