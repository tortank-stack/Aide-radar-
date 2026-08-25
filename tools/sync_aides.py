#!/usr/bin/env python3
import argparse, csv, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_URL='https://www.data.gouv.fr/api/1/datasets/r/61fb1ddf-b457-4884-afb3-7855f77591de'
DB_RE=re.compile(r'const AIDERADAR_EMBEDDED_DB=(\{.*?\});\n\nasync function loadDB\(\)\{',re.S)
URL_RE=re.compile(r'https?://[^\s"\'<>;,\\]+',re.I)

def norm(s):
    s=(s or '').strip().lower().replace('’',' ').replace("'",' ')
    s=re.sub(r'[^a-z0-9à-ÿ]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def download(url):
    req=urllib.request.Request(url,headers={'User-Agent':'AideRadar-V3/3.0 (+GitHub Pages sync)'})
    with urllib.request.urlopen(req,timeout=90) as r:return r.read()

def decode(blob):
    for enc in ('utf-8-sig','utf-8','cp1252','latin-1'):
        try:return blob.decode(enc)
        except UnicodeDecodeError:pass
    raise RuntimeError('Encodage non reconnu')

def dialect(text):
    try:return csv.Sniffer().sniff(text[:25000],delimiters=';,\t|')
    except csv.Error:return csv.excel

def first_url(s):
    m=URL_RE.search(s or '')
    return m.group(0).rstrip(').]') if m else ''

def keymap(row):return {norm(k):v for k,v in row.items() if k}
def pick(row,*aliases):
    m=keymap(row)
    for a in aliases:
        v=m.get(norm(a),'')
        if str(v or '').strip():return str(v).strip()
    return ''

def isoish(v):
    if not v:return ''
    m=re.search(r'(20\d{2})[-/]([01]\d)[-/]([0-3]\d)',v)
    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else v.strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--html',default='index.html')
    ap.add_argument('--source',default=DEFAULT_URL)
    ap.add_argument('--min-match',type=int,default=1500)
    args=ap.parse_args()
    path=Path(args.html)
    text=path.read_text(encoding='utf-8')
    m=DB_RE.search(text)
    if not m:raise RuntimeError('Base embarquée introuvable')
    payload=json.loads(m.group(1)); aids=payload.get('aides',[])
    if len(aids)<2000:raise RuntimeError(f'Base locale trop petite: {len(aids)}')
    by_id={str(a.get('id') or a.get('id_aid') or ''):a for a in aids if (a.get('id') or a.get('id_aid'))}
    raw=decode(download(args.source)); reader=csv.DictReader(io.StringIO(raw),dialect=dialect(raw))
    matched=changed=disabled=0; newest=''
    now=datetime.now(timezone.utc).isoformat()
    for row in reader:
        aid_id=pick(row,'id_aid','id aide','id')
        if not aid_id or aid_id not in by_id:continue
        matched+=1;a=by_id[aid_id];diff=False
        vals={
            'nom':pick(row,'aid_nom','nom'),
            'objet':pick(row,'aid_objet','objet'),
            'operations':pick(row,'aid_operations_el','operations eligibles','opérations éligibles'),
            'conditions':pick(row,'aid_conditions','conditions'),
            'montant':pick(row,'aid_montant','montant'),
            'benef':pick(row,'aid_benef','beneficiaires','bénéficiaires'),
        }
        for k,v in vals.items():
            if v and str(a.get(k,'')).strip()!=v:a[k]=v;diff=True
        src=first_url(pick(row,'complements_sources','aid_url','url_aide','url','source'))
        if src and a.get('source','')!=src:a['source']=src;diff=True
        fin=isoish(pick(row,'date_fin','date fin'))
        if fin and a.get('fin','')!=fin:a['fin']=fin;diff=True
        status=pick(row,'status','statut'); hidden=bool(status and status!='1')
        if a.get('_live_hidden',False)!=hidden:a['_live_hidden']=hidden;diff=True
        if hidden:disabled+=1
        modified=pick(row,'horodatage','date modification')
        validation=pick(row,'aid_validation','date validation')
        a['_live']={'modified':modified,'validation':validation,'status':status,'syncedAt':now}
        if modified and modified>newest:newest=modified
        if diff:changed+=1
    if matched<args.min_match:raise RuntimeError(f'Correspondance insuffisante: {matched}/{len(aids)}')
    ids=[str(a.get('id') or a.get('id_aid') or '') for a in aids]
    if len(ids)!=len(set(ids)):raise RuntimeError('IDs dupliqués après mise à jour')
    payload['updated']=datetime.now(timezone.utc).date().isoformat()
    payload['generated_at']=now
    payload['source']='Aides entreprises - DGE / ISM via data.gouv.fr'
    payload['source_url']=args.source
    payload['live_sync']={'matched':matched,'changed':changed,'disabled':disabled,'source_max_modified':newest,'synced_at':now}
    replacement='const AIDERADAR_EMBEDDED_DB='+json.dumps(payload,ensure_ascii=False,separators=(',',':'))+';\n\nasync function loadDB(){'
    new=DB_RE.sub(lambda _:replacement,text,count=1)
    tmp=path.with_suffix('.tmp');tmp.write_text(new,encoding='utf-8');tmp.replace(path)
    print(json.dumps({'ok':True,'matched':matched,'changed':changed,'disabled':disabled,'source_max_modified':newest},ensure_ascii=False))

if __name__=='__main__':main()
