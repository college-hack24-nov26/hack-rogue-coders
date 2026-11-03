"""Run the real research model on real NWIC groundwater data and print sample input/output.

Research demonstration only: the model is unapproved and nothing is published.
Usage: uv run python -m scripts.demo_model [--station NAME] [--issue-date YYYY-MM-DD] [--model seasonal]
"""
import argparse, csv, json, math, hashlib
from collections import defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor
from services.worker.model import predict_levels

FEATURES = ['level_t','level_t_minus_1','level_t_minus_3','level_t_minus_7','level_t_minus_14','level_t_minus_28','trend_7','season_sin','season_cos','latitude','longitude']
LAGS = [0, 1, 3, 7, 14, 28]

def load_daily(path):
    stations, daily = {}, defaultdict(dict)
    with open(path, encoding='utf-8-sig', newline='') as stream:
        for r in csv.DictReader(stream):
            try:
                if r['State LGD Code'] != '27' or r['Agency'] != 'Maharashtra GW':
                    continue
                lat, lon = float(r['Latitude']), float(r['Longitude'])
                level = float(r['Groundwater Level Telemetry 6 Hourly (meter)'])
                when = datetime.strptime(r['Data Acquisition Time'], '%d-%m-%Y %H:%M')
                if not math.isfinite(level):
                    continue
            except (KeyError, ValueError):
                continue
            key = (r['Station'], round(lat, 6), round(lon, 6))
            stations[key] = {'station': r['Station'], 'district': r['District'] if 'District' in r else r.get('District LGD Code'), 'lat': lat, 'lon': lon}
            cur = daily[key].get(when.date())
            if cur is None or when > cur[0]:
                daily[key][when.date()] = (when, level)
    return stations, daily

def features_at(series, meta, day):
    past = [series[day - timedelta(days=d)][1] for d in LAGS]
    angle = 2 * math.pi * day.timetuple().tm_yday / 365.25
    return past + [past[0] - past[3], math.sin(angle), math.cos(angle), meta['lat'], meta['lon']]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='seasonal')
    ap.add_argument('--csv', default='data/raw/nwic-maharashtra-2026.csv')
    ap.add_argument('--station'); ap.add_argument('--issue-date'); ap.add_argument('--count', type=int, default=3)
    args = ap.parse_args()
    root = Path('artifacts') / f'nwic-{args.model}'
    manifest = json.loads((root / 'evaluation.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((root / 'model.json').read_bytes()).hexdigest() == manifest['sha256'], 'artifact hash mismatch'
    model = XGBRegressor(); model.load_model(root / 'model.json')
    stations, daily = load_daily(args.csv)
    print(f"Model: {args.model} | stations in {args.csv}: {len(stations)} | approved={manifest['approved']} (research demo)")
    picks = []
    for key, series in daily.items():
        if args.station and args.station.lower() not in stations[key]['station'].lower():
            continue
        days = sorted(series)
        if args.issue_date:
            cands = [date.fromisoformat(args.issue_date)]
        else:  # latest issue date with a full 28-day history and 15 days of outcomes
            cands = [d for d in reversed(days) if all((d - timedelta(days=l)) in series for l in LAGS) and all((d + timedelta(days=h)) in series for h in range(1, 16))][:1]
        for d in cands:
            if all((d - timedelta(days=l)) in series for l in LAGS) and all((d + timedelta(days=h)) in series for h in range(1, 16)):
                picks.append((key, d))
        if len(picks) >= args.count and not args.station:
            break
    if not picks:
        raise SystemExit('No station/date with complete history and 15-day outcomes found')
    for key, d in picks[:args.count]:
        meta, series = stations[key], daily[key]
        x = features_at(series, meta, d)
        print(f"\n=== Station {meta['station']} (district code/name {meta['district']}) lat {meta['lat']:.4f} lon {meta['lon']:.4f} | issue date {d} ===")
        print('Sample input (issue-time features, metres below ground):')
        for n, v in zip(FEATURES, x):
            print(f'  {n:16s} {v: .4f}')
        pred = predict_levels(model, np.asarray([x], dtype=np.float32), manifest)[0]
        q = manifest['calibration_abs_error_quantile']
        actual = [series[d + timedelta(days=h)][1] for h in range(1, 16)]
        print('\n day  date        predicted   90% interval          actual    persistence  |err|  |persist err|')
        e_m = e_p = 0.0
        for h in range(15):
            e_m += abs(pred[h] - actual[h]); e_p += abs(x[0] - actual[h])
            print(f' {h+1:>3}  {d + timedelta(days=h+1)}  {pred[h]:9.3f}  [{pred[h]-q[h]:8.3f},{pred[h]+q[h]:8.3f}]  {actual[h]:8.3f}  {x[0]:10.3f}  {abs(pred[h]-actual[h]):6.3f}  {abs(x[0]-actual[h]):6.3f}')
        print(f' mean abs error: model {e_m/15:.3f} m vs persistence {e_p/15:.3f} m')

if __name__ == '__main__':
    main()
