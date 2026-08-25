#!/usr/bin/env python3
import csv, io, json, os, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Official "Aides entreprises" main CSV resource on data.gouv.fr.
SOURCE_URL = os.environ.get(
    "AIDERADAR_SOURCE_URL",
    "https://www.data.gouv.fr/api/1/datasets/r/61fb1ddf-b457-4884-afb3-7855f77591de"
)
OUT = Path(os.environ.get("AIDERADAR_OUTPUT", "aides_v15.json"))
MIN_ROWS = int(os.environ.get("AIDERADAR_MIN_ROWS", "1500"))
MAX_MISSING_SOURCE_RATIO = float(os.environ.get("AIDERADAR_MAX_MISSING_SOURCE_RATIO", "0.45"))

def norm_key(s):
    s=(s or "").strip().lower()
    s=re.sub(r"[’']", " ", s)
    s=re.sub(r"[^a-z0-9à-ÿ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

ALIASES = {
 "id":["id_aid","id aide","id","identifiant aide"],
 "nom":["aid_nom","nom","titre","intitule","intitulé","nom de l aide","nom aide"],
 "benef":["aid_benef","beneficiaires","bénéficiaires","beneficiaire","bénéficiaire","public","publics","cibles"],
 "objet":["aid_objet","objet","description","objectif","objectifs"],
 "conditions":["aid_conditions","conditions","condition","criteres","critères","conditions d attribution","conditions d'attribution"],
 "montant":["aid_montant","montant","montants","financement","modalites de financement","modalités de financement"],
 "operations":["aid_operations_el","operations eligibles","opérations éligibles","depenses eligibles","dépenses éligibles","operations","opérations"],
 "source":["complements_sources","aid_url","url_aide","url aide","url","lien","source","url source","site web","website"],
 "deps":["departements","départements","departement","département","territoire","territoires","zone geographique","zone géographique"],
 "couverture_geo":["couverture_geo","couverture geo","id couverture geo"],
 "organisme":["organisme","financeur","operateur","opérateur","contact","aid_financeur","nom_financeur"],
 "validation":["aid_validation"],
 "domaine":["id_domaine"],
 "handicapes":["handicapes"],
 "femmes":["femmes"],
 "seniors":["seniors"],
 "jeunes":["jeunes"],
 "date_fin":["date_fin"],
 "status":["status"],
 "effectif":["effectif"],
 "duree_projet":["duree_projet"],
 "age_entreprise":["age_entreprise"],
 "projets":["projets"],
 "profils":["profils"],
 "natures":["natures"],
 "territoires":["territoires"],
 "contacts":["contacts"],
 "financeurs":["financeurs"]
}

def pick(row, name):
    nk={norm_key(k):v for k,v in row.items() if k is not None}

    # Exact documented/known aliases first.
    for a in ALIASES[name]:
        key=norm_key(a)
        if key in nk and (nk[key] or "").strip():
            return (nk[key] or "").strip()

    # Conservative fuzzy fallback.
    for k,v in nk.items():
        if not (v or "").strip():
            continue
        for a in ALIASES[name]:
            ak=norm_key(a)
            if ak and (k==ak or k.startswith(ak+" ") or k.endswith(" "+ak)):
                return (v or "").strip()

    return ""


URL_RE = re.compile(r'https?://[^\s"\'<>;,\\]+', re.I)

def extract_source(raw):
    """Return the first usable URL from complements_sources or a URL-like field."""
    s=(raw or "").strip()
    if not s:
        return ""
    # JSON/list-like content is common in exported complement fields.
    try:
        obj=json.loads(s)
        if isinstance(obj, str):
            s=obj
        elif isinstance(obj, list):
            s=" ".join(str(x) for x in obj)
        elif isinstance(obj, dict):
            s=" ".join(str(v) for v in obj.values())
    except Exception:
        pass
    m=URL_RE.search(s)
    return m.group(0).rstrip(").]") if m else ""

def load_previous(path):
    """Use the last known-good production DB as an enrichment fallback."""
    if not path.exists():
        return {}, {}
    try:
        old=json.loads(path.read_text(encoding="utf-8"))
        aids=old.get("aides",[]) if isinstance(old,dict) else old
        by_id={}
        by_name={}
        for a in aids:
            aid_id=str(a.get("id_aid") or "").strip()
            if aid_id:
                by_id[aid_id]=a
            name=norm_key(a.get("nom") or "")
            if name:
                by_name[name]=a
        print(f"Base précédente chargée pour enrichissement : {len(aids)} aides")
        return by_id,by_name
    except Exception as e:
        print("AVERTISSEMENT : ancienne base non exploitable :",e)
        return {}, {}

def previous_match(row, by_id, by_name):
    aid_id=pick(row,"id")
    if aid_id and aid_id in by_id:
        return by_id[aid_id]
    return by_name.get(norm_key(pick(row,"nom")), {})


def parse_multi(raw):
    s=(raw or "").strip()
    if not s:
        return []
    try:
        obj=json.loads(s)
        if isinstance(obj,list):
            return [str(x).strip() for x in obj if str(x).strip()]
        if isinstance(obj,dict):
            return [str(v).strip() for v in obj.values() if str(v).strip()]
        if isinstance(obj,str):
            s=obj
    except Exception:
        pass
    parts=re.split(r"\s*(?:\||;|\n|\r)+\s*",s)
    if len(parts)==1 and s.count(",")>=1 and len(s)<1500:
        comma=[x.strip() for x in s.split(",") if x.strip()]
        if 1 < len(comma) <= 40:
            parts=comma
    out=[]; seen=set()
    for x in parts:
        x=x.strip(" []\"'")
        if not x: continue
        k=norm_key(x)
        if k not in seen:
            seen.add(k); out.append(x)
    return out

def parse_bool(raw):
    s=norm_key(raw)
    return s in {"1","true","vrai","oui","yes","x"}

def parse_int(raw):
    try: return int(float(str(raw).strip()))
    except Exception: return None

def normalize_date(raw):
    s=(raw or "").strip()
    if not s: return ""
    for rx,order in [
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),
        (r"^(\d{1,2})/(\d{1,2})/(\d{4})", "dmy"),
        (r"^(\d{1,2})-(\d{1,2})-(\d{4})", "dmy")
    ]:
        m=re.search(rx,s)
        if m:
            if order=="ymd": y,mo,d=map(int,m.groups())
            else: d,mo,y=map(int,m.groups())
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return s[:10] if len(s)>=10 else s

def row_quality(row):
    issues=[]; score=100
    if not row.get("source"): issues.append("source_missing"); score-=7
    if not row.get("benef"): issues.append("beneficiaries_missing"); score-=8
    if not row.get("objet"): issues.append("object_missing"); score-=8
    if not row.get("deps") and row.get("couverture_geo"):
        issues.append("territorial_scope_unresolved"); score-=12
    elif row.get("deps")==["ALL"] and row.get("couverture_geo") and row.get("territoires"):
        issues.append("territorial_scope_unclear"); score-=6
    return {"issues":issues,"score":max(0,score)}

def relation_tokens(raw):
    vals=parse_multi(raw)
    ids=[]; labels=[]
    for v in vals:
        s=str(v).strip()
        if not s: continue
        if re.fullmatch(r"\d+(?:\.0+)?", s): ids.append(str(int(float(s))))
        elif re.fullmatch(r"(?:\d+\s*[,;|]\s*)+\d+", s): ids.extend(re.findall(r"\d+", s))
        elif re.search(r"[A-Za-zÀ-ÿ]", s): labels.append(s)
        else: ids.append(s)
    return labels, list(dict.fromkeys(ids))

def safe_previous_list(prev,key):
    vals=prev.get(key) or []
    if not isinstance(vals,list): return []
    return [str(x).strip() for x in vals if str(x).strip() and re.search(r"[A-Za-zÀ-ÿ]",str(x))]


def parse_deps(raw):
    t=(raw or "").strip()
    if not t: return ["ALL"]
    low=norm_key(t)
    if any(x in low for x in ["national","france entiere","france entière","toute la france"]):
        return ["ALL"]
    # Capture French department codes (01..95, 2A/2B, 971..976)
    vals=re.findall(r"(?<!\d)(?:0[1-9]|[1-8]\d|9[0-5]|2A|2B|97[1-6])(?!\d)", t, flags=re.I)
    vals=[v.upper() for v in vals]
    return list(dict.fromkeys(vals)) or ["ALL"]

def download(url):
    req=urllib.request.Request(url,headers={"User-Agent":"AideRadar/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read()

def decode_csv(blob):
    for enc in ("utf-8-sig","utf-8","cp1252","latin-1"):
        try: return blob.decode(enc)
        except UnicodeDecodeError: pass
    raise RuntimeError("Encodage CSV non reconnu")

def sniff(text):
    sample=text[:20000]
    try: return csv.Sniffer().sniff(sample,delimiters=";,|\t,")
    except csv.Error: return csv.excel

def main():
    blob=download(SOURCE_URL)
    text=decode_csv(blob)
    reader=csv.DictReader(io.StringIO(text),dialect=sniff(text))

    headers=[h for h in (reader.fieldnames or []) if h]
    print("Colonnes détectées :", " | ".join(headers))

    normalized_headers={norm_key(h) for h in headers}
    expected_core=["aid_nom","aid_objet","aid_conditions","aid_montant","aid_benef"]
    found_core=[x for x in expected_core if norm_key(x) in normalized_headers]

    # The official documentation describes these aid_* columns.
    # If almost none are present, stop rather than silently corrupting the database.
    if len(found_core) < 3:
        raise RuntimeError(
            "Mapping officiel non reconnu. Colonnes aid_* attendues non trouvées : "
            + ", ".join(expected_core)
        )

    previous_by_id,previous_by_name=load_previous(OUT)

    rows=[]
    for r in reader:
        nom=pick(r,"nom")
        if not nom: continue
        couverture=pick(r,"couverture_geo")
        prev=previous_match(r,previous_by_id,previous_by_name)

        source=extract_source(pick(r,"source"))
        if not source:
            source=(prev.get("source") or "").strip()

        organisme=pick(r,"organisme") or (prev.get("organisme") or "")

        territoire_labels,territoire_ids=relation_tokens(pick(r,"territoires"))
        projet_labels,projet_ids=relation_tokens(pick(r,"projets"))
        profil_labels,profil_ids=relation_tokens(pick(r,"profils"))
        nature_labels,nature_ids=relation_tokens(pick(r,"natures"))
        contact_labels,contact_ids=relation_tokens(pick(r,"contacts"))
        financeur_labels,financeur_ids=relation_tokens(pick(r,"financeurs"))

        if territoire_labels:
            parsed_deps=parse_deps(" ".join(territoire_labels))
        elif prev.get("deps"):
            parsed_deps=prev.get("deps")
        else:
            parsed_deps=[]

        status=parse_int(pick(r,"status"))
        if status in {0,2}:
            continue

        row={
            "id_aid":pick(r,"id"),
            "nom":nom,
            "benef":pick(r,"benef"),
            "objet":pick(r,"objet"),
            "conditions":pick(r,"conditions"),
            "montant":pick(r,"montant"),
            "operations":pick(r,"operations"),
            "source":source,
            "organisme":organisme,
            "couverture_geo":couverture,
            "deps":parsed_deps,
            "geo":"aide nationale" if parsed_deps==["ALL"] else "aide territoriale",
            "local":parsed_deps!=["ALL"],
            "validation":normalize_date(pick(r,"validation")),
            "id_domaine":pick(r,"domaine"),
            "handicapes":parse_bool(pick(r,"handicapes")),
            "femmes":parse_bool(pick(r,"femmes")),
            "seniors":parse_bool(pick(r,"seniors")),
            "jeunes":parse_bool(pick(r,"jeunes")),
            "fin":normalize_date(pick(r,"date_fin")),
            "status":status if status is not None else 1,
            "effectif":pick(r,"effectif") or (prev.get("effectif") or ""),
            "duree_projet":pick(r,"duree_projet"),
            "age_entreprise":pick(r,"age_entreprise"),
            "projets":projet_labels or safe_previous_list(prev,"projets"),
            "projet_ids":projet_ids,
            "profils":profil_labels or safe_previous_list(prev,"profils"),
            "profil_ids":profil_ids,
            "natures":nature_labels or safe_previous_list(prev,"natures"),
            "nature_ids":nature_ids,
            "territoires":territoire_labels or safe_previous_list(prev,"territoires"),
            "territoire_ids":territoire_ids,
            "contacts":contact_labels,
            "contact_ids":contact_ids,
            "financeurs":financeur_labels,
            "financeur_ids":financeur_ids
        }
        row["_quality"]=row_quality(row)
        rows.append(row)

    if len(rows) < MIN_ROWS:
        raise RuntimeError(f"Contrôle qualité bloquant : seulement {len(rows)} aides extraites (< {MIN_ROWS}). Ancienne base conservée.")

    # Basic safety/quality metrics.
    missing_name=sum(not x["nom"] for x in rows)
    missing_source=sum(not x["source"] for x in rows)
    missing_benef=sum(not x["benef"] for x in rows)
    missing_objet=sum(not x["objet"] for x in rows)
    missing_projets=sum(not x.get("projets") for x in rows)
    missing_profils=sum(not x.get("profils") for x in rows)

    print(
        "Qualité mapping :",
        f"noms={len(rows)-missing_name}/{len(rows)}",
        f"beneficiaires={len(rows)-missing_benef}/{len(rows)}",
        f"objets={len(rows)-missing_objet}/{len(rows)}",
        f"sources={len(rows)-missing_source}/{len(rows)}"
    )

    if missing_name:
        raise RuntimeError("Contrôle qualité bloquant : aides sans nom.")

    missing_source_ratio = missing_source / len(rows)

    # The official stock CSV does not document a dedicated URL field.
    # We first extract complements_sources, then carry forward last known-good
    # links. Block only on a material regression versus production.
    previous_sources=0
    previous_total=len(previous_by_id) if previous_by_id else len(previous_by_name)
    previous_seen=set()
    for a in list(previous_by_id.values()) + list(previous_by_name.values()):
        key=str(a.get("id_aid") or norm_key(a.get("nom") or ""))
        if key in previous_seen:
            continue
        previous_seen.add(key)
        if (a.get("source") or "").strip():
            previous_sources+=1
    previous_total=len(previous_seen)
    previous_missing_ratio=(1-(previous_sources/previous_total)) if previous_total else None

    if previous_missing_ratio is not None:
        degradation=missing_source_ratio-previous_missing_ratio
        print(
            f"Sources : nouvelles manquantes={missing_source_ratio:.1%}, "
            f"ancienne base={previous_missing_ratio:.1%}, delta={degradation:+.1%}"
        )
        if degradation > 0.08:
            raise RuntimeError(
                f"Contrôle qualité bloquant : perte de couverture des sources de {degradation:.1%}. "
                "Ancienne base conservée."
            )
    elif missing_source_ratio > 0.95:
        raise RuntimeError(
            "Contrôle qualité bloquant : aucune source exploitable et aucune ancienne base "
            "pour enrichissement."
        )

    # Les champs bénéficiaires / objet peuvent être absents dans la source officielle.
    # On ne bloque que si la récupération semble manifestement cassée.
    missing_benef_ratio = missing_benef / len(rows)
    missing_objet_ratio = missing_objet / len(rows)

    if missing_benef_ratio > 0.97:
        raise RuntimeError(
            f"Contrôle qualité bloquant : {missing_benef_ratio:.1%} de bénéficiaires manquants. "
            "Cela ressemble à un problème de mapping de colonnes."
        )

    if missing_objet_ratio > 0.97:
        raise RuntimeError(
            f"Contrôle qualité bloquant : {missing_objet_ratio:.1%} d'objets manquants. "
            "Cela ressemble à un problème de mapping de colonnes."
        )

    today=datetime.now(timezone.utc).date().isoformat()
    payload={
        "updated":today,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source":"data.gouv.fr / Aides entreprises",
        "source_url":SOURCE_URL,
        "count":len(rows),
        "quality":{
            "missing_source":missing_source,
            "missing_source_ratio":round(missing_source_ratio,4),
            "source_strategy":"complements_sources_then_previous_db",
            "missing_beneficiaries":missing_benef,
            "missing_beneficiaries_ratio":round(missing_benef_ratio,4),
            "missing_object":missing_objet,
            "missing_object_ratio":round(missing_objet_ratio,4),
            "missing_projects":missing_projets,
            "missing_profiles":missing_profils,
            "status_policy":"only_online_status_1",
            "structured_relation_policy":"numeric_ids_never_used_as_labels"
        },
        "aides":rows
    }

    tmp=OUT.with_suffix(OUT.suffix+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    # Validate what we just wrote before replacing production data.
    chk=json.loads(tmp.read_text(encoding="utf-8"))
    if len(chk.get("aides",[])) < MIN_ROWS:
        raise RuntimeError("Validation finale échouée.")
    tmp.replace(OUT)
    print(f"OK: {len(rows)} aides écrites dans {OUT}; sources manquantes={missing_source}")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("ERREUR:",e,file=sys.stderr)
        sys.exit(1)
