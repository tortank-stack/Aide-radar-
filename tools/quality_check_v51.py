#!/usr/bin/env python3
import json,sys
from pathlib import Path

html_path=Path(sys.argv[1] if len(sys.argv)>1 else 'index.html')
db_path=Path(sys.argv[2] if len(sys.argv)>2 else 'aides.json')
html=html_path.read_text(encoding='utf-8')
payload=json.loads(db_path.read_text(encoding='utf-8'))
aids=payload if isinstance(payload,list) else payload.get('aides',[])

assert len(aids)>=2000, f'base too small: {len(aids)}'
ids=[str(x.get('id') or x.get('id_aid') or '') for x in aids]
assert all(ids),'empty aid id'
assert len(ids)==len(set(ids)),'duplicate ids'
assert 'V5.1 BÊTA OPTIMISÉE' in html,'V5.1 badge missing'
assert 'const AIDERADAR_DB_URL="./aides.json"' in html,'external aides.json loader missing'
assert 'AIDERADAR_EMBEDDED_DB' not in html,'embedded database still present'
assert 'window.AideRadarV5' in html and 'version:V5_VERSION' in html,'V5 layer missing'
assert any('Initiative 89' in (x.get('nom') or '') for x in aids),'Initiative 89 missing'
assert any('Avance remboursable pour la création et la reprise des TPE' in (x.get('nom') or '') for x in aids),'TPE BFC missing'
if isinstance(payload,dict) and payload.get('count') is not None:
    assert int(payload['count'])==len(aids),f"count mismatch: {payload['count']} != {len(aids)}"
print(json.dumps({'ok':True,'aides':len(aids),'version':'5.1.0','db':'external'},ensure_ascii=False))
