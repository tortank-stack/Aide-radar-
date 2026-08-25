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
 "nom":["nom","titre","intitule","intitulé","nom de l aide","nom aide"],
 "benef":["beneficiaires","bénéficiaires","beneficiaire","bénéficiaire","public","publics","cibles"],
 "objet":["objet","description","objectif","objectifs"],
 "conditions":["conditions","condition","criteres","critères","conditions d attribution","conditions d'attribution"],
 "montant":["montant","montants","financement","modalites de financement","modalités de financement"],
 "operations":["operations eligibles","opérations éligibles","depenses eligibles","dépenses éligibles","operations","opérations"],
 "source":["url","lien","source","url source","site web"],
 "deps":["departements","départements","departement","département","territoire","territoires","zone geographique","zone géographique"],
 "organisme":["organisme","financeur","operateur","opérateur","contact"]
}

def pick(row, name):
    nk={norm_key(k):v for k,v in row.items() if k is not None}
    for a in ALIASES[name]:
        if norm_key(a) in nk and (nk[norm_key(a)] or "").strip():
            return (nk[norm_key(a)] or "").strip()
    # fuzzy fallback
    for k,v in nk.items():
        if any(norm_key(a) in k for a in ALIASES[name]) and (v or "").strip():
            return (v or "").strip()
    return ""

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
    rows=[]
    for r in reader:
        nom=pick(r,"nom")
        if not nom: continue
        rows.append({
            "nom":nom,
            "benef":pick(r,"benef"),
            "objet":pick(r,"objet"),
            "conditions":pick(r,"conditions"),
            "montant":pick(r,"montant"),
            "operations":pick(r,"operations"),
            "source":pick(r,"source"),
            "organisme":pick(r,"organisme"),
            "deps":parse_deps(pick(r,"deps"))
        })

    if len(rows) < MIN_ROWS:
        raise RuntimeError(f"Contrôle qualité bloquant : seulement {len(rows)} aides extraites (< {MIN_ROWS}). Ancienne base conservée.")

    # Basic safety/quality metrics.
    missing_name=sum(not x["nom"] for x in rows)
    missing_source=sum(not x["source"] for x in rows)
    missing_benef=sum(not x["benef"] for x in rows)
    missing_objet=sum(not x["objet"] for x in rows)

    if missing_name:
        raise RuntimeError("Contrôle qualité bloquant : aides sans nom.")

    missing_source_ratio = missing_source / len(rows)
    if missing_source_ratio > MAX_MISSING_SOURCE_RATIO:
        raise RuntimeError(
            f"Contrôle qualité bloquant : {missing_source_ratio:.1%} de sources manquantes "
            f"(max {MAX_MISSING_SOURCE_RATIO:.0%}). Ancienne base conservée."
        )

    if missing_benef / len(rows) > 0.75:
        raise RuntimeError("Contrôle qualité bloquant : trop de bénéficiaires manquants.")

    if missing_objet / len(rows) > 0.75:
        raise RuntimeError("Contrôle qualité bloquant : trop d'objets manquants.")

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
            "missing_beneficiaries":missing_benef,
            "missing_object":missing_objet
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
