"""Train a research-only 15-horizon model from the real NWIC six-hourly CSV.

No weather archive is invented: features are past measured source levels and calendar/geography.
An artifact is never auto-approved. Unknown publication latency/sign semantics remain release blockers.
"""
import argparse,csv,hashlib,json,math,time
from collections import defaultdict
from datetime import datetime,date,timedelta
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor
from services.worker.model import evaluate

FEATURES=['level_t','level_t_minus_1','level_t_minus_3','level_t_minus_7','level_t_minus_14','level_t_minus_28','trend_7','season_sin','season_cos','latitude','longitude']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('csv');parser.add_argument('--output',default='artifacts/nwic-research');args=parser.parse_args()
    started=time.perf_counter();stations={};daily=defaultdict(dict);row_count=0;rejected=0
    with open(args.csv,encoding='utf-8-sig',newline='') as stream:
        for r in csv.DictReader(stream):
            row_count+=1
            try:
                if r['State LGD Code']!='27' or r['Agency']!='Maharashtra GW':raise ValueError('Wrong agency/state')
                lat,lon=float(r['Latitude']),float(r['Longitude']);level=float(r['Groundwater Level Telemetry 6 Hourly (meter)'])
                when=datetime.strptime(r['Data Acquisition Time'],'%d-%m-%Y %H:%M')
                if not math.isfinite(level) or not (15<=lat<=23 and 72<=lon<=81):raise ValueError('Invalid source value/coordinates')
                key=hashlib.sha256(f"{r['Agency']}|{r['Station']}|{lat:.6f}|{lon:.6f}".encode()).hexdigest()[:24]
                stations[key]={'source_station_name':r['Station'],'derived_station_id':key,'district':r['District LGD Code'],'latitude':lat,'longitude':lon,'identity_method':'agency + source station name + exact coordinate fingerprint; not provider stable ID'}
                existing=daily[key].get(when.date())
                if existing is None or when>existing[0]:daily[key][when.date()]=(when,level)
            except (KeyError,ValueError):rejected+=1
    x=[];y=[];dates=[];districts=[];station_ids=[];lags=[0,1,3,7,14,28]
    for key,series in daily.items():
        meta=stations[key]
        for day in sorted(series):
            needed=[day-timedelta(days=d) for d in lags]+[day+timedelta(days=d) for d in range(1,16)]
            if not all(d in series for d in needed):continue
            past=[series[day-timedelta(days=d)][1] for d in lags]
            angle=2*math.pi*day.timetuple().tm_yday/365.25
            x.append(past+[past[0]-past[3],math.sin(angle),math.cos(angle),meta['latitude'],meta['longitude']]);y.append([series[day+timedelta(days=d)][1] for d in range(1,16)]);dates.append(day.toordinal());districts.append(meta['district']);station_ids.append(key)
    if len(x)<500:raise ValueError('Insufficient complete daily sequences; no missing labels are filled')
    X=np.asarray(x,dtype=np.float32);Y=np.asarray(y,dtype=np.float32);D=np.asarray(dates);G=np.asarray(districts)
    unique_dates=np.unique(D);split1=unique_dates[int(len(unique_dates)*.60)];split2=unique_dates[int(len(unique_dates)*.80)]
    unique_groups=sorted(set(districts));held_out=set(unique_groups[::4]);geo=np.isin(G,list(held_out))
    train=(D<split1-15)&~geo;calibration=(D>=split1)&(D<split2-15)&~geo;temporal=(D>=split2)&~geo;geographic=(D>=split2)&geo
    if min(map(np.count_nonzero,[train,calibration,temporal,geographic]))<20:raise ValueError('Insufficient purged geographic/temporal partitions')
    model=XGBRegressor(n_estimators=90,max_depth=4,learning_rate=.07,subsample=.85,colsample_bytree=.9,n_jobs=4,random_state=1729,objective='reg:squarederror')
    fit_start=time.perf_counter();model.fit(X[train],Y[train]);fit_seconds=time.perf_counter()-fit_start
    calibration_errors=np.abs(model.predict(X[calibration])-Y[calibration]);q=np.quantile(calibration_errors,.9,axis=0)
    evaluations={}
    for name,mask in [('chronological',temporal),('geographic',geographic)]:
        predicted=model.predict(X[mask]);persistence=np.repeat(X[mask,0,None],15,axis=1);metrics=evaluate(Y[mask],predicted,persistence)
        for h in range(15):metrics[str(h+1)].update(coverage=float((np.abs(predicted[:,h]-Y[mask,h])<=q[h]).mean()),interval_width=float(2*q[h]),persistence_skill=1-metrics[str(h+1)]['mae']/metrics[str(h+1)]['persistence_mae'] if metrics[str(h+1)]['persistence_mae'] else None)
        evaluations[name]={'samples':int(mask.sum()),'metrics':metrics}
    folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True);artifact=folder/'model.json';model.save_model(artifact)
    np.savez_compressed(folder/'benchmark_features.npz',X=X,issue_dates=D)
    gates={name:all(m['persistence_mae']>0 and m['mae']<m['persistence_mae'] and m['coverage']>=.8 for m in run['metrics'].values()) for name,run in evaluations.items()}
    report={'approved':False,'purpose':'research_evaluation_only','source':'https://nwdp.nwic.gov.in/dataset/ground-water-level-telemetry-daily-maharashtra-gw','source_file_sha256':hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),'artifact':str(artifact),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'feature_names':FEATURES,'horizons':list(range(1,16)),'issue_time_features':True,'availability_verified':False,'geographic_holdout':sorted(held_out),'purge_days':15,'source_sign_verified':False,'units':'original_source_signed_meter','daily_aggregation':'last available six-hourly measurement per Asia/Kolkata date; incomplete calendar sequences excluded','rows_read':row_count,'rejected_rows':rejected,'stations':len(stations),'samples':len(X),'training_samples':int(train.sum()),'calibration_samples':int(calibration.sum()),'training_period':[date.fromordinal(int(D[train].min())).isoformat(),date.fromordinal(int(D[train].max())).isoformat()],'evaluation_start':date.fromordinal(int(split2)).isoformat(),'evaluations':evaluations,'metrics':evaluations['geographic']['metrics'],'uncertainty_target':.9,'calibration_abs_error_quantile':q.tolist(),'gates':gates,'release_blockers':['Source sign convention requires authoritative review','Historical source publication availability is not supplied','Derived station identity requires reviewed source crosswalk','No reviewed village/aquifer mappings','Human model release review required']+[name+' failed persistence/coverage gates' for name,passed in gates.items() if not passed],'download_seconds':None,'feature_seconds':fit_start-started,'fit_seconds':fit_seconds,'total_seconds':time.perf_counter()-started,'shortage_event_metrics':None}
    (folder/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');Path('docs/REAL_MODEL_EVALUATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['rows_read','stations','samples','training_samples','gates','release_blockers','feature_seconds','fit_seconds','total_seconds']},indent=2))
if __name__=='__main__':main()
