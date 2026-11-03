"""Publish dated station research replays, separate from operational village forecasts."""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import select
from xgboost import XGBRegressor

from services.api.db import Session, Record, Village
from services.worker.model import predict_levels


def main():
    root = Path('artifacts/nwic-current-run')
    manifest = json.loads((root / 'evaluation.json').read_text())
    if hashlib.sha256((root / 'model.json').read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Model hash mismatch')
    with np.load(root / 'training_cache.npz', allow_pickle=False) as cache:
        data = {key: cache[key] for key in ('X', 'Y', 'D', 'G', 'S')}
    latest = {}
    for i, station in enumerate(data['S']):
        if station not in latest or data['D'][i] > data['D'][latest[station]]:
            latest[str(station)] = i
    names = {}
    with Path('data/raw/nwic-maharashtra-2026.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            try:
                lat, lon = float(row['Latitude']), float(row['Longitude'])
                key = hashlib.sha256(f"{row['Agency']}|{row['Station']}|{lat:.6f}|{lon:.6f}".encode()).hexdigest()[:24]
                if key in latest:
                    names[key] = row['Station']
            except (KeyError, ValueError):
                continue
    indices = [latest[key] for key in sorted(latest)]
    model = XGBRegressor(n_jobs=4)
    model.load_model(root / 'model.json')
    predictions = predict_levels(model, data['X'][indices], manifest)
    grouped = defaultdict(list)
    for i, predicted in zip(indices, predictions):
        issue = date.fromordinal(int(data['D'][i]))
        station = str(data['S'][i])
        baseline = float(data['X'][i, 0])
        horizons = []
        for h, (p, actual, offset) in enumerate(zip(predicted, data['Y'][i], manifest['calibration_abs_error_quantile']), 1):
            horizons.append(dict(day=h, date=(issue+timedelta(days=h)).isoformat(), predicted=float(p),
                                 actual=float(actual), baseline=baseline,
                                 interval_lower=float(p-offset), interval_upper=float(p+offset)))
        grouped['district:'+str(data['G'][i])].append(dict(station_fingerprint=station,
            station_name=names.get(station, station), district=str(data['G'][i]), issue_date=issue.isoformat(),
            horizons=horizons))
    with Session() as db:
        districts = set(db.scalars(select(Village.jurisdiction).distinct()))
        for jurisdiction, samples in grouped.items():
            if jurisdiction not in districts:
                raise ValueError('Station district absent from imported geography')
            payload = dict(status='historical_research', operational=False, approved=False,
                resolution='district_station_examples_not_village_predictions', model_sha256=manifest['sha256'],
                source=manifest['source'], units=manifest['units'],
                limitations='Historical replay; some stations were used in development. No verified station-to-village mapping. Source sign interpretation and model release review remain open.',
                samples=sorted(samples, key=lambda s: (-date.fromisoformat(s['issue_date']).toordinal(), s['station_name'], s['station_fingerprint'])))
            old = db.scalar(select(Record).where(Record.kind=='research_predictions', Record.key==jurisdiction))
            if old:
                old.payload = payload
            else:
                db.add(Record(kind='research_predictions', key=jurisdiction, payload=payload))
        db.commit()
    summary = dict(stations=len(indices), districts=len(grouped), operational=False,
                   latest_issue_date=date.fromordinal(int(data['D'][indices].max())).isoformat())
    (root / 'research-publication.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
