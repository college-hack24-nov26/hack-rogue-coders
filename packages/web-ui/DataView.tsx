import React from 'react';

const label=(k:string)=>{const t=k.replaceAll('_',' ');return t.charAt(0).toUpperCase()+t.slice(1)};
const isPrimitive=(v:any)=>v===null||['string','number','boolean','undefined'].includes(typeof v);
const isIso=(v:any)=>typeof v==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(v)&&!isNaN(Date.parse(v));
function Scalar({v}:{v:any}){
 if(v===null||v===undefined||v==='')return <span className="dv-null">Not recorded</span>;
 if(typeof v==='boolean')return <span className={'badge '+(v?'good':'neutral')}>{v?'Yes':'No'}</span>;
 if(typeof v==='number')return <>{v.toLocaleString('en-IN')}</>;
 if(isIso(v))return <>{new Date(v).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})}</>;
 const s=String(v);
 if(/^https?:\/\//.test(s))return <a href={s} target="_blank" rel="noreferrer">{s}</a>;
 return <>{s}</>;
}
function Node({value,depth}:{value:any;depth:number}){
 if(isPrimitive(value))return <Scalar v={value}/>;
 if(Array.isArray(value)){
  if(!value.length)return <span className="dv-null">None</span>;
  if(value.every(x=>isPrimitive(x)))return <span className="dv-tags">{value.map((x,i)=><span className="badge" key={i}><Scalar v={x}/></span>)}</span>;
  const flat=value.every(x=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.values(x).every(isPrimitive));
  if(flat){
   const keys=[...new Set(value.flatMap(x=>Object.keys(x)))].slice(0,10);
   return <div className="table-wrap"><table><thead><tr>{keys.map(k=><th key={k}>{label(k)}</th>)}</tr></thead><tbody>{value.map((x,i)=><tr key={i}>{keys.map(k=><td key={k}><Scalar v={x[k]}/></td>)}</tr>)}</tbody></table></div>;
  }
  return <div className="dv-list">{value.map((x,i)=><div className="dv-item" key={i}><Node value={x} depth={depth+1}/></div>)}</div>;
 }
 const entries=Object.entries(value);
 if(!entries.length)return <span className="dv-null">None</span>;
 return <dl className={'dv-grid depth-'+Math.min(depth,2)}>{entries.map(([k,v])=><React.Fragment key={k}><dt>{label(k)}</dt><dd><Node value={v} depth={depth+1}/></dd></React.Fragment>)}</dl>;
}
/** Readable view of an API record. The exact JSON stays one click away. */
export function DataView({value}:{value:any}){
 if(value===null||value===undefined)return <p className="muted">No data loaded yet.</p>;
 return <div className="dataview"><Node value={value} depth={0}/><details className="raw"><summary>Raw data</summary><pre className="evidence">{JSON.stringify(value,null,2)}</pre></details></div>;
}
