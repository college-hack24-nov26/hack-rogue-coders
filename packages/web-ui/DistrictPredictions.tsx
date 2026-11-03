import React,{useEffect,useState} from 'react';
import {Api} from '../api-types';
import {PredictionExamples} from './PredictionExamples';

export function DistrictPredictions({api,villageId,days}:{api:Api;villageId:string;days:number}){
 const [result,setResult]=useState<any>(null);
 const [error,setError]=useState('');
 useEffect(()=>{
  let active=true;
  setResult(null);setError('');
  api.request('/admin/villages/'+encodeURIComponent(villageId)+'/research-predictions?days='+days)
   .then(value=>{if(active)setResult(value)})
   .catch(e=>{if(active)setError(e.message)});
  return ()=>{active=false};
 },[api,villageId,days]);
 return <section className="card" aria-label="District station predictions">
  <h3>Station predictions{result?.district_name?' · '+result.district_name:''}</h3>
  {error?<p role="alert" className="error">{error}</p>:!result?<p>Loading station predictions…</p>:!result.samples?.length?<p>{result.reason}</p>:<>
   {result.experimental_current&&<>
    <h3>Today's experimental forecasts · {result.experimental_current.forecast_date}</h3>
    <p>{result.experimental_current.samples.length} stations with complete recent inputs. Predictions extend through {result.experimental_current.valid_through}. Station-to-village mapping and operational model approval remain pending.</p>
    <PredictionExamples key={'current:'+villageId+':'+days} data={result.experimental_current} description="Experimental station forecasts from a separately trained seven-day-history model, using measured inputs through the issue date. Calibrated intervals describe historical evaluation; these are not approved village forecasts."/>
   </>}
   <details><summary>Historical predictions and measured outcomes · {result.samples.length} stations</summary>
   <p>Monitoring stations in the district containing {result.village_name}.</p>
   <PredictionExamples key={villageId+':'+days} data={result} description="Historical research replay using measured station inputs. Some stations were used during model development. These station results are not a current forecast for the selected village."/>
   </details>
  </>}
 </section>;
}
