#!/usr/bin/env python3
import json,sys
from pathlib import Path
html=Path(sys.argv[1] if len(sys.argv)>1 else 'index.html')
db=Path(sys.argv[2] if len(sys.argv)>2 else 'aides.json')
s=html.read_text(encoding='utf-8');d=json.loads(db.read_text(encoding='utf-8'));a=d.get('aides',[]) if isinstance(d,dict) else d
assert html.stat().st_size < 700_000, f'index trop lourd: {html.stat().st_size}'
assert 'AIDERADAR_EMBEDDED_DB' not in s,'base encore embarquée'
assert 'AIDERADAR_DB_URL="./aides.json"' in s,'chargement externe absent'
assert 'V5.1 BÊTA OPTIMISÉE' in s,'version V5.1 absente'
assert 'const V5_VERSION="5.1.0"' in s,'constante V5.1 absente'
assert 'v3SyncNow' in s and 'data.gouv.fr/api/1/datasets' in s
assert 'AideRadar V4.0 — traçabilité + mode pilote' in s and 'AideRadarV4' in s
assert len(a)>=2000,len(a)
ids=[str(x.get('id') or x.get('id_aid') or '') for x in a];assert len(ids)==len(set(ids)),'duplicate ids'
assert any('Initiative 89' in (x.get('nom') or '') for x in a)
assert any('Avance remboursable pour la création et la reprise des TPE' in (x.get('nom') or '') for x in a)
print(json.dumps({'ok':True,'aides':len(a),'version':'5.1.0','index_bytes':html.stat().st_size,'db_bytes':db.stat().st_size},ensure_ascii=False))
