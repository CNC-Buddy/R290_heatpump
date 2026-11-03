"""Create synthetic Modbus readings for the offline diagnosis UI test."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
catalog = json.loads((root / "custom_components/r290_heatpump/frontend/register-catalog.json").read_text(encoding="utf-8"))
addresses = sorted(r["address"] for r in catalog["records"] if r["unknown"])
assert len(addresses) == 128 and 0xED in addresses
nonzero = {0xED, *[a for a in addresses if a != 0xED][:10]}
samples = [dict(at="2026-01-01T00:00:00Z", slave=1, address=a, raw=int(a in nonzero), signed=int(a in nonzero)) for a in addresses]
samples.append(dict(at="2026-01-01T00:00:01Z", slave=1, address=0xED, raw=2, signed=2))
output = root / "artifacts/register-live-samples.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(dict(method="synthetic test fixture", samples=samples, errors=[])), encoding="utf-8")
