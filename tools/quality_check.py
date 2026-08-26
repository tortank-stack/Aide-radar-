#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
p=Path(sys.argv[1] if len(sys.argv)>1 else 'index.html')
s=p.read_text(encoding='utf-8')
m=re.search(r'const AIDERADAR_EMBEDDED_DB=(\{.*?\});\n\nasync function loadDB\(\)\{',s,re.S)
assert m,'base embedded missing';d=json.loads(m.group(1));a=d.get('aides',[])
assert len(a)>=2000,len(a)
ids=[str(x.get('id') or x.get('id_aid') or '') for x in a];assert len(ids)==len(set(ids)),'duplicate ids'
assert 'V4.0 PILOTE' in s
assert 'v3SyncNow' in s and 'data.gouv.fr/api/1/datasets' in s
assert 'AideRadar V4.0 — traçabilité + mode pilote' in s and 'AideRadarV4' in s
# Regression sentinels from the reference scenario
n={x.get('nom'):x for x in a}
assert any('Initiative 89' in (x.get('nom') or '') for x in a)
assert any('Avance remboursable pour la création et la reprise des TPE' in (x.get('nom') or '') for x in a)
print(json.dumps({'ok':True,'aides':len(a),'version':'4.0.0'},ensure_ascii=False))
