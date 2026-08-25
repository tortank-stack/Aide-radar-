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


# Decision/action layer contracts.
decision_js = prefix + r"""
const P={activity:"btp",activityDetail:"Plomberie",naf:"",companyStatus:"standard",companyAge:"lt1",dept:"89",postalCode:"89130",commune:"Toucy",communeCode:"89419",epciCode:"",streetAddress:"",latitude:0,longitude:0,employees:"1-4",project:"creation",budget:25000,turnover:0,ownerAge:29,franchise:false,jobSeeker:false};
const cleanAid={id_aid:"d1",nom:"Prime création",benef:"TPE",objet:"Créer une entreprise",conditions:"Fournir un devis, un RIB et un Kbis.",montant:"Prime forfaitaire de 1 000 €",operations:"",source:"https://example.test",deps:["89"],status:1,_quality:{score:100,issues:[]}};
const pendingAid={...cleanAid,id_aid:"d2",conditions:"Être à jour URSSAF. Fournir un DUERP et un devis.",montant:"Subvention représentant 50 % des dépenses éligibles."};
const r1=scoreAid(cleanAid,P);
const r2=scoreAid(pendingAid,P);
const d1=decisionModel(cleanAid,r1,P,0);
const d2=decisionModel(pendingAid,r2,P,1);
const docs=inferDocuments({...pendingAid,conditions:"Fournir Kbis, RIB, devis, attestation URSSAF et DUERP."},P);
const road=buildRoadmap([{a:cleanAid,r:r1},{a:pendingAid,r:r2}],P);
const txt=buildRoadmapText([{a:cleanAid,r:r1},{a:pendingAid,r:r2}],P);
console.log(JSON.stringify({d1,d2,docs,road:{grantTotal:road.grantTotal,top:road.top.length},txt}));
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(decision_js); decision_file=f.name
res=subprocess.run(["node",decision_file],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(5)
d=json.loads(res.stdout)
decision_checks=[
 ("Décision priorité calculée", d["d1"]["priority"] in ("now","check","later")),
 ("Montant fixe décision = 1000", d["d1"]["exactGrant"] == 1000),
 ("Documents Kbis détectés", any("Kbis" in x for x in d["docs"])),
 ("Documents RIB détectés", "RIB" in d["docs"]),
 ("Documents devis détectés", any("Devis" in x for x in d["docs"])),
 ("Documents URSSAF détectés", any("URSSAF" in x for x in d["docs"])),
 ("Documents DUERP détectés", any("DUERP" in x for x in d["docs"])),
 ("Roadmap top construite", d["road"]["top"] == 2),
 ("Roadmap additionne uniquement subventions chiffrables", d["road"]["grantTotal"] >= 1000),
 ("Plan texte généré", "AideRadar — Plan d’action" in d["txt"] and "Prime création" in d["txt"])
]
for label,ok in decision_checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in decision_checks): raise SystemExit(6)
print(f"Decision layer contracts: {len(decision_checks)} checks passed.")


# Dossier assistant contracts.
dossier_js = prefix + r"""
const P={activity:"btp",activityDetail:"Plomberie",naf:"",companyStatus:"standard",companyAge:"lt1",dept:"89",postalCode:"89130",commune:"Toucy",communeCode:"89419",epciCode:"",streetAddress:"",latitude:0,longitude:0,employees:"1-4",project:"creation",budget:25000,turnover:0,ownerAge:29,franchise:false,jobSeeker:false};
const A={id_aid:"doc1",nom:"Aide test création",benef:"TPE",objet:"Soutenir la création",conditions:"Demande avant tout engagement. Fournir Kbis, RIB, devis, attestation URSSAF, DUERP. Vérifier les règles de cumul et les aides de minimis.",montant:"Prime forfaitaire de 1 000 €",operations:"Matériel",source:"https://example.test",deps:["89"],status:1,fin:"2026-12-31",_quality:{score:100,issues:[]}};
const R=scoreAid(A,P);
const list=buildDossierChecklist(A,R,P);
const msg=buildContactMessage(A,R,P,0);
const checklistText=buildChecklistText(A,R,P);
console.log(JSON.stringify({list,msg,checklistText}));
"""
with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
    f.write(dossier_js); dossier_file=f.name
res=subprocess.run(["node",dossier_file],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(7)
x=json.loads(res.stdout)
labels=[i["label"] for i in x["list"]]
dossier_checks=[
 ("Checklist contient fiche officielle", any("fiche officielle" in s.lower() for s in labels)),
 ("Checklist Kbis", any("Kbis" in s for s in labels)),
 ("Checklist RIB", any(s=="RIB" for s in labels)),
 ("Checklist devis", any("Devis" in s for s in labels)),
 ("Checklist URSSAF", any("URSSAF" in s for s in labels)),
 ("Checklist DUERP", any("DUERP" in s for s in labels)),
 ("Checklist avant engagement", any("avant de commander" in s.lower() for s in labels)),
 ("Checklist de minimis", any("minimis" in s.lower() for s in labels)),
 ("Checklist cumul", any("cumul" in s.lower() for s in labels)),
 ("Checklist échéance", any("date limite" in s.lower() for s in labels)),
 ("Message contient nom aide", "Aide test création" in x["msg"]),
 ("Message contient budget", "25" in x["msg"] and "€" in x["msg"]),
 ("Message demande éligibilité", "mon éligibilité" in x["msg"]),
 ("Message demande dépenses éligibles", "dépenses éligibles" in x["msg"]),
 ("Message demande procédure", "procédure de dépôt" in x["msg"]),
 ("Checklist texte générée", "AideRadar — Checklist dossier" in x["checklistText"])
]
for label,ok in dossier_checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in dossier_checks): raise SystemExit(8)
print(f"Dossier assistant contracts: {len(dossier_checks)} checks passed.")


# Tracking dashboard contracts.
dashboard_js = prefix + r"""
const tracking={
  a1:"verify",
  a2:"preparing",
  a3:"done"
};
const metas={
  a1:{name:"Prime A",source:"https://example.test/a",end_date:"2026-09-10",exact_grant:1000,readiness:70,next_action:"Vérifier l'éligibilité",checklist_ids:["d1","d2"]},
  a2:{name:"Prime B",source:"",end_date:"2026-12-31",exact_grant:2500,readiness:82,next_action:"Préparer les devis",checklist_ids:["x1","x2","x3"]},
  a3:{name:"Prêt C",source:"https://example.test/c",end_date:"",exact_grant:0,readiness:95,next_action:"Archiver la décision",checklist_ids:["z1"]}
};
const dossiers={
  a1:{d1:true,d2:false},
  a2:{x1:true,x2:true,x3:false},
  a3:{z1:true}
};
const model=dashboardModel(tracking,metas,dossiers,"2026-08-25T10:00:00");
const preparing=filterDashboardItems(model.items,"preparing");
const text=trackingDashboardText(model);
console.log(JSON.stringify({model,preparing,text}));
"""
with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
    f.write(dashboard_js); dashboard_file=f.name
res=subprocess.run(["node",dashboard_file],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(9)
dash=json.loads(res.stdout)
model=dash["model"]
dashboard_checks=[
 ("Dashboard compte 3 aides", model["total"] == 3),
 ("Dashboard statut vérifier", model["counts"]["verify"] == 1),
 ("Dashboard statut préparation", model["counts"]["preparing"] == 1),
 ("Dashboard statut obtenue", model["counts"]["done"] == 1),
 ("Dashboard total subventions = 3500", model["grant_total"] == 3500),
 ("Dashboard détecte échéance urgente", model["urgent_count"] == 1),
 ("Dashboard progression dossier A = 50%", next(x for x in model["items"] if x["key"]=="a1")["checklist_pct"] == 50),
 ("Dashboard progression dossier B = 67%", next(x for x in model["items"] if x["key"]=="a2")["checklist_pct"] == 67),
 ("Filtre préparation retourne une aide", len(dash["preparing"]) == 1 and dash["preparing"][0]["key"]=="a2"),
 ("Export suivi généré", "AideRadar — Suivi des démarches" in dash["text"] and "Prime A" in dash["text"])
]
for label,ok in dashboard_checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in dashboard_checks): raise SystemExit(10)
print(f"Tracking dashboard contracts: {len(dashboard_checks)} checks passed.")


# Financing-path contracts.
financing_js = prefix + r"""
const P={activity:"commerce",activityDetail:"Commerce de détail",naf:"",companyStatus:"standard",companyAge:"1to3",dept:"89",postalCode:"89000",commune:"Auxerre",communeCode:"89024",epciCode:"",streetAddress:"",latitude:0,longitude:0,employees:"1-4",project:"invest",budget:20000,turnover:200000,ownerAge:35,franchise:false,jobSeeker:false};
const mk=(id,nom,montant,conditions,natures=[])=>({id_aid:id,nom,benef:"TPE",objet:"Financer un investissement",conditions,montant,operations:"Matériel",source:"https://example.test/"+id,deps:["89"],status:1,natures,_quality:{score:100,issues:[]}});
const g1=mk("g1","Prime investissement","Prime forfaitaire de 4 000 €","Demande avant tout engagement.");
const g2=mk("g2","Subvention complémentaire","Prime forfaitaire de 2 000 €","Aide soumise aux règles de cumul et de minimis.");
const loan=mk("l1","Prêt croissance","Prêt à taux zéro de 5 000 € à 20 000 €","Sous réserve d'étude du dossier.");
const ex=mk("e1","Exonération locale","Exonération fiscale","Exonération de fiscalité locale.",["Exonération"]);
const bad=mk("b1","Prime exclusive","Prime forfaitaire de 1 500 €","Cette aide est non cumulable avec une autre aide sur la même dépense.");
const rows=[g1,g2,loan,ex,bad].map(a=>({a,r:scoreAid(a,P)})).filter(x=>x.r!==null);
const path=buildFinancingPath(rows,P);
const txt=financingPathText(path);
console.log(JSON.stringify({path,txt,kinds:rows.map((x,i)=>aidFinanceKind(x.a,decisionModel(x.a,x.r,P,i))),riskBad:cumulationRisk(bad),before:beforeSpendConstraint(g1)}));
"""
with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
    f.write(financing_js); financing_file=f.name
res=subprocess.run(["node",financing_file],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(11)
fin=json.loads(res.stdout)
path=fin["path"]
financing_checks=[
 ("Parcours contient étapes", len(path["steps"]) >= 2),
 ("Subvention principale prudente = 4000", path["primaryGrant"] == 4000),
 ("Les subventions ne sont pas additionnées", path["primaryGrant"] != 6000),
 ("Autre subvention signalée séparément", path["otherExactGrantCount"] >= 1),
 ("Prêt détecté comme financement", "loan" in fin["kinds"]),
 ("Exonération détectée", "exemption" in fin["kinds"]),
 ("Non-cumul détecté fort", fin["riskBad"]["level"] == "high"),
 ("Avant engagement détecté", fin["before"] is True),
 ("Le parcours signale une vérification de cumul", path["needsCumulationCheck"] is True),
 ("Texte parcours généré", "Parcours de financement recommandé" in fin["txt"]),
 ("Texte rappelle le cumul", "cumul" in fin["txt"].lower())
]
for label,ok in financing_checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in financing_checks): raise SystemExit(12)
print(f"Financing path contracts: {len(financing_checks)} checks passed.")


# V28 reliability contracts.
reliability_js = prefix + r"""
const BASEP={activity:"btp",activityDetail:"Plomberie",naf:"43.22A",companyStatus:"standard",companyAge:"lt1",dept:"89",postalCode:"89130",commune:"Toucy",communeCode:"89419",epciCode:"200067130",streetAddress:"",latitude:0,longitude:0,employees:"1-4",project:"creation",budget:25000,turnover:0,ownerAge:29,franchise:false,jobSeeker:false,registeredRM:"unknown",registeredRCS:"unknown",bankFinancing:"unknown",zoneQpv:"unknown",zoneFrr:"unknown",zoneAfr:"unknown"};
const aid=(id,nom,benef,obj,cond,effectif="")=>({id_aid:id,nom,benef,objet:obj,conditions:cond,montant:"Prime forfaitaire de 1 000 €",operations:"",source:"https://example.test/"+id,deps:["89"],status:1,effectif,_quality:{score:100,issues:[]}});
const qpv=aid("q","Prime QPV","TPE","Créer une entreprise en quartier prioritaire","Être installé dans un QPV.");
const frr=aid("f","Prime FRR","TPE","Créer une entreprise en France Ruralités Revitalisation","Être en zone FRR.");
const afr=aid("a","Prime AFR","TPE","Créer une entreprise en zone d'aide à finalité régionale","Être en zone AFR.");
const bank=aid("b","Prêt d'honneur","TPE","Créer une entreprise","Le prêt est toujours couplé à un prêt bancaire.");
const rm=aid("rm","Aide artisan","TPE inscrites au répertoire des métiers","Créer une entreprise","Inscription au RM obligatoire.");
const age=aid("age","Prime jeunes","Jeunes entre 18 et 30 ans","Créer une entreprise","");
const naf=aid("naf","Aide hors plomberie","TPE. Secteurs exclus : activités NAF 43.22","Créer une entreprise","");
const eff=aid("eff","Aide grande PME","TPE/PME","Créer une entreprise","", "50-249");
const narrow={...aid("prof","Aide culture","Entreprises culturelles","Créer une entreprise",""),profils:["Culture-Médias"]};

const qUnknown=hardConditionGate(qpv,BASEP);
const qYes=hardConditionGate(qpv,{...BASEP,zoneQpv:"yes"});
const qNo=hardConditionGate(qpv,{...BASEP,zoneQpv:"no"});
const fYes=hardConditionGate(frr,{...BASEP,zoneFrr:"yes"});
const aNo=hardConditionGate(afr,{...BASEP,zoneAfr:"no"});

const bankUnknown=universalMandatoryChecks(bank,BASEP);
const bankYes=universalMandatoryChecks(bank,{...BASEP,bankFinancing:"yes"});
const bankNo=universalMandatoryChecks(bank,{...BASEP,bankFinancing:"no"});
const rmUnknown=universalMandatoryChecks(rm,BASEP);
const rmYes=universalMandatoryChecks(rm,{...BASEP,registeredRM:"yes"});
const rmNo=universalMandatoryChecks(rm,{...BASEP,registeredRM:"no"});

const ageOk=ownerAgeGate(age,{...BASEP,ownerAge:29});
const ageBad=ownerAgeGate(age,{...BASEP,ownerAge:35});
const ageReq=parseOwnerAgeRequirement(age);
const nafGate=explicitNafExclusionGate(naf,BASEP);
const effGate=structuredEffectifGate(eff,BASEP);
const profGate=structuredProfileGate(narrow,BASEP);

console.log(JSON.stringify({qUnknown,qYes,qNo,fYes,aNo,bankUnknown,bankYes,bankNo,rmUnknown,rmYes,rmNo,ageOk,ageBad,ageReq,nafGate,effGate,profGate}));
"""
with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
    f.write(reliability_js); reliability_file=f.name
res=subprocess.run(["node",reliability_file],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(13)
v=json.loads(res.stdout)

def state(checks,label):
    for c in checks:
        if c.get("label")==label:
            return c.get("state")
    return None

reliability_checks=[
 ("QPV inconnu exclu", v["qUnknown"]["exclude"] is True),
 ("QPV vérifié oui accepté", v["qYes"]["exclude"] is False),
 ("QPV vérifié non exclu", v["qNo"]["exclude"] is True),
 ("FRR vérifié oui accepté", v["fYes"]["exclude"] is False),
 ("AFR vérifié non exclu", v["aNo"]["exclude"] is True),
 ("Banque inconnue reste check", state(v["bankUnknown"],"Financement associé")=="check"),
 ("Banque oui passe ok", state(v["bankYes"],"Financement associé")=="ok"),
 ("Banque non devient fail", state(v["bankNo"],"Financement associé")=="fail"),
 ("RM inconnu reste check", state(v["rmUnknown"],"Inscription RM")=="check"),
 ("RM oui passe ok", state(v["rmYes"],"Inscription RM")=="ok"),
 ("RM non devient fail", state(v["rmNo"],"Inscription RM")=="fail"),
 ("Âge 29 compatible 18-30", v["ageOk"]["exclude"] is False),
 ("Âge 35 exclu 18-30", v["ageBad"]["exclude"] is True),
 ("Parse âge min=18", v["ageReq"]["min"]==18),
 ("Parse âge max=30", v["ageReq"]["max"]==30),
 ("NAF explicitement exclu détecté", v["nafGate"]["exclude"] is True),
 ("Effectif structuré incompatible exclu", v["effGate"]["exclude"] is True),
 ("Profil officiel étroit incompatible exclu", v["profGate"]["exclude"] is True)
]
for label,ok in reliability_checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in reliability_checks): raise SystemExit(14)
print(f"Reliability contracts: {len(reliability_checks)} checks passed.")


# V29 UX / mobile wizard contracts.
ux_js = prefix + r"""
const good1={activity:"btp",activityDetail:"Plomberie",companyStatus:"standard",companyAge:"lt1",employees:"1-4",dept:"89",project:"creation",budgetRaw:"25000",naf:"43.22A",turnover:0,ownerAge:29,franchise:false,jobSeeker:true,registeredRM:"yes",registeredRCS:"unknown",bankFinancing:"unknown",postalCode:"89130",commune:"Toucy",streetAddress:"",zoneQpv:"unknown",zoneFrr:"unknown",zoneAfr:"unknown"};
const bad1={...good1,activity:"",activityDetail:"",employees:"",dept:"999"};
const bad2={...good1,project:"",budgetRaw:"",postalCode:"8913"};
const review=reviewModel(good1);
const advice=emptyStateAdvice({...good1,naf:"",postalCode:"",commune:""});
console.log(JSON.stringify({
  dept89:validDepartment("89"),
  dept2a:validDepartment("2a"),
  dept971:validDepartment("971"),
  deptBad:validDepartment("999"),
  norm2a:normalizeDepartment(" 2a "),
  goodStep1:wizardValidation(good1,1),
  badStep1:wizardValidation(bad1,1),
  goodStep2:wizardValidation(good1,2),
  badStep2:wizardValidation(bad2,2),
  precision:optionalPrecisionCount(good1),
  review,advice
}));
"""
with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False,encoding="utf-8") as f:
    f.write(ux_js); ux_file=f.name
res=subprocess.run(["node",ux_file],capture_output=True,text=True)
if res.returncode:
    print(res.stderr,file=sys.stderr); raise SystemExit(15)
ux=json.loads(res.stdout)

ux_checks=[
 ("Département 89 accepté", ux["dept89"] is True),
 ("Département Corse 2A accepté", ux["dept2a"] is True),
 ("Département 971 accepté", ux["dept971"] is True),
 ("Département 999 refusé", ux["deptBad"] is False),
 ("Département normalisé en majuscules", ux["norm2a"]=="2A"),
 ("Étape entreprise valide", len(ux["goodStep1"])==0),
 ("Étape entreprise bloque les champs manquants", len(ux["badStep1"])>=3),
 ("Étape projet valide", len(ux["goodStep2"])==0),
 ("Étape projet bloque projet/budget/CP invalides", len(ux["badStep2"])>=3),
 ("Précisions facultatives comptées", ux["precision"]>=4),
 ("Résumé reprend plomberie", "Plomberie" in ux["review"]["activityDetail"]),
 ("Résumé reprend budget", ux["review"]["budget"]==25000),
 ("État vide propose des pistes", len(ux["advice"])>=2),
 ("Wizard HTML contient 3 étapes", html.count('data-wizard-step="')==3),
 ("Bouton retry DB présent", 'id="retryDbBtn"' in html),
 ("Résultats détaillés repliables", 'class="result-more"' in html),
 ("Technique repliée", 'class="technical-details"' in html),
 ("Formulaire sans ancien advancedProfile", 'id="advancedProfile"' not in html)
]
for label,ok in ux_checks: print(("OK" if ok else "FAIL"),"-",label)
if not all(ok for _,ok in ux_checks): raise SystemExit(16)
print(f"UX contracts: {len(ux_checks)} checks passed.")

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
