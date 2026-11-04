export type ReviewStatus='submitted'|'awaiting_location'|'needs_information'|'accepted'|'rejected'|'duplicate'|'withdrawn';
export interface Profile {id:string;email:string;role:'farmer'|'admin'|'official'|'system_admin';jurisdictions:string[];preferences:Record<string,unknown>}
export interface Village {id:string;name:string;district:string;taluka:string;jurisdiction:string;provenance:Record<string,unknown>}
export interface Complaint {id:string;description:string;original?:string;village_id:string|null;category:string;channel?:string;location?:{village:string;taluka:string;district:string}|null;gps?:{latitude:number;longitude:number}|null;review_status:ReviewStatus;service_status:string;jurisdiction:string|null;version:number;created_at:string;timeline:{kind:string;note:string;created_at:string}[]}
export class ApiError extends Error {
  constructor(public status:number,message:string,public fields:Record<string,string>={}){super(message);this.name='ApiError'}
}
function responseError(status:number,data:any):ApiError{
  const issues=Array.isArray(data?.errors)?data.errors:Array.isArray(data?.detail)?data.detail:[];
  const fields:Record<string,string>={};
  for(const issue of issues){
    const field=typeof issue.field==='string'?issue.field:Array.isArray(issue.loc)?issue.loc.filter((v:unknown)=>!['body','query','path'].includes(String(v))).join('.'):'request';
    const message=String(issue.message||issue.msg||'Check this field.').replace(/^Value error, /,'');
    if(!fields[field])fields[field]=message;
  }
  const message=Object.keys(fields).length?Object.entries(fields).map(([field,text])=>`${field.replaceAll('_',' ')}: ${text}`).join(' '):typeof data?.detail==='string'?data.detail:status>=500?'JalSathi is temporarily unavailable. Please try again.':'The request could not be completed. Please try again.';
  return new ApiError(status,message,fields);
}
async function sendRequest(url:string,options:RequestInit):Promise<Response>{
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),25000);
  try{return await fetch(url,{...options,signal:controller.signal})}
  catch{throw new ApiError(0,'Could not connect to JalSathi. Check your connection and try again.')}
  finally{clearTimeout(timeout)}
}
export class Api {
  constructor(public base:string,public token='',public refreshToken='',public onSession?:(token:string,refresh:string)=>void){}
  async request<T=any>(path:string,method='GET',body?:unknown,idempotency?:string):Promise<T>{
    const send=()=>sendRequest(this.base.replace(/\/$/,'')+'/api/v1'+path,{method,headers:{'Content-Type':'application/json',...(this.token?{Authorization:'Bearer '+this.token}:{}),...(idempotency?{'Idempotency-Key':idempotency}:{})},body:body===undefined?undefined:JSON.stringify(body)});
    let response=await send();
    if(response.status===401&&this.refreshToken&&!path.startsWith('/auth/')){
      const refreshed=await fetch(this.base+'/api/v1/auth/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh_token:this.refreshToken})});
      if(refreshed.ok){const next=await refreshed.json();this.token=next.access_token;this.refreshToken=next.refresh_token;this.onSession?.(this.token,this.refreshToken);response=await send()}
    }
    const data=await response.json().catch(()=>null);if(!response.ok)throw responseError(response.status,data);if(data===null)throw new ApiError(response.status,'JalSathi returned an unreadable response. Please try again.');return data;
  }
}
