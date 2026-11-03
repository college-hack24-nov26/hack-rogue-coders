import React,{useState} from 'react';

type Horizon={day:number;date?:string;predicted:number;actual:number|null;baseline:number;interval_lower:number;interval_upper:number};
type Sample={station_fingerprint:string;station_name?:string;district:string;issue_date:string;horizons:Horizon[]};

export function PredictionExamples({data,description}:{data?:{samples:Sample[]};description?:string}){
 const [selected,setSelected]=useState(0);
 const samples=data?.samples||[];
 const sample=samples[selected]||samples[0];
 if(!sample)return null;
 const rows=sample.horizons;
 const measured=rows.every(r=>typeof r.actual==='number');
 const values=rows.flatMap(r=>typeof r.actual==='number'?[r.predicted,r.actual,r.baseline]:[r.predicted,r.baseline]);
 const low=Math.min(...values),high=Math.max(...values),span=Math.max(high-low,.05);
 const y=(value:number)=>175-(value-low)/span*140;
 const line=(key:'predicted'|'actual'|'baseline')=>rows.map((r,i)=>`${45+i*37},${y(r[key] as number)}`).join(' ');
 return <section aria-label="Historical prediction examples">
  <h3>{measured?'Predictions compared with measured outcomes':'Experimental daily station predictions'}</h3>
  <p>{description||"Historical evaluation on held-out stations. These dated examples do not represent today's village outlook."}</p>
  <label>Prediction example<select value={selected} onChange={e=>setSelected(Number(e.target.value))}>{samples.map((s,i)=><option key={s.station_fingerprint} value={i}>{s.station_name||'Station '+s.station_fingerprint.slice(0,8)} · district {s.district} · issued {s.issue_date}</option>)}</select></label>
  <p>Issue date: <strong>{sample.issue_date}</strong> · Values in original source signed metres.</p>
  <svg viewBox="0 0 620 220" role="img" aria-label="Fifteen daily predictions compared with actual readings" style={{width:'100%'}}>
   <text x="0" y="30" fontSize="12">{high.toFixed(2)}</text><text x="0" y="180" fontSize="12">{low.toFixed(2)}</text>
   <polyline points={line('baseline')} fill="none" stroke="#a87918" strokeWidth="2" strokeDasharray="5 4"/>
   {measured&&<polyline points={line('actual')} fill="none" stroke="#3676bd" strokeWidth="3"/>}
   <polyline points={line('predicted')} fill="none" stroke="#16834A" strokeWidth="3"/>
   {rows.map((r,i)=><text key={r.day} x={45+i*37} y="205" fontSize="11">{r.day}</text>)}
  </svg>
  <div className="model-legend"><span style={{color:'#16834A'}}>━ Predicted</span>{measured&&<span style={{color:'#3676bd'}}>━ Measured</span>}<span style={{color:'#a87918'}}>┄ Latest-reading baseline</span></div>
  <div style={{overflowX:'auto'}}><table><thead><tr><th>Day / date</th><th>Predicted (m)</th><th>Measured (m)</th><th>Baseline (m)</th><th>90% calibrated interval (m)</th></tr></thead><tbody>{rows.map(r=><tr key={r.day}><td>{r.date||r.day}</td><td>{r.predicted.toFixed(3)}</td><td>{typeof r.actual==='number'?r.actual.toFixed(3):'Not yet observed'}</td><td>{r.baseline.toFixed(3)}</td><td>{r.interval_lower.toFixed(3)} to {r.interval_upper.toFixed(3)}</td></tr>)}</tbody></table></div>
 </section>;
}
