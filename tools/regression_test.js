const fs=require('fs'), vm=require('vm');
const html=fs.readFileSync(process.argv[2]||'index.html','utf8');
const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(m=>m[1]);
class El{
 constructor(id=''){this.id=id;this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.style={};this.dataset={};this.innerHTML='';this.textContent='';this.className='';this.options=[];this.selectedOptions=[];this.classList={add(){},remove(){},toggle(){},contains(){return false}}}
 addEventListener(){} removeEventListener(){} setAttribute(){} removeAttribute(){} appendChild(){return new El()} insertBefore(){} querySelector(){return null} querySelectorAll(){return []} closest(){return null} scrollIntoView(){} click(){} remove(){} requestSubmit(){} focus(){}
}
const elements=new Map();
function getEl(id){if(!elements.has(id)) elements.set(id,new El(id));return elements.get(id)}
global.window=global;
global.document={
 getElementById:getEl,
 querySelector:()=>null, querySelectorAll:()=>[],
 createElement:(tag)=>new El(tag),
 body:new El('body'),
 documentElement:new El('html'),
 addEventListener(){},
};
global.localStorage={getItem(){return null},setItem(){},removeItem(){}};
global.sessionStorage=global.localStorage;
global.navigator={share:null,serviceWorker:null,clipboard:{writeText:async()=>{}}};
global.location={protocol:'file:',href:'file://test',origin:'null'};
global.history={replaceState(){}};
global.CSS={escape:s=>String(s)};
global.Blob=class{};
global.URL={createObjectURL(){return 'blob:'},revokeObjectURL(){}};
global.fetch=async()=>{throw new Error('offline test')};
global.indexedDB={open(){throw new Error('no idb')}};
global.confirm=()=>true;global.alert=()=>{};
global.requestAnimationFrame=(f)=>setTimeout(f,0);
global.performance={now:()=>Date.now()};
global.structuredClone=o=>JSON.parse(JSON.stringify(o));
global.HTMLElement=El;
try{
 vm.runInThisContext(scripts.join('\n;\n'),{filename:'aideradar.js'});
 console.log('loaded scripts');
 console.log('DB', typeof DB!=='undefined'?DB.length:'undef');
 const scenarios=[
  ['plomberie_creation_89',{activity:'btp',activityDetail:'Plomberie',companyStatus:'standard',companyAge:'lt1',dept:'89',employees:'1-4',project:'creation',projectDetail:'Créer une entreprise de plomberie chauffage',budget:25000,ownerAge:29,jobSeeker:true}],
  ['boulangerie_invest_89',{activity:'commerce',activityDetail:'Boulangerie',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'1-4',project:'invest',projectDetail:'Acheter un four professionnel et un pétrin',budget:30000,turnover:180000}],
  ['plombier_vehicle_89',{activity:'btp',activityDetail:'Plomberie chauffage',companyStatus:'standard',companyAge:'1to3',dept:'89',employees:'1-4',project:'vehicle',projectDetail:'Acheter un utilitaire diesel d occasion',budget:30000,turnover:120000}],
  ['restaurant_local_89',{activity:'restauration',activityDetail:'Restaurant traditionnel',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'1-4',project:'local',projectDetail:'Rénover la salle et la cuisine du restaurant',budget:80000,turnover:250000}],
  ['agence_web_digital_89',{activity:'services',activityDetail:'Agence web',companyStatus:'standard',companyAge:'1to3',dept:'89',employees:'1-4',project:'digital',projectDetail:'Créer un site e-commerce et acheter des logiciels',budget:20000,turnover:100000}],
  ['pme_ai_89',{activity:'services',activityDetail:'Agence de services numériques',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'10-49',project:'digital',projectDetail:'Adopter une solution intelligence artificielle pour automatiser le support',budget:50000,turnover:800000}],
  ['industrie_innovation_89',{activity:'industrie',activityDetail:'Fabrication industrielle',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'10-49',project:'innovation',projectDetail:'Développer un nouveau procédé industriel innovant R&D',budget:300000,turnover:2500000}],
  ['commerce_hire_89',{activity:'commerce',activityDetail:'Commerce de proximité',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'1-4',project:'hire',projectDetail:'Embaucher un salarié en CDI',budget:30000,turnover:250000}],
  ['commerce_apprentice_89',{activity:'commerce',activityDetail:'Commerce de proximité',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'1-4',project:'hire',projectDetail:'Recruter un apprenti en alternance',budget:15000,turnover:250000}],
  ['plombier_energy_89',{activity:'btp',activityDetail:'Plomberie chauffage',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'1-4',project:'energy',projectDetail:'Installer une pompe à chaleur et réduire la consommation énergétique des locaux',budget:40000,turnover:180000}],
  ['btp_cash_89',{activity:'btp',activityDetail:'Entreprise de bâtiment',companyStatus:'standard',companyAge:'gt3',dept:'89',employees:'5-9',project:'cash',projectDetail:'Renforcer la trésorerie et financer le besoin en fonds de roulement',budget:50000,turnover:600000}],
  ['coiffure_creation_89',{activity:'artisan',activityDetail:'Salon de coiffure',companyStatus:'standard',companyAge:'lt1',dept:'89',employees:'1-4',project:'creation',projectDetail:'Créer un salon de coiffure',budget:25000,ownerAge:27,jobSeeker:true}],
 ];
 function base(p){return Object.assign({naf:'',postalCode:'',commune:'',communeCode:'',epciCode:'',zoneQpv:'unknown',zoneFrr:'unknown',zoneAfr:'unknown',streetAddress:'',latitude:0,longitude:0,turnover:0,ownerAge:0,franchise:false,jobSeeker:false,registeredRM:'unknown',registeredRCS:'unknown',bankFinancing:'unknown'},p)}
 const all=[];
 for(const [name,p0] of scenarios){const p=base(p0);const territorial=DB.filter(a=>(a.deps||[]).includes('ALL')||(a.deps||[]).includes(p.dept));const scored=territorial.map(a=>({a,r:scoreAid(a,p)})).filter(x=>x.r!==null);const eligible=scored.filter(x=>eligibilitySummary(x.a,x.r,p).state!=='no');eligible.sort((x,y)=>{const xc=confidenceScore(x.a,x.r,p),yc=confidenceScore(y.a,y.r,p);return (yc-xc)||(y.r.score-x.r.score)});const ded=dedupeRankedRows(eligible,p);const strong=ded.filter(x=>x.r.score>=50);const rows=(strong.length?strong:ded).slice(0,12);const names=rows.map(x=>clean(x.a.nom));all.push({name,count:names.length,names});console.log(name,names.length,names.slice(0,5).join(' / '));}
 const get=n=>all.find(x=>x.name===n).names;
 if(!get('plomberie_creation_89').some(x=>x.includes('Initiative 89'))) throw Error('Initiative 89 missing');
 if(!get('plomberie_creation_89').some(x=>x.includes('Avance remboursable pour la création et la reprise des TPE'))) throw Error('TPE BFC missing');
 if(get('plomberie_creation_89').some(x=>x.toLowerCase().includes('culture et à la création numérique'))) throw Error('culture false positive');
 if(get('plombier_vehicle_89').some(x=>x.includes('Horizon Europe'))) throw Error('Horizon vehicle false positive');
 if(!get('commerce_apprentice_89').some(x=>x.toLowerCase().includes('apprenti'))) throw Error('apprentice aid missing');
 if(!get('industrie_innovation_89').some(x=>/innovation|inno/i.test(x))) throw Error('innovation aid missing');
 if(get('boulangerie_invest_89').some(x=>/amiante|cabine de peinture|international|export/i.test(x))) throw Error('boulangerie specialized false positive');
 if(get('plombier_vehicle_89').some(x=>/horizon|vélo|velo|bicyc/i.test(x))) throw Error('vehicle specialized false positive');
 if(get('agence_web_digital_89').some(x=>/culture et.*création|effets visuels|cinéma|cinema/i.test(x))) throw Error('digital culture false positive');
 if(get('btp_cash_89').some(x=>/culture|cinéma|cinema|horizon europe/i.test(x))) throw Error('cash irrelevant false positive');
 if(typeof window.AideRadarV4!=="object" || window.AideRadarV4.version!=="4.0.0") throw Error('V4 layer missing');
 if(typeof window.AideRadarV5!=="object" || window.AideRadarV5.version!=="5.0.0") throw Error('V5 product layer missing');
 const trustAid=DB.find(a=>String(a.id)==='3596');
 const trust=window.AideRadarV4.trustForAid(trustAid);
 if(!trust.some(x=>/Lien financeur disponible/.test(x.text))) throw Error('V4 source trace missing');
 // Scenario de référence exact partagé par l'utilisateur : le plan d'action doit être ordonné par préparation.
 const pref=base({activity:'btp',activityDetail:'Plomberie',companyStatus:'standard',companyAge:'lt1',dept:'89',employees:'1-4',project:'creation',projectDetail:'Crée une entreprise de plomberie',budget:25000,ownerAge:29,jobSeeker:true});
 const tr=DB.filter(a=>(a.deps||[]).includes('ALL')||(a.deps||[]).includes(pref.dept));
 const sr=tr.map(a=>({a,r:scoreAid(a,pref)})).filter(x=>x.r!==null).filter(x=>eligibilitySummary(x.a,x.r,pref).state!=='no');
 sr.sort((x,y)=>(confidenceScore(y.a,y.r,pref)-confidenceScore(x.a,x.r,pref))||(y.r.score-x.r.score));
 const dd=dedupeRankedRows(sr,pref), ss=dd.filter(x=>x.r.score>=50), rr=(ss.length?ss:dd).slice(0,12), road=buildRoadmap(rr,pref);
 const rt=road.top.map(x=>clean(x.a.nom));
 // Le flux public peut faire bouger légèrement les scores de préparation.
 // On verrouille les décisions métier, pas un ordre artificiellement figé.
 if(!/Initiative 89/.test(rt[0]||'')) throw Error('reference roadmap rank 1 wrong: '+rt.join(' / '));
 const top3=rt.slice(0,3);
 if(!top3.some(x=>/Avance remboursable.*TPE/i.test(x))) throw Error('TPE BFC missing from reference top 3: '+rt.join(' / '));
 if(!top3.some(x=>/Pacte création/i.test(x))) throw Error('Pacte création missing from reference top 3: '+rt.join(' / '));
 const p45={...pref,ownerAge:45};
 const tr45=DB.filter(a=>(a.deps||[]).includes('ALL')||(a.deps||[]).includes(p45.dept)).map(a=>({a,r:scoreAid(a,p45)})).filter(x=>x.r!==null).filter(x=>eligibilitySummary(x.a,x.r,p45).state!=='no');
 tr45.sort((x,y)=>(confidenceScore(y.a,y.r,p45)-confidenceScore(x.a,x.r,p45))||(y.r.score-x.r.score));
 const d45=dedupeRankedRows(tr45,p45), s45=d45.filter(x=>x.r.score>=50), r45=(s45.length?s45:d45).slice(0,12), road45=buildRoadmap(r45,p45);
 if(road45.top.some(x=>/Pacte création/i.test(clean(x.a.nom)))) throw Error('under-30 Pacte incorrectly prioritized for age 45');
 console.log('V4_TRUST_AND_ROADMAP_OK',rt.join(' / '));
 // CSV parser + patch unit test against full generated CSV to test V3 path without network.
 const sample='id_aid;aid_nom;aid_objet;aid_conditions;aid_montant;aid_benef;date_fin;status;horodatage;complements_sources\n3596;Prêt d\'honneur Initiative 89;Objet test;Condition test;Prêt de 1 000 à 23 000 €;Créateurs;2026-12-31;1;2026-08-25;https://www.initiative89.fr/nos-principaux-outils-de-financement.html\n';
 const parsed=window.AideRadarV3.parseCSV(sample);if(parsed.length!==2)throw Error('CSV parser failed');
 
 // Full V3 synchronisation patch test on all embedded IDs (network-independent).
 const q=s=>`"${String(s??'').replace(/"/g,'""').replace(/\r?\n/g,' ')}"`;
 let mock='id_aid;aid_nom;aid_objet;aid_operations_el;aid_conditions;aid_montant;aid_benef;date_fin;status;horodatage;complements_sources\n';
 for(const a of DB){
   const changed=String(a.id)==='3596';
   mock += [a.id,q(a.nom),q(a.objet),q(a.operations),q(a.conditions),q(changed?'Prêt d’honneur de 1 000 à 23 000 € à taux zéro':a.montant),q(a.benef),a.fin||'',1,'2026-08-25',q(a.source||'')].join(';')+'\n';
 }
 const patch=window.AideRadarV3.buildRemotePatch(mock);
 if(patch.matched<2400) throw Error('live patch matched too few: '+patch.matched);
 if(!patch.changes.some(x=>String(x.id)==='3596'&&x.fields.includes('montant'))) throw Error('live change detection failed');
 console.log('V3_PATCH_OK',patch.matched,patch.changes.length);
 console.log('ALL_TESTS_OK');
}catch(e){console.error('HARNESS_FAIL',e&&e.stack||e);process.exitCode=1}
