"""Evaluate a persistence-anchored research candidate without weakening release gates.

Hyperparameters and shrinkage use a separate purged tuning partition. Calibration
and final holdouts are untouched by selection. This is a follow-up experiment to
the already inspected absolute-level model, not a new prospective trial.
"""
import argparse
import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from xgboost import XGBRegressor
from services.worker.model import evaluate, model_inputs, predict_levels
from scripts.train_groundwater import FEATURES


def prepare(sources, cache):
    source_files=[dict(file=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest()) for source in sources]
    digest = hashlib.sha256(json.dumps(source_files,sort_keys=True).encode()).hexdigest()
    meta = cache.with_suffix('.json')
    if cache.exists() and meta.exists() and json.loads(meta.read_text())['sha256'] == digest:
        z = np.load(cache, allow_pickle=False)
        return {key:z[key] for key in z.files}, json.loads(meta.read_text())
    daily = defaultdict(dict)
    stations = {}
    rows = rejected = 0
    for source in sources:
        with source.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                rows += 1
                try:
                    lat, lon = float(row['Latitude']), float(row['Longitude'])
                    level = float(row['Groundwater Level Telemetry 6 Hourly (meter)'])
                    if row['State LGD Code'] != '27' or row['Agency'] != 'Maharashtra GW' or not math.isfinite(level) or not (15 <= lat <= 23 and 72 <= lon <= 81):
                        raise ValueError('Invalid source observation')
                    when = datetime.strptime(row['Data Acquisition Time'], '%d-%m-%Y %H:%M')
                    key = hashlib.sha256(f"{row['Agency']}|{row['Station']}|{lat:.6f}|{lon:.6f}".encode()).hexdigest()[:24]
                    stations[key] = (row['District LGD Code'], lat, lon)
                    old = daily[key].get(when.date())
                    if old is None or when > old[0]:
                        daily[key][when.date()] = (when, level)
                except (KeyError, ValueError):
                    rejected += 1
        print(json.dumps({'prepared_source':str(source),'observations_so_far':rows}),flush=True)
    features, targets, dates, groups, identities = [], [], [], [], []
    for key, series in daily.items():
        group, lat, lon = stations[key]
        for day in sorted(series):
            lags = [day-timedelta(days=n) for n in (0,1,3,7,14,28)]
            future = [day+timedelta(days=n) for n in range(1,16)]
            if not all(d in series for d in lags+future):
                continue
            past = [series[d][1] for d in lags]
            angle = 2*math.pi*day.timetuple().tm_yday/365.25
            features.append(past+[past[0]-past[3],math.sin(angle),math.cos(angle),lat,lon])
            targets.append([series[d][1] for d in future])
            dates.append(day.toordinal());groups.append(group);identities.append(key)
    arrays = dict(X=np.array(features,dtype=np.float32),Y=np.array(targets,dtype=np.float32),D=np.array(dates),G=np.array(groups),S=np.array(identities))
    metadata = dict(sha256=digest,source_files=source_files,rows_read=rows,rejected_rows=rejected,stations=len(stations))
    cache.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(cache,**arrays);meta.write_text(json.dumps(metadata,indent=2))
    return arrays, metadata


def partitions(dates, groups, year_holdout=None, full_year_calibration=False):
    unique = np.unique(dates)
    a,b,c = [unique[int(len(unique)*fraction)] for fraction in (.50,.65,.80)]
    if year_holdout:
        a=date(year_holdout-(2 if full_year_calibration else 1),1,1).toordinal()
        b=date(year_holdout-1,1 if full_year_calibration else 7,1).toordinal()
        c=date(year_holdout,1,1).toordinal()
    held_out = sorted(set(groups))[::4]
    geographic = np.isin(groups,held_out)
    masks = dict(train=(dates<a-15)&~geographic,
                 tuning=(dates>=a)&(dates<b-15)&~geographic,
                 calibration=(dates>=b)&(dates<c-15)&~geographic,
                 chronological=(dates>=c)&~geographic,
                 geographic=(dates>=c)&geographic)
    if min(int(mask.sum()) for mask in masks.values()) < 20:
        raise ValueError('Insufficient independent purged partitions')
    return masks, held_out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('csv',type=Path)
    parser.add_argument('--history',type=Path)
    parser.add_argument('--year-holdout',type=int)
    parser.add_argument('--full-year-calibration',action='store_true')
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--output',type=Path,default=Path('artifacts/nwic-residual'))
    parser.add_argument('--report',type=Path,default=Path('docs/RESIDUAL_MODEL_EVALUATION.json'))
    args=parser.parse_args();started=time.perf_counter()
    args.output.mkdir(parents=True,exist_ok=True)
    data,metadata=prepare(([args.history] if args.history else [])+[args.csv],args.cache or args.output/'training_cache.npz')
    X,Y,D,G=data['X'],data['Y'],data['D'],data['G']
    if args.full_year_calibration and not args.year_holdout:parser.error('--full-year-calibration requires --year-holdout')
    masks,held_out=partitions(D,G,args.year_holdout,args.full_year_calibration)
    manifest=dict(feature_names=FEATURES,input_transform='relative_lags_v1',prediction_transform='delta_from_latest_v1')
    transformed=model_inputs(X,manifest)
    delta=Y-X[:,0,None]
    candidates=[];best=None;fit_started=time.perf_counter()
    for objective,trees,depth in [('reg:absoluteerror',100,3),('reg:absoluteerror',180,4),('reg:pseudohubererror',100,3)]:
        model=XGBRegressor(objective=objective,n_estimators=trees,max_depth=depth,learning_rate=.05,subsample=.85,colsample_bytree=.9,n_jobs=4,random_state=1729,tree_method='hist')
        model.fit(transformed[masks['train']],delta[masks['train']])
        residual=model.predict(transformed[masks['tuning']])
        actual=delta[masks['tuning']]
        weights=[]
        for h in range(15):
            weights.append(min((0,.25,.5,.75,1),key=lambda w:float(np.abs(actual[:,h]-residual[:,h]*w).mean())))
        score=float(np.abs(actual-residual*np.asarray(weights)).mean())
        config=dict(objective=objective,n_estimators=trees,max_depth=depth,residual_weights=weights,tuning_mae=score)
        candidates.append(config);print(json.dumps({'candidate':config}),flush=True)
        if best is None or score<best[0]:best=(score,model,config)
    _,model,config=best;manifest['residual_weights']=config['residual_weights']
    # Split conformal calibration; finite-sample rank, never holdout residuals.
    errors=np.abs(predict_levels(model,X[masks['calibration']],manifest)-Y[masks['calibration']])
    rank=min(len(errors),math.ceil((len(errors)+1)*.9))-1
    offsets=np.sort(errors,axis=0)[rank]
    evaluations={}
    for name in ('chronological','geographic'):
        mask=masks[name];predicted=predict_levels(model,X[mask],manifest)
        metrics=evaluate(Y[mask],predicted,np.repeat(X[mask,0,None],15,axis=1))
        for h in range(15):
            m=metrics[str(h+1)]
            m.update(coverage=float((np.abs(Y[mask,h]-predicted[:,h])<=offsets[h]).mean()),interval_width=float(2*offsets[h]),persistence_skill=1-m['mae']/m['persistence_mae'] if m['persistence_mae'] else None)
        evaluations[name]=dict(samples=int(mask.sum()),metrics=metrics)
    artifact=args.output/'model.json';model.save_model(artifact)
    gates={name:all(m['persistence_mae']>0 and m['mae']<m['persistence_mae'] and m['coverage']>=.8 for m in run['metrics'].values()) for name,run in evaluations.items()}
    report=dict(manifest,**{k:v for k,v in metadata.items() if k!='sha256'},approved=False,purpose='research_evaluation_only',
        source='https://nwdp.nwic.gov.in/dataset/ground-water-level-telemetry-daily-maharashtra-gw',
        source_file_sha256=metadata['source_files'][0]['sha256'] if len(metadata['source_files'])==1 else None,sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),artifact=str(artifact),
        horizons=list(range(1,16)),issue_time_features=True,availability_verified=False,source_sign_verified=False,
        geographic_holdout=held_out,purge_days=15,units='original_source_signed_meter',
        daily_aggregation='Last recorded six-hourly value at end of Asia/Kolkata day; no labels filled',
        samples=len(X),training_samples=int(masks['train'].sum()),calibration_samples=int(masks['calibration'].sum()),
        training_period=[date.fromordinal(int(D[masks['train']].min())).isoformat(),date.fromordinal(int(D[masks['train']].max())).isoformat()],
        evaluation_start=date.fromordinal(int(D[masks['chronological']].min())).isoformat(),
        partitions={name:dict(samples=int(mask.sum()),start=date.fromordinal(int(D[mask].min())).isoformat(),end=date.fromordinal(int(D[mask].max())).isoformat()) for name,mask in masks.items()},
        selection=dict(method='Minimum MAE on separate tuning dates only; no refit on calibration or test',candidates=candidates,selected=config,full_year_calibration=args.full_year_calibration,prior_holdout_exposure='Earlier experiments inspected these dates/districts. Full-year calibration was investigated after observing undercoverage in the first multi-year experiment. A new prospective evaluation is required before operational release.'),
        evaluations=evaluations,metrics=evaluations['geographic']['metrics'],gates=gates,
        calibration_abs_error_quantile=offsets.tolist(),uncertainty_target=.9,
        release_blockers=['Source sign convention requires authoritative review','Historical source publication availability is not supplied','Derived station identity requires reviewed source crosswalk','No reviewed village/aquifer mappings','Fresh prospective evaluation and human release review required']+[name+' failed persistence/coverage gates' for name,passed in gates.items() if not passed],
        feature_seconds=fit_started-started,selection_and_evaluation_seconds=time.perf_counter()-fit_started,total_seconds=time.perf_counter()-started,shortage_event_metrics=None)
    (args.output/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'gates':gates,'day_15':{k:v['metrics']['15'] for k,v in evaluations.items()},'total_seconds':report['total_seconds']},indent=2),flush=True)

if __name__=='__main__':main()
