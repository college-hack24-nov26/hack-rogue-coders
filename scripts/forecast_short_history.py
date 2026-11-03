"""Train and evaluate a separate short-history research model; publish dated station previews."""
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, timedelta, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from xgboost import XGBRegressor

from scripts.demo_model import load_daily
from scripts.repair_forecast import partitions
from services.api.db import Session, Record
from services.worker.model import evaluate


def transform(x):
    values = np.asarray(x, dtype=np.float32).copy()
    values[:, 1:4] -= values[:, 0, None]
    values[:, 0] = 0
    return values


def main():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    root = Path('artifacts/nwic-short-history')
    root.mkdir(parents=True, exist_ok=True)
    source = json.loads(Path('data/raw/nwic-maharashtra-2026.metadata.json').read_text())
    with np.load('artifacts/nwic-current-run/training_cache.npz', allow_pickle=False) as cache:
        x = cache['X'][:, [0, 1, 2, 3, 6, 7, 8, 9, 10]]
        y, dates, groups, identities = (cache[k] for k in ('Y', 'D', 'G', 'S'))
    masks, held_out = partitions(dates, groups, 2026, True)
    features = transform(x)
    delta = y-x[:, 0, None]
    model = XGBRegressor(objective='reg:absoluteerror', n_estimators=180, max_depth=4,
                         learning_rate=.05, subsample=.85, colsample_bytree=.9,
                         n_jobs=4, random_state=1729, tree_method='hist')
    model.fit(features[masks['train']], delta[masks['train']])
    tuning = model.predict(features[masks['tuning']])
    weights = np.asarray([min((0, .25, .5, .75, 1), key=lambda w:
        float(np.abs(delta[masks['tuning'], h]-tuning[:, h]*w).mean())) for h in range(15)])
    def predict(rows):
        return rows[:, 0, None]+model.predict(transform(rows))*weights
    residuals = np.abs(predict(x[masks['calibration']])-y[masks['calibration']])
    rank = min(len(residuals), math.ceil((len(residuals)+1)*.9))-1
    offsets = np.sort(residuals, axis=0)[rank]
    evaluations, gates = {}, {}
    for name in ('chronological', 'geographic'):
        mask = masks[name]
        predicted = predict(x[mask])
        metrics = evaluate(y[mask], predicted, np.repeat(x[mask, 0, None], 15, axis=1))
        for h in range(15):
            metrics[str(h+1)]['coverage'] = float((np.abs(predicted[:, h]-y[mask, h])<=offsets[h]).mean())
        evaluations[name] = {'samples': int(mask.sum()), 'metrics': metrics}
        gates[name] = all(m['mae']<m['persistence_mae'] and m['coverage']>=.8 for m in metrics.values())
    model.save_model(root/'model.json')
    report = dict(approved=False, purpose='short-history experimental station forecasts',
        trained_feature_names=['level_t','level_t_minus_1','level_t_minus_3','level_t_minus_7','trend_7','season_sin','season_cos','latitude','longitude'],
        model_sha256=hashlib.sha256((root/'model.json').read_bytes()).hexdigest(),
        source=source['source'], source_file_sha256=source['sha256'],
        evaluations=evaluations, gates=gates, residual_weights=weights.tolist(),
        calibration_abs_error_quantile=offsets.tolist(), held_out_districts=held_out,
        training_sample_selection='Existing complete 28-day-history evaluation cache, projected to seven-day features. No missing inputs imputed.',
        limitations=['Separate research model; not operationally approved', 'Previous experiments exposed these holdouts',
                     'No reviewed station-to-village mapping', 'Source sign and publication availability require review'])
    (root/'evaluation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'evaluated_model': 'seven-day history', 'gates': gates}), flush=True)
    # A candidate that fails the existing accuracy/coverage checks is not published even as a current preview.
    if not all(gates.values()):
        print('Current preview withheld: accuracy/coverage checks failed', flush=True)
        return
    stations, daily = load_daily('data/raw/nwic-maharashtra-2026.csv')
    districts = dict(zip(identities, groups))
    current, metadata = [], []
    for key, series in daily.items():
        issue = today-timedelta(days=1)
        required = [issue-timedelta(days=lag) for lag in (0, 1, 3, 7)]
        if not all(day in series for day in required):
            continue
        meta = stations[key]
        fingerprint = hashlib.sha256(f"Maharashtra GW|{key[0]}|{key[1]:.6f}|{key[2]:.6f}".encode()).hexdigest()[:24]
        if fingerprint not in districts:
            continue
        past = [series[day][1] for day in required]
        angle = 2*math.pi*issue.timetuple().tm_yday/365.25
        current.append(past+[past[0]-past[3], math.sin(angle), math.cos(angle), meta['lat'], meta['lon']])
        metadata.append((fingerprint, meta, str(districts[fingerprint]), issue))
    if not current:
        print('No stations have complete required recent inputs', flush=True)
        return
    forecasts = predict(np.asarray(current, dtype=np.float32))
    grouped = defaultdict(list)
    for values, predicted, (fingerprint, meta, district, issue) in zip(current, forecasts, metadata):
        horizons = [dict(day=h+1, date=(issue+timedelta(days=h+1)).isoformat(), predicted=float(p),
                    actual=None, baseline=float(values[0]), interval_lower=float(p-offsets[h]),
                    interval_upper=float(p+offsets[h])) for h, p in enumerate(predicted)]
        grouped['district:'+district].append(dict(station_fingerprint=fingerprint, station_name=meta['station'],
            district=district, issue_date=issue.isoformat(), horizons=horizons))
    with Session() as db:
        for jurisdiction, samples in grouped.items():
            payload = dict(status='experimental_current', operational=False, approved=False,
                forecast_date=today.isoformat(), valid_through=(today+timedelta(days=14)).isoformat(),
                source=source['source'], source_file_sha256=source['sha256'],
                model_sha256=report['model_sha256'], model_history_days=7, evaluations=evaluations,
                units='original_source_signed_meter', limitations=report['limitations'],
                samples=sorted(samples, key=lambda s: s['station_name']))
            row = db.scalar(select(Record).where(Record.kind=='experimental_forecasts', Record.key==jurisdiction))
            if row:
                row.payload=payload
            else:
                db.add(Record(kind='experimental_forecasts', key=jurisdiction, payload=payload))
        db.commit()
    summary = dict(forecast_date=today.isoformat(), stations=len(metadata), districts=len(grouped),
                   satara_stations=len(grouped.get('district:494', [])), gates=gates, operational=False)
    (root/'publication.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
