import React,{useState,useEffect} from 'react';
import {View,Text,Linking,Image,Platform} from 'react-native';
import * as Crypto from 'expo-crypto';
import {Api} from '../../packages/api-types';
import {color,radius,space,type} from './theme';
import {Button,Card,CardTitle,Field,Muted,Badge,Notice} from './ui';

const box={marginVertical:space.xs} as const;
const readable=(k:string)=>{const t=k.replaceAll('_',' ');return t.charAt(0).toUpperCase()+t.slice(1)};
export function MarketTools({api}:{api:Api}){
 const [filters,setFilters]=useState({market:'',variety:'',quote_date:'',units:''});const [data,setData]=useState<any>(null);const [error,setError]=useState('');const [economics,setEconomics]=useState({yield_kg:'',price_per_kg:'',cultivation_cost:'',transport_cost:'',assumptions:''});const [result,setResult]=useState<any>(null);
 async function run(f:()=>Promise<void>){try{setError('');await f()}catch(e){setError((e as Error).message)}}
 return <View>
  <Card tone="alt"><CardTitle>Market comparison</CardTitle>
   {Object.entries(filters).map(([k,v])=><Field key={k} label={readable(k)} accessibilityLabel={k.replaceAll("_"," ")} value={v} onChange={value=>setFilters({...filters,[k]:value})}/>)}
   <Button title="Apply quote filters" icon="search-outline" onPress={()=>run(async()=>{const query=Object.entries(filters).filter(([,v])=>v).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');setData(await api.request('/markets?'+query))})}/>
   {data&&<><View style={{flexDirection:'row',gap:space.sm,alignItems:'center',marginTop:space.md}}><Badge label={String(data.status)} tone="good"/><Muted>Quotes are not price forecasts</Muted></View>
    {data.quotes.map((r:any)=><Card key={r.id} style={box}><View style={{flexDirection:'row',justifyContent:'space-between',gap:space.md}}><View style={{flex:1}}><Text style={type.heading}>{r.payload.commodity}</Text><Muted>{r.payload.market} · {r.payload.variety}</Muted></View><Text style={{fontSize:18,fontWeight:'800',color:color.greenDark}}>{r.payload.price}</Text></View><Muted>{r.payload.units} · quote date {r.payload.source_date}</Muted><Button title="Official source" variant="secondary" icon="open-outline" onPress={()=>Linking.openURL(r.payload.source)}/></Card>)}</>}
  </Card>
  <Card tone="alt"><CardTitle>Economics scenario</CardTitle>
   {Object.entries(economics).map(([k,v])=><Field key={k} label={readable(k)} accessibilityLabel={k.replaceAll("_"," ")} value={v} onChange={value=>setEconomics({...economics,[k]:value})}/>)}
   <Button title="Calculate assumed margin (INR)" onPress={()=>run(async()=>{if(Object.values(economics).some(v=>!v.trim()))throw Error('Provide all explicit assumptions');setResult(await api.request('/calculations/economics','POST',{...Object.fromEntries(Object.entries(economics).filter(([k])=>k!=='assumptions').map(([k,v])=>[k,Number(v)])),assumptions:economics.assumptions}))})}/>
   {result&&<Card tone="sage" style={box}><Text style={type.heading}>Assumed revenue ₹{result.revenue} · margin ₹{result.margin}. {result.warning}</Text></Card>}
   {error&&<Notice tone="error">{error}</Notice>}
  </Card>
 </View>
}
export function Notices({api,villageId}:{api:Api;villageId:string}){const [items,setItems]=useState<any[]>([]);useEffect(()=>{if(villageId)api.request('/notices?village_id='+encodeURIComponent(villageId)).then(setItems).catch(()=>setItems([]))},[api,villageId]);return <View>{items.map(n=><Card key={n.id} tone="alt" style={box}><Text style={type.heading}>{n.title}</Text><Text style={[type.body,{marginTop:space.xs}]}>{n.passage}</Text><Muted style={{marginTop:space.sm}}>{n.applicability_note} · {n.source_date} · valid until {n.valid_until}</Muted><Button title="Read official notice source" variant="secondary" icon="open-outline" onPress={()=>Linking.openURL(n.source)}/></Card>)}</View>}
export async function uploadPhoto(api:Api,complaintId:string,uri:string){
 const blob=await(await fetch(uri)).blob();const bytes=await blob.arrayBuffer();const digest=await Crypto.digest(Crypto.CryptoDigestAlgorithm.SHA256,new Uint8Array(bytes));const sha256=Array.from(new Uint8Array(digest)).map(v=>v.toString(16).padStart(2,'0')).join('');
 const type=blob.type==='image/png'?'image/png':'image/jpeg';const pending=await api.request('/uploads/presign','POST',{complaint_id:complaintId,size:blob.size,sha256,content_type:type});
 const upload=pending.upload;const url=upload.url.startsWith('/')?api.base+upload.url:upload.url;
 const response=await fetch(url,{method:upload.method,headers:{...upload.headers,...(upload.authenticated?{Authorization:'Bearer '+api.token}:{})},body:blob});if(!response.ok)throw Error('Photo upload failed; the complaint ticket is saved. Retry the photo separately.');
 return api.request('/uploads/'+pending.attachment_id+'/finalize','POST');
}
export function Attachments({api,complaintId,photo}:{api:Api;complaintId:string;photo?:string|null}){
 const [list,setList]=useState<any[]>([]);const [error,setError]=useState('');const [uri,setUri]=useState('');
 const refresh=()=>api.request('/complaints/'+complaintId+'/attachments').then(setList).catch(e=>setError(e.message));useEffect(()=>{refresh()},[complaintId]);
 return <Card tone="alt" style={box}><Text style={type.heading}>Private report photos</Text>{photo&&<Button title="Upload & inspect selected photo" icon="cloud-upload-outline" onPress={async()=>{try{await uploadPhoto(api,complaintId,photo);await refresh()}catch(e){setError((e as Error).message)}}}/>}{list.map(a=><View key={a.id} style={{marginTop:space.sm}}><View style={{flexDirection:'row',gap:space.sm,alignItems:'center',flexWrap:'wrap'}}><Badge label={String(a.inspection)} tone="neutral"/><Badge label={a.approved_for_officials?'Approved for officials':'Private until reviewed'} tone={a.approved_for_officials?'good':'warn'}/></View><Button title="View inspected photo" variant="secondary" icon="image-outline" onPress={async()=>{const path=api.base+'/api/v1/attachments/'+a.id+'/content';if(Platform.OS==='web'){try{const r=await fetch(path,{headers:{Authorization:'Bearer '+api.token}});if(!r.ok)throw Error('Photo unavailable');setUri(URL.createObjectURL(await r.blob()))}catch(e){setError((e as Error).message)}}else setUri(path)}}/></View>)}{uri&&<Image source={{uri,headers:{Authorization:'Bearer '+api.token}}} style={{height:200,width:'100%',borderRadius:radius.input,marginTop:space.sm}}/>}{error&&<Notice tone="error">{error}</Notice>}</Card>
}
