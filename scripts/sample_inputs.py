"""Export real-data sample inputs for model testing, and run the model on a sample file.

  uv run python -m scripts.sample_inputs export   # writes docs/MODEL_SAMPLE_INPUTS.json from real NWIC rows
  uv run python -m scripts.sample_inputs run      # predicts 15 days for every sample in that file
Research use only. The model is unapproved; nothing is published.
"""
import json, sys, hashlib
from datetime import date, timedelta
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor
from scripts.demo_model import load_daily, features_at, FEATURES, LAGS
from services.worker.model import predict_levels

OUT = Path('docs/MODEL_SAMPLE_INPUTS.json')
ROOT = Path('artifacts/nwic-seasonal')

def export():
    stations, daily = load_daily('data/raw/nwic-maharashtra-2026.csv')
    issue = date(2026, 2, 15)
    rows = []
    for key, s in sorted(daily.items(), key=lambda kv: stations[kv[0]]['station']):
        if not (all((issue - timedelta(days=l)) in s for l in LAGS) and all((issue + timedelta(days=h)) in s for h in range(1, 16))):
            continue
        x = features_at(s, stations[key], issue)
        y = [s[issue + timedelta(days=h)][1] for h in range(1, 16)]
        if max(y) - min(y) > 2 or abs(x[0] - x[3]) > 2:  # skip visibly noisy sensors for a clean demo
            continue
        rows.append({'station': stations[key]['station'], 'district': stations[key]['district'], 'issue_date': issue.isoformat(), 'values': [round(v, 6) for v in x], 'actual_next_15_days': y})
        if len(rows) == 5:
            break
    OUT.write_text(json.dumps({'source': 'NWIC Maharashtra GW telemetry (real rows), units: metres, negative = below ground', 'feature_names': FEATURES, 'samples': rows}, indent=2), encoding='utf-8')
    print(f'wrote {OUT} with {len(rows)} real samples')

def run():
    data = json.loads(OUT.read_text(encoding='utf-8'))
    man = json.loads((ROOT / 'evaluation.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ROOT / 'model.json').read_bytes()).hexdigest() == man['sha256']
    assert data['feature_names'] == man['feature_names'], 'feature order mismatch'
    model = XGBRegressor(); model.load_model(ROOT / 'model.json')
    X = np.asarray([s['values'] for s in data['samples']], dtype=np.float32)
    pred = predict_levels(model, X, man)
    for s, p in zip(data['samples'], pred):
        a = np.asarray(s.get('actual_next_15_days', []))
        line = f"{s['station']:<22} latest {s['values'][0]:8.3f} | day1 {p[0]:8.3f} day7 {p[6]:8.3f} day15 {p[14]:8.3f}"
        if len(a):
            line += f" | MAE model {np.abs(p - a).mean():.3f} vs persistence {np.abs(s['values'][0] - a).mean():.3f}"
        print(line)

if __name__ == '__main__':
    {'export': export, 'run': run}[sys.argv[1] if len(sys.argv) > 1 else 'run']()
