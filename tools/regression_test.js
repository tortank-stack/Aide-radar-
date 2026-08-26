const fs=require('fs'), vm=require('vm');
const htmlPath=process.argv[2]||'index.html', dbPath=process.argv[3]||'aides.json';
const html=fs.readFileSync(htmlPath,'utf8');
const dbPayload=JSON.parse(fs.readFileSync(dbPath,'utf8'));
const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(m=>m[1]);
class El{constructor(id=''){this.id=id;this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.style={};this.dataset={};this.innerHTML='';this.textContent='';this.className='';this.options=[];this.selectedOptions=[];this.classList={add(){},remove(){},toggle(){},contains(){return false}}}addEventListener(){} removeEventListener(){} setAttribute(){} removeAttribute(){} appendChild(){return new El()} insertBefore(){} querySelector(){return null} querySelectorAll(){return []} closest(){return null} scrollIntoView(){} click(){} remove(){} requestSubmit(){} focus(){}}
const elements=new Map();function getEl(id){if(!elements.has(id))elements.set(id,new El(id));return elements.get(id)}
global.window=global;global.document={getElementById:getEl,querySelector:()=>null,querySelectorAll:()=>[],createElement:(tag)=>new El(tag),body:new El('body'),documentElement:new El('html'),addEventListener(){}};
global.localStorage={getItem(){return null},setItem(){},removeItem(){}};global.sessionStorage=global.localStorage;
global.navigator={share:null,serviceWorker:null,clipboard:{writeText:async()=>{}}};global.location={protocol:'file:',href:'file://test',origin:'null'};global.history={replaceState(){}};global.CSS={escape:s=>String(s)};global.Blob=class{};global.URL={createObjectURL(){return 'blob:'},revokeObjectURL(){}};
global.fetch=async(url)=>{if(String(url).includes('aides.json'))return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(dbPayload)),text:async()=>JSON.stringify(dbPayload)};throw new Error('offline test')};
global.indexedDB={open(){throw new Error('no idb')}};global.confirm=()=>true;global.alert=()=>{};global.requestAnimationFrame=(f)=>setTimeout(f,0);global.performance={now:()=>Date.now()};global.structuredClone=o=>JSON.parse(JSON.stringify(o));global.HTMLElement=El;
(async()=>{try{
 vm.runInThisContext(scripts.join('\n;\n'),{filename:'aideradar.js'});if(typeof loadDB==='function')await loadDB();
 if(!Array.isArray(DB)||DB.length<2000)throw Error('external DB not loaded');
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
 function rowsFor(p0){const p=base(p0),territorial=DB.filter(a=>(a.deps||[]).includes('ALL')||(a.deps||[]).includes(p.dept)),scored=territorial.map(a=>({a,r:scoreAid(a,p)})).filter(x=>x.r!==null),eligible=scored.filter(x=>eligibilitySummary(x.a,x.r,p).state!=='no');eligible.sort((x,y)=>(confidenceScore(y.a,y.r,p)-confidenceScore(x.a,x.r,p))||(y.r.score-x.r.score));const ded=dedupeRankedRows(eligible,p),strong=ded.filter(x=>x.r.score>=50);return {p,rows:(strong.length?strong:ded).slice(0,12)}}
 const all=[];for(const [name,p0] of scenarios){const {rows}=rowsFor(p0),names=rows.map(x=>clean(x.a.nom));all.push({name,names});console.log(name,names.slice(0,5).join(' / '));}
 const get=n=>all.find(x=>x.name===n).names;
 if(!get('plomberie_creation_89').some(x=>x.includes('Initiative 89')))throw Error('Initiative 89 missing');
 if(!get('plomberie_creation_89').some(x=>x.includes('Avance remboursable pour la création et la reprise des TPE')))throw Error('TPE BFC missing');
 if(get('plomberie_creation_89').some(x=>x.toLowerCase().includes('culture et à la création numérique')))throw Error('culture false positive');
 if(get('plombier_vehicle_89').some(x=>/Horizon Europe|vélo|velo|bicyc/i.test(x)))throw Error('vehicle specialized false positive');
 if(!get('commerce_apprentice_89').some(x=>x.toLowerCase().includes('apprenti')))throw Error('apprentice aid missing');
 if(!get('industrie_innovation_89').some(x=>/innovation|inno/i.test(x)))throw Error('innovation aid missing');
 if(get('boulangerie_invest_89').some(x=>/amiante|cabine de peinture|international|export/i.test(x)))throw Error('boulangerie specialized false positive');
 if(get('agence_web_digital_89').some(x=>/culture et.*création|effets visuels|cinéma|cinema/i.test(x)))throw Error('digital culture false positive');
 if(get('btp_cash_89').some(x=>/culture|cinéma|cinema|horizon europe/i.test(x)))throw Error('cash irrelevant false positive');
 if(typeof window.AideRadarV4!=="object"||window.AideRadarV4.version!=="4.0.0")throw Error('V4 layer missing');
 if(typeof window.AideRadarV5!=="object"||window.AideRadarV5.version!=="5.1.0")throw Error('V5.1 layer missing');
 const pref=base({activity:'btp',activityDetail:'Plomberie',companyStatus:'standard',companyAge:'lt1',dept:'89',employees:'1-4',project:'creation',projectDetail:'Crée une entreprise de plomberie',budget:25000,ownerAge:29,jobSeeker:true});
 const {rows:rr}=rowsFor(pref),road=buildRoadmap(rr,pref),rt=road.top.map(x=>clean(x.a.nom));
 if(!/Initiative 89/.test(rt[0]||''))throw Error('reference roadmap rank 1 wrong: '+rt.join(' / '));
 const top3=rt.slice(0,3);if(!top3.some(x=>/Avance remboursable.*TPE/i.test(x)))throw Error('TPE BFC missing from reference top 3: '+rt.join(' / '));if(!top3.some(x=>/Pacte création/i.test(x)))throw Error('Pacte création missing from reference top 3: '+rt.join(' / '));
 const p45={...pref,ownerAge:45},{rows:r45}=rowsFor(p45),road45=buildRoadmap(r45,p45);if(road45.top.some(x=>/Pacte création/i.test(clean(x.a.nom))))throw Error('under-30 Pacte incorrectly prioritized for age 45');
 console.log('REFERENCE_OK',rt.join(' / '));console.log('ALL_TESTS_OK');
}catch(e){console.error('HARNESS_FAIL',e&&e.stack||e);process.exitCode=1}})();
