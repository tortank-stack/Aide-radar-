#!/usr/bin/env python3
import json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
html = (ROOT / "index.html").read_text(encoding="utf-8")
m = re.search(r"<script>(.*)</script>", html, re.S)
if not m:
    raise SystemExit("No JS block found")
prefix = m.group(1).split("let LAST_DIAGNOSTIC=null;")[0]
data = json.loads((ROOT / "aides_v15.json").read_text(encoding="utf-8"))
aids = data["aides"] if isinstance(data, dict) else data

profiles = [
  ("plomberie_creation", {
    "activity":"btp","activityDetail":"Plomberie","naf":"","companyStatus":"standard",
    "companyAge":"lt1","dept":"89","postalCode":"89130","commune":"Toucy",
    "communeCode":"89419","epciCode":"200067130","streetAddress":"",
    "latitude":0,"longitude":0,"employees":"1-4","project":"creation",
    "budget":25000,"turnover":0,"ownerAge":29,"franchise":False,"jobSeeker":True
  }),
  ("industrie_energy", {
    "activity":"industrie","activityDetail":"Fabrication de pièces métalliques","naf":"",
    "companyStatus":"standard","companyAge":"gt3","dept":"89","postalCode":"89000",
    "commune":"Auxerre","communeCode":"89024","epciCode":"","streetAddress":"",
    "latitude":0,"longitude":0,"employees":"10-49","project":"energy",
    "budget":100000,"turnover":3000000,"ownerAge":45,"franchise":False,"jobSeeker":False
  }),
  ("restaurant_digital", {
    "activity":"restauration","activityDetail":"Restaurant traditionnel","naf":"",
    "companyStatus":"standard","companyAge":"1to3","dept":"89","postalCode":"89000",
    "commune":"Auxerre","communeCode":"89024","epciCode":"","streetAddress":"",
    "latitude":0,"longitude":0,"employees":"1-4","project":"digital",
    "budget":8000,"turnover":250000,"ownerAge":38,"franchise":False,"jobSeeker":False
  }),
  ("boulangerie_invest", {
    "activity":"commerce","activityDetail":"Boulangerie pâtisserie","naf":"",
    "companyStatus":"standard","companyAge":"gt3","dept":"89","postalCode":"89000",
    "commune":"Auxerre","communeCode":"89024","epciCode":"","streetAddress":"",
    "latitude":0,"longitude":0,"employees":"1-4","project":"invest",
    "budget":30000,"turnover":350000,"ownerAge":40,"franchise":False,"jobSeeker":False
  })
]

runner = prefix + "\nconst TEST_DB=" + json.dumps(aids, ensure_ascii=False) + ";\n"
runner += "const PROFILES=" + json.dumps(profiles, ensure_ascii=False) + ";\n"
runner += r'''
function runProfile(p){
 const territorial=TEST_DB.filter(a=>(a.deps||[]).includes("ALL")||(a.deps||[]).includes(p.dept));
 const scored=territorial.map(a=>({a,r:scoreAid(a,p)})).filter(x=>x.r!==null);
 const eligible=scored.filter(x=>eligibilitySummary(x.a,x.r,p).state!=="no");
 eligible.sort((x,y)=>confidenceScore(y.a,y.r,p)-confidenceScore(x.a,x.r,p)||y.r.score-x.r.score);
 return dedupeRankedRows(eligible,p).slice(0,12).map(x=>({
   name:clean(x.a.nom),
   confidence:confidenceScore(x.a,x.r,p),
   reasons:x.r.reasons
 }));
}
const out={}; for(const [n,p] of PROFILES) out[n]=runProfile(p);
console.log(JSON.stringify(out));
'''

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(runner); jsfile=f.name
res=subprocess.run(["node",jsfile],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(1)
out=json.loads(res.stdout)
top2=[x["name"] for x in out["plomberie_creation"][:2]]
checks=[
 ("Top 2 plomberie cohérent", any("Initiative 89" in n for n in top2) and any("Avance remboursable" in n for n in top2)),
 ("AIF absente plomberie", all("Aide individuelle" not in x["name"] for x in out["plomberie_creation"])),
 ("JUMP absent plomberie", all("JUMP" not in x["name"] for x in out["plomberie_creation"])),
 ("Décarbonation industrie", any("Décarbonation" in x["name"] for x in out["industrie_energy"])),
 ("Cinéma absent restaurant", all("cinéma" not in x["name"].lower() for x in out["restaurant_digital"])),
 ("Presse absente boulangerie", all("presse" not in x["name"].lower() for x in out["boulangerie_invest"]))
]
for label,ok in checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in checks):
    print("\nDiagnostic plomberie top 8:")
    for x in out["plomberie_creation"][:8]: print(" -",x["name"],"| confiance",x["confidence"])
    print("\nDiagnostic industrie énergie top 12:")
    for x in out["industrie_energy"][:12]: print(" -",x["name"],"| confiance",x["confidence"])
    raise SystemExit(2)

# Contract tests: official structured fields must influence the engine before free-text guesses.
synthetic = prefix + r'''
const P={activity:"btp",activityDetail:"Plomberie",naf:"",companyStatus:"standard",companyAge:"lt1",dept:"89",postalCode:"89130",commune:"Toucy",communeCode:"89419",epciCode:"",streetAddress:"",latitude:0,longitude:0,employees:"1-4",project:"creation",budget:25000,turnover:0,ownerAge:29,franchise:false,jobSeeker:false};
const base={id_aid:"synthetic",nom:"Soutien économique",benef:"PME",objet:"Accompagner l'entreprise",conditions:"",montant:"Subvention",operations:"",source:"https://example.test",deps:["89"],status:1,effectif:"-10",profils:["Artisanat - Bâtiment"],projets:["Financer le lancement de son entreprise"],natures:["Subvention"],territoires:["Yonne 89"],_quality:{score:100,issues:[]}};
const r1=scoreAid(base,P);
const r2=scoreAid({...base,id_aid:"expired",fin:"2020-01-01"},P);
const r3=scoreAid({...base,id_aid:"disabled",status:2},P);
const r4=scoreAid({...base,id_aid:"wrong",projets:["Transition énergétique"]},P);
const numericProject={...base,id_aid:"numeric-project",nom:"Aide à la création d'entreprise",objet:"Soutenir la création et la reprise",projets:["12","47"],profils:["3","8"]};
const r5=scoreAid(numericProject,P);
const sig5=structuredProjectSignal(numericProject,P);
console.log(JSON.stringify({r1,r2,r3,r4,r5,sig5}));
'''
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(synthetic); synfile=f.name
res=subprocess.run(["node",synfile],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(1)
s=json.loads(res.stdout)
contract=[
 ("Projet officiel structuré accepté", s["r1"] is not None),
 ("Preuve projet officielle ajoutée", s["r1"] is not None and any("indexation officielle" in x for x in s["r1"].get("reasons",[]))),
 ("Aide expirée exclue", s["r2"] is None),
 ("Aide désactivée exclue", s["r3"] is None),
 ("Projet officiel incompatible exclu", s["r4"] is None),
 ("IDs projet non résolus ignorés", s["r5"] is not None),
 ("IDs projet ne valent pas indexation connue", s["sig5"]["known"] is False)
]
for label,ok in contract: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in contract): raise SystemExit(3)
print(f"All {len(checks)+len(contract)} regression/contract checks passed.")

# Updater parsing contracts: catch schema regressions before committing a rebuilt DB.
import importlib.util
spec=importlib.util.spec_from_file_location("aideradar_updater", ROOT / "update_aides.py")
upd=importlib.util.module_from_spec(spec); spec.loader.exec_module(upd)
updater_checks=[
 ("parse_multi séparateurs", upd.parse_multi("Création; Développement") == ["Création","Développement"]),
 ("normalize_date FR", upd.normalize_date("31/12/2026") == "2026-12-31"),
 ("parse status", upd.parse_int("2") == 2),
 ("parse département", upd.parse_deps("Yonne (89)") == ["89"]),
 ("relation IDs séparés", upd.relation_tokens("12;47") == ([],["12","47"])),
 ("relation labels séparés", upd.relation_tokens("Création; Transition énergétique") == (["Création","Transition énergétique"],[])),
]
for label,ok in updater_checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in updater_checks): raise SystemExit(4)
print(f"Updater contracts: {len(updater_checks)} checks passed.")
