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
   confidence:confidenceScore(x.a,x.r,p)
 }));
}
const out={};
for(const [n,p] of PROFILES) out[n]=runProfile(p);
console.log(JSON.stringify(out));
'''

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(runner)
    jsfile=f.name

res=subprocess.run(["node",jsfile],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr)
    raise SystemExit(1)

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

for label, ok in checks:
    print(("OK" if ok else "FAIL"), "-", label)

if not all(ok for _,ok in checks):
    raise SystemExit(2)

print(f"All {len(checks)} regression checks passed.")
