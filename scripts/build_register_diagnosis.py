"""Create a self-contained HTML report from workbook audit and read-only samples."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    catalog = json.loads((ROOT / 'custom_components/r290_heatpump/frontend/register-catalog.json').read_text(encoding='utf-8'))
    live_path = ROOT / 'artifacts/register-live-samples.json'
    live = json.loads(live_path.read_text(encoding='utf-8')) if live_path.exists() else dict(samples=[], errors=[], method='Noch nicht abgefragt')
    # Compact diagnostics: register metadata + all received samples; no credentials.
    payload = dict(sources=catalog['sources'], counts=catalog['counts'], notes=catalog['notes'],
                   records=[{k: r.get(k) for k in ('section','address','hex','name','code','row','file','kind','coverage','unknown','issues')} for r in catalog['records']], live=live)
    template = (ROOT / 'scripts/register-diagnosis-template.html').read_text(encoding='utf-8')
    notice = '<aside style="padding:18px;background:#fff3d8;border:1px solid #d8a251;margin:16px;border-radius:10px"><strong>Offline-Momentaufnahme / Offline snapshot</strong><br>Diese Datei aktualisiert sich nicht. This file does not update.<br>Live-Diagnose: Home Assistant → R290 NextGen → Diagnose / Diagnostics</aside>'
    template = template.replace('</style>', '</style><body>'+notice, 1)
    target = ROOT / 'artifacts/r290-register-diagnose.html'
    target.write_text(template.replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')),encoding='utf-8')
    print(str(target))


if __name__ == '__main__':
    main()
