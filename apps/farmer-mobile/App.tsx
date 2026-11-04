import React,{useEffect,useMemo,useState} from 'react';
import {View,Text,ScrollView,Pressable,Switch,Linking,Image,StyleSheet} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import {MarketTools,Notices,Attachments,uploadPhoto} from './Tools';
import {PrivacyTools} from './PrivacyTools';
import {Evidence} from './Evidence';
import {AuthForm} from './AuthForm';
import {Api,Complaint,Village} from '../../packages/api-types/index';
import {labels,categories} from '../../packages/shared-domain/index';
import {load,save,loadToken,saveToken} from './storage';
import {color,radius,space,type,font} from './theme';
import {Button,Field,Card,CardTitle,Muted,Badge,Chip,Segmented,ScreenHeader,ListRow,Notice,EmptyState,BottomNav,Icon,Logo,IconName} from './ui';
import {LineChart,Sparkline,RadioCard,FarmScene} from './charts';

function Data({value,bare=false}:{value:any;bare?:boolean}){return <Evidence value={value} bare={bare}/>}
const cap=(x:string)=>x.charAt(0).toUpperCase()+x.slice(1).replaceAll('_',' ');
const shortDay=(d:string)=>{const t=new Date(d);return isNaN(+t)?String(d).slice(-5):t.toLocaleDateString('en-IN',{day:'numeric',month:'short'})};
const statusTone=(x:string):'good'|'warn'|'bad'|'neutral'=>['accepted','resolved'].includes(x)?'good':['rejected'].includes(x)?'bad':['submitted','pending_acknowledgement','needs_information','needs_clarification','awaiting_location'].includes(x)?'warn':'neutral';
const reportTypes:Record<string,{title:string;icon:IconName;tone:'sage'|'water'|'warn'}>={
 shortage:{title:'Low water in source',icon:'water-outline',tone:'water'},
 interruption:{title:'Supply interruption',icon:'git-pull-request-outline',tone:'warn'},
 irrigation:{title:'Irrigation problem',icon:'leaf-outline',tone:'sage'},
 leakage:{title:'Leakage / blockage',icon:'construct-outline',tone:'water'},
 other:{title:'Other issue',icon:'warning-outline',tone:'warn'},
};
export default function App(){
 const base=process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000';const [token,setToken]=useState('');const [refreshToken,setRefreshToken]=useState('');const api=useMemo(()=>new Api(base,token,refreshToken,(t,r)=>{setToken(t);setRefreshToken(r)}),[base,token,refreshToken]);
 const [profile,setProfile]=useState<any>(null);const [authNotice,setAuthNotice]=useState('');const [lang,setLang]=useState<'mr'|'en'>('en');const L=labels[lang];
 const [started,setStarted]=useState(false);const [menuOpen,setMenuOpen]=useState(false);const [addingFarm,setAddingFarm]=useState(false);const [mandiCrop,setMandiCrop]=useState('');const [advisoryFarm,setAdvisoryFarm]=useState('');
 const [page,setPage]=useState('home');const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [villages,setVillages]=useState<Village[]>([]);const [q,setQ]=useState('');const [villageId,setVillageId]=useState('');const [days,setDays]=useState<7|15>(7);const [outlook,setOutlook]=useState<any>(null);const [waterBudget,setWaterBudget]=useState<any>(null);const [lastSync,setLastSync]=useState('');const [cached,setCached]=useState(false);
 const [pickerOpen,setPickerOpen]=useState(false);const [villageResults,setVillageResults]=useState<Village[]|null>(null);const [description,setDescription]=useState('');const [category,setCategory]=useState('shortage');const [consent,setConsent]=useState(false);const [draftKey,setDraftKey]=useState(()=>Date.now()+'-'+Math.random().toString(36).slice(2));const [photo,setPhoto]=useState<string|null>(null);const [complaints,setComplaints]=useState<Complaint[]>([]);const [selected,setSelected]=useState<Complaint|null>(null);const [reply,setReply]=useState('');const [waLink,setWaLink]=useState('');const [ticketSearch,setTicketSearch]=useState('');
 const [editingFarm,setEditingFarm]=useState('');const [farms,setFarms]=useState<any[]>([]);const [crop,setCrop]=useState('');const [area,setArea]=useState('');const [sowing,setSowing]=useState('');const [method,setMethod]=useState('drip');const [coords,setCoords]=useState<{latitude:number;longitude:number}|null>(null);const [et0,setEt0]=useState('');const [kc,setKc]=useState('');const [rain,setRain]=useState('');const [efficiency,setEfficiency]=useState('');const [plan,setPlan]=useState<any>(null);
 const [question,setQuestion]=useState('');const [aiConsent,setAiConsent]=useState(false);const [answer,setAnswer]=useState<any>(null);const [content,setContent]=useState<any>(null);
 async function work(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{loadToken().then(value=>{if(value.startsWith('{')){try{const s=JSON.parse(value);setToken(s.access_token);setRefreshToken(s.refresh_token||'')}catch{setToken('')}}else setToken(value)})},[]);
 useEffect(()=>{if(!token)return;work(async()=>{const p=await api.request('/me');if(p.role!=='farmer')throw Error('Use the separate portal for this account role');setProfile(p);await saveToken(JSON.stringify({access_token:token,refresh_token:refreshToken}));setVillages(await api.request('/villages'));if(p.preferences.village_id)setVillageId(p.preferences.village_id);setFarms(await api.request('/farms'));setComplaints(await api.request('/complaints/mine'));const d=await load('draft:'+p.id);if(d){setDescription(d.description);setCategory(d.category);setDraftKey(d.key);setPhoto(d.photo)}})},[api]);
 useEffect(()=>{if(!villageId||!profile)return;work(async()=>{try{const a=await api.request(`/villages/${villageId}/supply-outlook`);const b=await api.request(`/villages/${villageId}/water-budget?days=${days}`);setOutlook(a);setWaterBudget(b);const sync=new Date().toISOString();setLastSync(sync);setCached(false);await save('supply-outlook-v1:'+profile.id+':'+villageId+':'+days,{a,b,sync})}catch(e){const c=await load('supply-outlook-v1:'+profile.id+':'+villageId+':'+days);if(c){setOutlook(c.a);setWaterBudget(c.b);setLastSync(c.sync);setCached(true)}else throw e}})},[villageId,days,profile]);
 async function submit(){if(!consent)throw Error('Consent required');const ticket=await api.request('/complaints','POST',{village_id:villageId,description,category,consent:true},draftKey);setComplaints(await api.request('/complaints/mine'));setSelected(ticket);if(photo){try{await uploadPhoto(api,ticket.id,photo)}catch(e){setError('Ticket saved. Photo requires retry: '+(e as Error).message)}}setDescription('');setPhoto(null);setDraftKey(Date.now()+'-'+Math.random().toString(36).slice(2));await save('draft:'+profile.id,null);setPage('complaints')}
 function go(p:string){setMenuOpen(false);setPage(p);setContent(null);if(p==='markets'||p==='schemes')work(async()=>setContent(await api.request('/'+p)))}
 const village=villages.find(v=>v.id===villageId);
 const villageLabel=village?`${village.name}, ${village.district}`:villageId?`Village ${villageId}`:'Select your village';
 const supplyPeriod=outlook?.outlooks?.find((r:any)=>r.days===days);const storageVals:number[]|null=supplyPeriod?.daily?.length?supplyPeriod.daily.map((d:any)=>d.closing_litres):null;
 const outlookBadge=!outlook?{label:'Select a village',tone:'neutral' as const}:cached?{label:'Cached',tone:'warn' as const}:supplyPeriod?.enough===true?{label:'Enough · scenario',tone:'water' as const}:supplyPeriod?.enough===false?{label:'Not enough · scenario',tone:'warn' as const}:{label:'Insufficient data',tone:'neutral' as const};
 const outlookMessage=!outlook?'Choose your village to check water supply.':supplyPeriod?.enough===true?`Usable supply covers the next ${days} days under reviewed assumptions.`:supplyPeriod?.enough===false?`Projected shortfall: ${supplyPeriod.shortage_litres.toLocaleString()} litres. First shortage: ${supplyPeriod.first_shortage_date}.`:'Current usable storage, supply and complete demand inputs are needed. Missing supply is not zero.';
 const en=lang==='en';
 const titles:Record<string,string>={outlook:'Water Outlook',actions:"Today's Action Card",farms:en?'My Farms':L.farms,advisory:'Crop Advisory',markets:en?'Mandi Prices':L.markets,schemes:L.schemes,report:en?'Submit Report':L.submit,complaints:L.complaints,assistant:L.assistant,settings:'Profile'};
 const navItems=[
  {key:'home',label:'Home',icon:'home-outline',iconActive:'home'},
  {key:'farms',label:en?'My Farms':L.farms,icon:'leaf-outline',iconActive:'leaf'},
  {key:'markets',label:en?'Market':L.markets,icon:'trending-up-outline',iconActive:'trending-up'},
  {key:'schemes',label:L.schemes,icon:'business-outline',iconActive:'business'},
  {key:'settings',label:'Profile',icon:'person-outline',iconActive:'person'},
 ] as const;
 const navActive=['outlook','actions'].includes(page)?'home':page==='advisory'?'farms':page;
 const menuItems:[string,string,IconName][]=[['home','Home','home-outline'],['outlook','Water Outlook','water-outline'],['actions',"Today's Action Card",'checkmark-done-outline'],['farms',en?'My Farms':L.farms,'leaf-outline'],['advisory','Crop Advisory','flower-outline'],['markets',en?'Mandi Prices':L.markets,'trending-up-outline'],['schemes',L.schemes,'business-outline'],['report',en?'Submit Report':L.submit,'warning-outline'],['complaints',L.complaints,'document-text-outline'],['assistant',L.assistant,'chatbubble-ellipses-outline'],['settings','Profile','person-outline']];
 const showPicker=!villageId||pickerOpen;
 const VillageChip=<Pressable accessibilityRole="button" accessibilityLabel="Choose village" onPress={()=>setPickerOpen(!pickerOpen)} style={s.villageChip}><Icon name="location" size={18}/><Text style={[type.label,{flexShrink:1}]} numberOfLines={1}>{villageLabel}</Text><Icon name={showPicker?'chevron-up':'chevron-down'} size={16} tint={color.textMuted}/></Pressable>;
 const searchVillages=()=>work(async()=>{const found=await api.request<Village[]>('/villages?q='+encodeURIComponent(q.trim()));setVillages(found);setVillageResults(found)});
 const VillagePicker=showPicker?<Card><CardTitle>Choose your village</CardTitle><Field label="Search village / district / LGD code" value={q} onChange={setQ} placeholder="Type a village, taluka or district" returnKeyType="search" onSubmitEditing={searchVillages}/><Button title="Search directory" variant="secondary" icon="search-outline" onPress={searchVillages}/>
  {villageResults===null&&<Muted style={{marginTop:space.sm}}>Search by village, taluka, district or LGD code. Matching villages will appear here.</Muted>}
  {(villageResults||[]).slice(0,20).map(v=><Pressable key={v.id} accessibilityRole="button" style={[s.village,villageId===v.id&&{backgroundColor:color.bgAlt}]} onPress={()=>work(async()=>{setVillageId(v.id);setPickerOpen(false);await api.request('/me','PATCH',{village_id:v.id,language:lang})})}><Icon name="location-outline" size={20} tint={villageId===v.id?color.green:color.textMuted}/><View style={{flex:1}}><Text style={type.heading}>{v.name}</Text><Muted>{v.taluka} · {v.district} · {v.id}</Muted></View>{villageId===v.id&&<Icon name="checkmark-circle" size={22}/>}</Pressable>)}
  {villageResults!==null&&!villageResults.length&&<EmptyState icon="location-outline" title={`No village matches "${q.trim()}"`} hint="Check the spelling, or search by taluka, district or LGD code."/>}</Card>:null;
 const villageBar=<Pressable accessibilityRole="button" onPress={()=>go('home')} style={s.chipBar}><Icon name="location" size={18}/><Text style={[type.label,{flex:1}]} numberOfLines={1}>{village?`Village: ${village.name}`:'No village selected · choose one on Home'}</Text><Icon name="chevron-forward" size={16} tint={color.textMuted}/></Pressable>;
 const quotes:any[]=Array.isArray(content?.quotes)?content.quotes:[];
 const mandiCrops=[...new Set(quotes.map((r:any)=>String(r.payload.commodity)))];
 const mandiRows=quotes.filter((r:any)=>!mandiCrop||r.payload.commodity===mandiCrop);
 const mandiDate=quotes.map((r:any)=>String(r.payload.source_date||'')).sort().pop();
 const farmFormOpen=!farms.length||addingFarm||!!editingFarm;
 const activeFarm=farms.find(f=>f.id===advisoryFarm)||farms[0];

 if(!profile&&!started)return <View style={s.root}><ScrollView contentContainerStyle={[s.container,{paddingTop:72,alignItems:'center'}]}>
  <Logo size={92}/><Text style={s.splashBrand}>JalSathi</Text><Text style={s.splashTag}>Maharashtra · Water & Farming</Text>
  <View style={{width:'100%',marginTop:space.xl}}><FarmScene/></View>
  <View style={{width:'100%',marginTop:space.xl}}><Button title="Get Started" icon="arrow-forward" iconRight onPress={()=>setStarted(true)}/><Button title="Continue in English" variant="outline" onPress={()=>{setLang('en');setStarted(true)}}/></View>
  <View style={{flexDirection:'row',gap:6,marginTop:space.lg}}><View style={[s.pageDot,{backgroundColor:color.green,width:20}]}/><View style={[s.pageDot,{backgroundColor:color.water}]}/><View style={[s.pageDot,{backgroundColor:color.border}]}/></View>
 </ScrollView></View>;

 return <View style={s.root}><ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
  <View style={s.top}>
   {profile?<Pressable accessibilityRole="button" accessibilityLabel="Open menu" onPress={()=>setMenuOpen(true)} hitSlop={10} style={s.menuBtn}><Icon name="menu" size={24} tint={color.text}/></Pressable>:<View style={{width:40}}/>}
   {profile?<View style={{flexDirection:'row',alignItems:'center',gap:space.sm,flex:1}}><Logo size={30}/><Text style={s.brand}>JalSathi</Text></View>:<View style={{flex:1}}/>}
   <Pressable accessibilityRole="button" onPress={()=>setLang(lang==='mr'?'en':'mr')} style={s.langPill}><Icon name="language-outline" size={16} tint={color.greenDark}/><Text style={[type.label,{color:color.greenDark}]}>{lang==='mr'?'English':'मराठी'}</Text></Pressable></View>
  {busy&&<Text accessibilityLiveRegion="polite" style={[type.small,{marginTop:space.sm}]}>Connecting…</Text>}{error?<Notice tone="error">{error}</Notice>:null}
  {!profile?<AuthForm api={api} onAuthenticated={(session,created)=>{setError('');setAuthNotice(created?'Account created. Welcome to JalSathi.':'');setRefreshToken(session.refresh_token||'');setToken(session.access_token)}}/>:<>
  {authNotice?<Notice tone="info">{authNotice}</Notice>:null}
  {page!=='home'&&<><View style={{height:space.lg}}/><ScreenHeader title={titles[page]||page} onBack={()=>go('home')} right={page==='farms'?<Pressable accessibilityRole="button" accessibilityLabel="Add farm" onPress={()=>{setEditingFarm('');setCrop('');setArea('');setSowing('');setAddingFarm(true)}} style={s.plusBtn}><Icon name="add" size={24} tint="#fff"/></Pressable>:undefined}/>{!['outlook','actions','farms','report'].includes(page)&&villageBar}</>}

  {page==='home'&&<>
   <View style={{marginTop:space.lg}}><Text style={type.display}>Hello, {String(profile.email||'farmer').split('@')[0]}!</Text><Text style={[type.body,{color:color.textMuted,marginTop:space.xs}]}>Get local water insights, crop guidance and government support.</Text></View>
   <View style={{marginTop:space.md}}>{VillageChip}</View>
   {VillagePicker}
   <Pressable accessibilityRole="button" accessibilityLabel="Open water outlook" onPress={()=>go('outlook')}><Card>
    <View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:space.sm}}><Text style={type.heading}>Water Outlook <Text style={type.small}>(Next {days} Days)</Text></Text><Badge label={outlookBadge.label} tone={outlookBadge.tone}/></View>
    <View style={{flexDirection:'row',alignItems:'center',gap:space.md,marginTop:space.md}}>
     <View style={[s.rowIconBig,{backgroundColor:color.waterBg}]}><Icon name="water" size={28} tint={color.water}/></View>
     <View style={{flex:1}}><Text style={s.bigNumber}>{supplyPeriod?.enough===true?'Enough':supplyPeriod?.enough===false?'Not enough':'—'}</Text><Muted>{outlookMessage}</Muted></View>
     {storageVals&&<Sparkline values={storageVals}/>}</View></Card></Pressable>
   <View style={{flexDirection:'row',gap:space.md}}>
    <Card style={s.tile}><View style={{flexDirection:'row',alignItems:'center',gap:space.sm}}><Icon name="partly-sunny-outline" size={26} tint={color.warn}/><View><Muted>Temperature</Muted><Text style={[type.heading,{color:color.textMuted}]}>Not available</Text></View></View></Card>
    <Card style={s.tile}><View style={{flexDirection:'row',alignItems:'center',gap:space.sm}}><Icon name="rainy-outline" size={26} tint={color.water}/><View><Muted>Rainfall</Muted><Text style={[type.heading,{color:color.textMuted}]}>Not available</Text></View></View></Card></View>
   <Muted style={{marginTop:-space.xs,marginBottom:space.sm}}>Weather is shown only when a dated, reviewed weather record exists for your farm.</Muted>
   <Button title="Today's Action Card" icon="arrow-forward" iconRight onPress={()=>go('actions')}/></>}

  {page==='outlook'&&<>
   <Segmented value={days} onChange={setDays} options={[{label:'7 Days',value:7},{label:'15 Days',value:15}]}/>
   <Card><Text style={[type.heading,{marginBottom:space.md}]}>Village: {village?`${village.name}, ${village.district}`:'not selected'}</Text>
    <View style={{flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:space.md}}>
     <View style={{flexDirection:'row',alignItems:'center',gap:space.sm,flex:1}}><View style={[s.rowIconBig,{backgroundColor:color.waterBg}]}><Icon name="water" size={28} tint={color.water}/></View><View><Muted>Projected shortfall</Muted><Text style={s.bigNumber}>{supplyPeriod?.shortage_litres!=null?supplyPeriod.shortage_litres.toLocaleString()+' L':'—'}</Text></View></View>
    </View>
    {storageVals?<View style={{marginTop:space.lg}}><LineChart values={storageVals} labels={supplyPeriod.daily.map((d:any)=>shortDay(d.date))}/></View>:<View style={{marginTop:space.md}}><Notice tone="warn">{outlookMessage}</Notice></View>}
    <Muted style={{marginTop:space.sm}}>{cached?'Cached record · ':''}Last sync: {lastSync?new Date(lastSync).toLocaleString():'No successful synchronization'}</Muted></Card>
   <Card tone="sage"><View style={{flexDirection:'row',gap:space.sm,alignItems:'center',marginBottom:space.xs}}><Icon name="information-circle-outline" size={20}/><Text style={type.heading}>Interpretation</Text></View><Text style={type.body}>{outlookMessage}</Text><Muted style={{marginTop:space.xs}}>Reviewed supply-and-demand scenario, not a measured future delivery guarantee. Chart shows projected closing storage in litres.</Muted></Card>
   <Data value={outlook||{status:'unavailable',reason:'Select a village'}} bare/>
   <Card><CardTitle>Water budget · litres</CardTitle><Data value={waterBudget||{status:'unavailable'}}/><Muted>Household and agriculture remain separate. Missing supply does not mean zero supply.</Muted></Card></>}

  {page==='actions'&&<>
   <Muted style={{marginBottom:space.sm}}>Recommended actions for your farm based on current water and crop conditions.</Muted>
   <Card tone="water"><View style={{flexDirection:'row',alignItems:'center',gap:space.md}}><View style={[s.rowIconBig,{backgroundColor:color.bg}]}><Icon name="water" size={26} tint={color.water}/></View><View style={{flex:1}}><View style={{flexDirection:'row',alignItems:'center',gap:space.sm,flexWrap:'wrap'}}><Text style={type.heading}>Water outlook</Text><Badge label={outlookBadge.label} tone={outlookBadge.tone}/></View><Text style={[type.body,{marginTop:space.xs}]}>{outlookMessage}</Text></View></View></Card>
   <Card tone="sage"><ListRow flat icon="water-outline" title="Irrigation" subtitle="Open your farms and dated irrigation estimates" onPress={()=>go('farms')}/></Card>
   <Card tone="sage"><ListRow flat icon="trending-up-outline" title="Mandi opportunity" subtitle="Compare dated market quotes with their sources" onPress={()=>go('markets')}/></Card>
   <Card tone="warn"><ListRow flat icon="business-outline" title="Government scheme" subtitle="Official notices and required documents" tone="warn" onPress={()=>go('schemes')}/></Card>
   <Card><ListRow icon="warning-outline" title={L.submit} subtitle="Tell JalSathi about a water problem" onPress={()=>go('report')}/><ListRow icon="document-text-outline" title={L.complaints} subtitle="Track your reports and their progress" onPress={()=>go('complaints')}/><ListRow icon="chatbubble-ellipses-outline" title={L.assistant} subtitle="Ask questions answered from saved evidence" onPress={()=>go('assistant')}/></Card></>}

  {page==='farms'&&<>
   {farms.map((f,i)=><Card key={f.id}><View style={{flexDirection:'row',gap:space.md}}><View style={s.farmIcon}><Icon name="leaf" size={24}/></View><View style={{flex:1}}>
    <Text style={type.heading}>{f.details.crop} · {f.details.area_ha} ha</Text><Muted>Farm {i+1}</Muted>
    <View style={{marginTop:space.sm,gap:2}}><Text style={type.body}>Sowing date: {f.details.sowing_date}</Text><Text style={type.body}>Irrigation: {cap(String(f.details.irrigation_method))}</Text></View>
    <View style={{flexDirection:'row',gap:space.sm,flexWrap:'wrap',marginTop:space.sm}}><View style={{flex:1,minWidth:130}}><Button title="Edit farm" variant="secondary" onPress={()=>{setAddingFarm(false);setEditingFarm(f.id);setCrop(f.details.crop);setArea(String(f.details.area_ha));setSowing(f.details.sowing_date);setMethod(f.details.irrigation_method);setVillageId(f.village_id);setCoords(f.details.latitude!=null?{latitude:f.details.latitude,longitude:f.details.longitude}:null)}}/></View><View style={{flex:1,minWidth:130}}><Button title="Crop advisory" variant="secondary" onPress={()=>{setAdvisoryFarm(f.id);go('advisory')}}/></View></View>
    <Button title="View dated irrigation plan" variant="secondary" onPress={()=>work(async()=>setPlan(await api.request(`/farms/${f.id}/irrigation-plan?days=${days}`)))}/></View></View></Card>)}
   {!farms.length&&<Card><EmptyState icon="leaf-outline" title="No farms yet" hint="Add your first farm below to get crop-stage irrigation estimates."/></Card>}
   {farmFormOpen&&<Card><CardTitle>{editingFarm?'Edit farm':'Add a farm'}</CardTitle>
    <Field label="Crop" value={crop} onChange={setCrop}/><Field label="Area (hectares)" value={area} onChange={setArea}/><Field label="Sowing date YYYY-MM-DD" value={sowing} onChange={setSowing}/>
    <Text style={[type.label,{marginTop:space.sm,marginBottom:6}]}>Irrigation method</Text><View style={s.wrap}>{['drip','sprinkler','surface'].map(m=><Chip key={m} label={cap(m)} active={method===m} onPress={()=>setMethod(m)}/>)}</View>
    <Button title="Use device coordinates (permission required)" variant="secondary" icon="navigate-outline" onPress={()=>work(async()=>{const p=await Location.requestForegroundPermissionsAsync();if(p.status!=='granted')throw Error('Location permission not granted');const c=await Location.getCurrentPositionAsync({});setCoords({latitude:c.coords.latitude,longitude:c.coords.longitude})})}/>
    {coords&&<Muted>Farmer-reported coordinates: {coords.latitude}, {coords.longitude}. Village association remains explicit.</Muted>}
    <Button title={editingFarm?'Save farm changes':'Save farm'} onPress={()=>work(async()=>{await api.request(editingFarm?'/farms/'+editingFarm:'/farms',editingFarm?'PATCH':'POST',{village_id:villageId,crop,area_ha:Number(area),sowing_date:sowing,irrigation_method:method,...coords});setFarms(await api.request('/farms'));setEditingFarm('');setAddingFarm(false)})}/>
    {(addingFarm||editingFarm)&&farms.length>0?<Button title="Cancel" variant="ghost" onPress={()=>{setAddingFarm(false);setEditingFarm('')}}/>:null}</Card>}
   {plan&&<Data value={plan}/>}
   <Card><CardTitle>Irrigation scenario</CardTitle><Muted>Enter explicit assumptions. This calculator does not claim measured weather or reviewed agronomy.</Muted>
    <Field label="ET0 (mm/day)" value={et0} onChange={setEt0}/><Field label="Crop-stage Kc" value={kc} onChange={setKc}/><Field label="Effective rain (mm/day)" value={rain} onChange={setRain}/><Field label="Application efficiency (0–1)" value={efficiency} onChange={setEfficiency}/>
    <Button title="Calculate daily requirement" onPress={()=>work(async()=>{if(![area,et0,kc,rain,efficiency].every(x=>x.trim()))throw Error('All scenario assumptions are required');setPlan(await api.request('/calculations/irrigation','POST',{area_ha:Number(area),et0:Number(et0),kc:Number(kc),effective_rain:Number(rain),efficiency:Number(efficiency),soil_contribution:0}))})}/></Card></>}

  {page==='advisory'&&<>
   {!farms.length?<Card><EmptyState icon="flower-outline" title="Add a farm first" hint="Crop advice is tied to the crop and sowing date of one of your farms."/><Button title="Go to My Farms" onPress={()=>go('farms')}/></Card>:<>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{gap:space.sm,paddingVertical:space.xs}}>{farms.map(f=><Chip key={f.id} label={f.details.crop} active={activeFarm?.id===f.id} onPress={()=>setAdvisoryFarm(f.id)}/>)}</ScrollView>
    <Card><View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:space.sm}}><Text style={type.heading}>Current stage</Text><Badge label={plan?.daily?.[0]?.crop_stage?cap(String(plan.daily[0].crop_stage)):'Not available'} tone={plan?.daily?.[0]?.crop_stage?'good':'neutral'}/></View>
     <Muted style={{marginTop:space.xs}}>{activeFarm?`${activeFarm.details.crop} · sown ${activeFarm.details.sowing_date}`:''}</Muted>
     <Button title="Check crop-stage plan" icon="refresh-outline" onPress={()=>work(async()=>setPlan(await api.request(`/farms/${activeFarm.id}/irrigation-plan?days=${days}`)))}/></Card>
    <Card tone="sage"><View style={{flexDirection:'row',gap:space.sm,alignItems:'center',marginBottom:space.xs}}><Icon name="flower-outline" size={20}/><Text style={type.heading}>Advisory</Text></View>
     <Text style={type.body}>{plan?.status&&plan.status!=='unavailable'?'Dated crop-stage water requirement from your farm record:':'No reviewed crop advice is published for this crop yet. Check the crop-stage plan to see its stage and water requirement when reviewed inputs exist.'}</Text></Card>
    {plan&&<Data value={plan}/>}</>}</>}

  {page==='report'&&<>
   <Text style={[type.heading,{marginBottom:space.xs}]}>Select Report Type</Text>
   {categories.map(c=><RadioCard key={c} icon={(reportTypes[c]||reportTypes.other).icon} title={(reportTypes[c]||{title:cap(c)}).title} tone={(reportTypes[c]||reportTypes.other).tone} selected={category===c} onPress={()=>setCategory(c)}/>)}
   <Card style={{marginTop:space.md}}><CardTitle>Report details</CardTitle><Muted>Reports go to JalSathi review. Acceptance and service progress are separate.</Muted>
   <Field label="Problem description" multiline value={description} onChange={setDescription} placeholder="Describe the water problem"/>
   <Button title="Select report photo" variant="secondary" icon="camera-outline" onPress={()=>work(async()=>{const r=await ImagePicker.launchImageLibraryAsync({mediaTypes:['images'],quality:.7});if(!r.canceled)setPhoto(r.assets[0].uri)})}/>
   {photo&&<><Image source={{uri:photo}} style={{height:160,borderRadius:radius.input,marginVertical:space.sm}}/><Muted>The photo is uploaded privately and decoded, inspected and re-encoded after the ticket is saved. Officials receive only reviewer-approved photos.</Muted></>}
   <View style={[s.row,{marginVertical:space.md}]}><Switch value={consent} onValueChange={setConsent} trackColor={{true:color.green,false:color.border}}/><Text style={[type.small,{flex:1}]}>I agree to submit this report for review.</Text></View>
   <Button title="Save draft on this device" variant="secondary" icon="save-outline" onPress={()=>work(async()=>save('draft:'+profile.id,{description,category,key:draftKey,photo}))}/>
   <Button title="Review & submit report" icon="arrow-forward" iconRight onPress={()=>work(submit)}/>
   <Muted>A draft is not submitted until the API returns a ticket. Retries reuse the same submission key.</Muted></Card></>}

  {page==='complaints'&&<Card><CardTitle right={<Button title="Refresh tickets" variant="secondary" onPress={()=>work(async()=>setComplaints(await api.request('/complaints/mine')))}/>}>Tickets</CardTitle>
   <Button title="Link WhatsApp complaints" variant="secondary" onPress={()=>work(async()=>{const r=await api.request('/whatsapp/link-code','POST');setWaLink(r.command)})}/>
   {waLink&&<Text selectable style={type.body}>Send this from your WhatsApp to JalSathi within 10 minutes: {waLink}. Then refresh tickets.</Text>}
   <Field label="Find by reference ID" value={ticketSearch} onChange={setTicketSearch}/><Button title="Track reference" variant="secondary" onPress={()=>work(async()=>setSelected(await api.request('/complaints/'+encodeURIComponent(ticketSearch.trim()))))}/>
   {complaints.map(c=><Pressable accessibilityRole="button" style={[s.village,selected?.id===c.id&&{backgroundColor:color.bgAlt}]} key={c.id} onPress={()=>setSelected(c)}><View style={{flex:1,gap:space.xs}}><Text style={type.heading}>{c.description}</Text><View style={{flexDirection:'row',gap:space.sm,flexWrap:'wrap'}}><Badge label={cap(c.review_status)} tone={statusTone(c.review_status)}/><Badge label={'Service demo: '+cap(c.service_status)} tone={statusTone(c.service_status)}/></View></View><Icon name="chevron-forward" size={18} tint={color.textMuted}/></Pressable>)}
   {!complaints.length&&<EmptyState icon="document-text-outline" title="No submitted tickets" hint="Reports you send will appear here with their progress."/>}
   {selected&&<View style={{marginTop:space.lg}}><Text selectable style={[type.label,{color:color.textMuted}]}>Ticket {selected.id}</Text>
    {selected.location&&<Text style={type.body}>{selected.location.village}, {selected.location.taluka}, {selected.location.district}</Text>}
    <Attachments api={api} complaintId={selected.id} photo={photo}/>
    <Text style={[type.heading,{marginTop:space.md}]}>Action timeline</Text>
    {selected.timeline.map((e,i)=><View style={s.timeline} key={i}><View style={s.dot}/><View style={{flex:1}}><Text style={type.label}>{cap(e.kind).replace(':',' · ')}</Text><Text style={type.body}>{e.note}</Text><Muted>{e.created_at}</Muted></View></View>)}
    <Field label="Reply to a request for information" value={reply} onChange={setReply}/><Button title="Send clarification" onPress={()=>work(async()=>{const c=await api.request(`/complaints/${selected.id}/messages`,'POST',{text:reply,village_id:villageId||null});setSelected(c);setReply('');setComplaints(await api.request('/complaints/mine'))})}/></View>}</Card>}

  {page==='markets'&&<>
   <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{gap:space.sm,paddingVertical:space.xs}}><Chip label="All crops" active={!mandiCrop} onPress={()=>setMandiCrop('')}/>{mandiCrops.map(c=><Chip key={c} label={c} active={mandiCrop===c} onPress={()=>setMandiCrop(c)}/>)}</ScrollView>
   <Card style={{padding:0,overflow:'hidden'}}>
    <View style={s.tHead}><Text style={[s.th,{flex:1.3}]}>Mandi</Text><Text style={[s.th,{flex:1.2,textAlign:'right'}]}>Price</Text><Text style={[s.th,{width:64,textAlign:'right'}]}>Change</Text></View>
    {mandiRows.slice(0,15).map((r:any)=><View key={r.id} style={s.tRow}><View style={{flex:1.3}}><Text style={type.heading}>{r.payload.market}</Text><Muted>{r.payload.commodity} · {r.payload.variety}</Muted></View><View style={{flex:1.2,alignItems:'flex-end'}}><Text style={type.heading}>{r.payload.price}</Text><Muted>{r.payload.units}</Muted></View><Text style={[type.body,{width:64,textAlign:'right',color:color.textMuted}]}>—</Text></View>)}
    {!mandiRows.length&&<EmptyState icon="trending-up-outline" title="No dated quotes yet" hint="Quotes appear only when a market response contains dated prices. Nothing is estimated."/>}</Card>
   <Card tone="water" style={{flexDirection:'row',gap:space.sm,alignItems:'center'}}><Icon name="information-circle-outline" size={20} tint={color.water}/><Text style={[type.small,{flex:1,color:color.text}]}>{mandiDate?`Prices as on ${mandiDate}. Quotes are not harvest-price forecasts; change needs an earlier dated quote.`:'Quotes retain original market, date, variety and units. They are not harvest-price forecasts.'}</Text></Card>
   <MarketTools api={api}/>
   <Button title="Open MSAMB official reports" variant="secondary" icon="open-outline" onPress={()=>Linking.openURL('https://www.msamb.com/ApmcDetail/APMCPriceInformation')}/></>}

  {page==='schemes'&&<Card><CardTitle>Official notices</CardTitle><Muted>Official evidence does not certify individual eligibility.</Muted><Notices api={api} villageId={villageId}/> {content&&<Data value={content}/>}<Button title="Open MahaDBT official portal" variant="secondary" icon="open-outline" onPress={()=>Linking.openURL('https://mahadbt.maharashtra.gov.in/Farmer/AgriLogin/AgriLogin')}/></Card>}

  {page==='assistant'&&<Card><CardTitle>Ask a question</CardTitle><Muted>Answers use the same saved evidence as the outlook. Missing evidence stays unavailable.</Muted>
   <Field label={lang==='mr'?'तुमचा प्रश्न':'Your question'} value={question} onChange={setQuestion} placeholder="For example: Will water be short this week?"/>
   <View style={[s.row,{marginVertical:space.sm}]}><Switch value={aiConsent} onValueChange={setAiConsent} trackColor={{true:color.green,false:color.border}}/><Text style={[type.small,{flex:1}]}>Allow question & evidence sharing with Gemini</Text></View>
   <Button title="Ask" icon="send-outline" onPress={()=>work(async()=>setAnswer(await api.request('/assistant/messages','POST',{village_id:villageId,question,language:lang,days,consent:aiConsent})))}/>
   {answer&&<View style={{marginTop:space.md}}><View style={{flexDirection:'row',gap:space.sm}}><Badge label={String(answer.mode)} tone="water"/><Badge label={String(answer.status)} tone="neutral"/></View><Card tone="sage" style={{marginTop:space.sm}}><Text style={[type.body,{lineHeight:24}]}>{answer.text}</Text></Card><Data value={answer.evidence}/></View>}</Card>}

  {page==='settings'&&<><Card><CardTitle>Profile & privacy</CardTitle><View style={s.row}><View style={s.avatar}><Icon name="person" size={26}/></View><View style={{flex:1}}><Text style={type.heading}>{profile.email}</Text><Muted>Farmer account</Muted></View></View><PrivacyTools api={api}/><Muted>Last successful sync: {lastSync||'unavailable'}</Muted>
   <Button title="Save language preference" onPress={()=>work(async()=>{await api.request('/me','PATCH',{language:lang,consent})})}/>
   <Button title="Sign out & clear native session" variant="secondary" icon="log-out-outline" onPress={()=>work(async()=>{if(refreshToken){try{await api.request('/auth/logout','POST',{refresh_token:refreshToken})}catch{}}await saveToken('');setRefreshToken('');setToken('');setProfile(null);setPage('home');setMenuOpen(false);setSelected(null);setComplaints([]);setFarms([]);setOutlook(null);setWaterBudget(null)})}/></Card></>}
  </>}
  <Text style={s.footer}>JalSathi · Evidence, dates and assumptions stay visible.{profile?' Officials actions are a demonstration.':''}</Text></ScrollView>
  {profile&&<View style={s.navWrap}><View style={s.navInner}><BottomNav items={navItems as any} active={navItems.some(i=>i.key===navActive)?navActive:''} onSelect={go}/></View></View>}
  {profile&&menuOpen&&<View style={StyleSheet.absoluteFill}><Pressable accessibilityRole="button" accessibilityLabel="Close menu" onPress={()=>setMenuOpen(false)} style={s.backdrop}/><View style={s.drawer}>
   <View style={{flexDirection:'row',alignItems:'center',gap:space.sm,marginBottom:space.lg}}><Logo size={34}/><Text style={s.brand}>JalSathi</Text></View>
   {menuItems.map(([key,label,icon])=><Pressable key={key} accessibilityRole="menuitem" onPress={()=>go(key)} style={[s.menuItem,page===key&&{backgroundColor:color.sage}]}><Icon name={icon} size={22} tint={page===key?color.green:color.textMuted}/><Text style={[type.heading,{fontWeight:page===key?'700':'500'}]}>{label}</Text></Pressable>)}</View></View>}
 </View>
}
const s=StyleSheet.create({
 root:{flex:1,backgroundColor:color.bg},
 container:{padding:space.lg,paddingTop:44,maxWidth:560,width:'100%',alignSelf:'center',paddingBottom:space.xxl},
 top:{flexDirection:'row',alignItems:'center',gap:space.sm},
 menuBtn:{width:40,height:40,alignItems:'center',justifyContent:'center'},
 brand:{fontSize:24,fontWeight:'800',color:color.greenDark,fontFamily:font,letterSpacing:-.3},
 splashBrand:{fontSize:40,fontWeight:'800',color:color.greenDark,fontFamily:font,letterSpacing:-.8,marginTop:space.md},
 splashTag:{fontSize:15,color:color.text,fontFamily:font,marginTop:space.xs},
 pageDot:{height:6,width:6,borderRadius:3},
 langPill:{flexDirection:'row',alignItems:'center',gap:6,backgroundColor:color.sage,paddingVertical:8,paddingHorizontal:12,borderRadius:radius.pill},
 villageChip:{flexDirection:'row',alignItems:'center',gap:space.sm,alignSelf:'flex-start',maxWidth:'100%',backgroundColor:color.bg,borderWidth:1,borderColor:color.border,borderRadius:radius.pill,paddingVertical:9,paddingHorizontal:14},
 chipBar:{flexDirection:'row',alignItems:'center',gap:space.sm,backgroundColor:color.sage,borderRadius:radius.pill,paddingVertical:10,paddingHorizontal:14,marginBottom:space.sm},
 village:{flexDirection:'row',alignItems:'center',gap:space.md,paddingVertical:space.md,paddingHorizontal:space.sm,borderBottomWidth:1,borderBottomColor:color.border,borderRadius:radius.input},
 farmIcon:{width:48,height:48,borderRadius:radius.input,backgroundColor:color.sage,alignItems:'center',justifyContent:'center'},
 plusBtn:{width:44,height:44,borderRadius:22,backgroundColor:color.green,alignItems:'center',justifyContent:'center'},
 rowIconBig:{width:52,height:52,borderRadius:26,alignItems:'center',justifyContent:'center'},
 bigNumber:{fontSize:28,fontWeight:'800',color:color.text,fontFamily:font,letterSpacing:-.4},
 tile:{flex:1,marginVertical:space.sm},
 avatar:{width:48,height:48,borderRadius:24,backgroundColor:color.sage,alignItems:'center',justifyContent:'center'},
 row:{flexDirection:'row',gap:space.md,alignItems:'center'},
 wrap:{flexDirection:'row',gap:space.sm,flexWrap:'wrap'},
 timeline:{flexDirection:'row',gap:space.md,paddingVertical:space.sm},
 dot:{width:10,height:10,borderRadius:5,backgroundColor:color.green,marginTop:6},
 tHead:{flexDirection:'row',backgroundColor:color.sage,paddingVertical:space.md,paddingHorizontal:space.lg},
 th:{fontSize:13,fontWeight:'700',color:color.greenDark,fontFamily:font},
 tRow:{flexDirection:'row',alignItems:'center',paddingVertical:space.md,paddingHorizontal:space.lg,borderTopWidth:1,borderTopColor:color.border},
 footer:{fontSize:11,lineHeight:18,color:color.textMuted,marginTop:space.xl,textAlign:'center',fontFamily:font},
 navWrap:{borderTopWidth:1,borderTopColor:color.border,backgroundColor:color.bg},
 navInner:{width:'100%',maxWidth:560,alignSelf:'center'},
 backdrop:{...StyleSheet.absoluteFillObject,backgroundColor:'rgba(23,35,29,.4)'},
 drawer:{position:'absolute',left:0,top:0,bottom:0,width:290,maxWidth:'82%',backgroundColor:color.bg,padding:space.lg,paddingTop:52},
 menuItem:{flexDirection:'row',alignItems:'center',gap:space.md,paddingVertical:space.md,paddingHorizontal:space.md,borderRadius:radius.input},
});
