"""Unit and artifact tests for services.worker.model (gated XGBoost inference)."""
import copy, hashlib, json
from datetime import date
from pathlib import Path
import numpy as np
import pytest
from xgboost import XGBRegressor
from services.worker.model import ApprovedModel, evaluate, model_inputs, predict_levels, release_gate

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts'
NAMES = ['level_t','level_t_minus_1','level_t_minus_3','level_t_minus_7','level_t_minus_14','level_t_minus_28','trend_7','season_sin','season_cos','latitude','longitude']

def good_manifest():
    metrics = {str(h): {'mae': 1.0, 'rmse': 1.5, 'persistence_mae': 2.0, 'coverage': .9, 'interval_width': 3.0} for h in range(1, 16)}
    ev = {k: {'metrics': {str(h): {'mae': 1.0, 'persistence_mae': 2.0, 'coverage': .9} for h in range(1, 16)}} for k in ('chronological', 'geographic')}
    return {'approved': True, 'release_blockers': [], 'horizons': list(range(1, 16)), 'issue_time_features': True, 'geographic_holdout': ['A'],
            'purge_days': 15, 'availability_verified': True, 'source_sign_verified': True, 'calibration_abs_error_quantile': [1.0] * 15,
            'metrics': metrics, 'evaluations': ev, 'feature_names': NAMES}

# ---- release gate ----
def test_release_gate_accepts_complete_manifest():
    assert release_gate(good_manifest()) is True

@pytest.mark.parametrize('mutate', [
    lambda m: m.update(approved=False),
    lambda m: m.update(release_blockers=['x']),
    lambda m: m.update(horizons=list(range(1, 15))),
    lambda m: m.update(issue_time_features=False),
    lambda m: m.update(geographic_holdout=[]),
    lambda m: m.update(purge_days=3),
    lambda m: m.update(availability_verified=False),
    lambda m: m.update(source_sign_verified=False),
    lambda m: m.update(calibration_abs_error_quantile=[1.0] * 14),
    lambda m: m.update(calibration_abs_error_quantile=[float('nan')] * 15),
    lambda m: m['metrics']['3'].update(mae=2.5),
    lambda m: m['metrics']['3'].update(coverage=.5),
    lambda m: m['metrics']['3'].pop('rmse'),
    lambda m: m['metrics']['3'].update(persistence_mae=0),
    lambda m: m['evaluations'].pop('geographic'),
    lambda m: m['evaluations']['chronological']['metrics']['7'].update(mae=9),
    lambda m: m['evaluations']['geographic']['metrics']['7'].update(coverage=.1),
])
def test_release_gate_rejects(mutate):
    m = good_manifest(); mutate(m)
    with pytest.raises(ValueError):
        release_gate(m)

# ---- transforms ----
def row(level=10.0):
    return [level, level + 1, level + 2, level + 3, level + 4, level + 5, -3.0, 0.1, 0.9, 19.0, 75.0]

def test_relative_lag_transform_is_shift_invariant():
    man = {'input_transform': 'relative_lags_v1', 'feature_names': NAMES}
    a = model_inputs([row(5.0)], man); b = model_inputs([row(50.0)], man)
    np.testing.assert_allclose(a[:, 1:6], b[:, 1:6]); assert (a[:, 0] == 0).all()
    assert a.dtype == np.float32

def test_model_inputs_does_not_mutate_caller_data():
    data = np.array([row()], dtype=np.float32); before = data.copy()
    model_inputs(data, {'input_transform': 'relative_lags_v1', 'feature_names': NAMES})
    np.testing.assert_array_equal(data, before)

def test_model_inputs_rejects_bad_input():
    man = {'input_transform': 'relative_lags_v1', 'feature_names': NAMES}
    with pytest.raises(ValueError): model_inputs([row()[:-1] + [float('nan')]], man)
    with pytest.raises(ValueError): model_inputs([1.0, 2.0], man)
    with pytest.raises(ValueError): model_inputs([row()], {'input_transform': 'relative_lags_v1', 'feature_names': NAMES[::-1]})
    with pytest.raises(ValueError): model_inputs([row()], {'input_transform': 'bogus'})

class Stub:
    def __init__(self, value): self.value = value
    def predict(self, x): return np.full((len(x), 15), self.value, dtype=float)

def test_delta_transform_applies_weights_to_latest_level():
    man = {'prediction_transform': 'delta_from_latest_v1', 'residual_weights': [.5] * 15}
    out = predict_levels(Stub(2.0), [row(10.0)], man)
    np.testing.assert_allclose(out, 11.0)

@pytest.mark.parametrize('weights', [[.5] * 14, [1.5] * 15, [-.1] * 15, [float('nan')] * 15, []])
def test_delta_transform_rejects_bad_weights(weights):
    with pytest.raises(ValueError):
        predict_levels(Stub(1.0), [row()], {'prediction_transform': 'delta_from_latest_v1', 'residual_weights': weights})

def test_unknown_prediction_transform_and_bad_shape_rejected():
    with pytest.raises(ValueError): predict_levels(Stub(1.0), [row()], {'prediction_transform': 'nope'})
    class Wrong:
        def predict(self, x): return np.zeros((len(x), 14))
    with pytest.raises(ValueError): predict_levels(Wrong(), [row()], {})
    with pytest.raises(ValueError): predict_levels(Stub(float('inf')), [row()], {})

# ---- evaluate ----
def test_evaluate_computes_metrics():
    a = np.zeros((4, 15)); p = np.ones((4, 15)); b = np.full((4, 15), 2.0)
    m = evaluate(a, p, b)
    assert set(m) == {str(h) for h in range(1, 16)}
    assert m['1'] == {'mae': 1.0, 'rmse': 1.0, 'persistence_mae': 2.0}

def test_evaluate_rejects_bad_shapes_and_nan():
    ok = np.zeros((3, 15))
    with pytest.raises(ValueError): evaluate(ok, np.zeros((3, 14)), ok)
    bad = ok.copy(); bad[0, 0] = np.nan
    with pytest.raises(ValueError): evaluate(ok, bad, ok)

# ---- ApprovedModel with a tiny real booster ----
@pytest.fixture()
def tiny(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 11)).astype(np.float32); Y = rng.normal(size=(200, 15)).astype(np.float32)
    mdl = XGBRegressor(n_estimators=5, max_depth=2, random_state=0); mdl.fit(X, Y)
    path = tmp_path / 'model.json'; mdl.save_model(path)
    man = good_manifest(); man['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, man, X

def test_approved_model_predicts_in_batches(tiny):
    path, man, X = tiny
    m = ApprovedModel(path, man)
    out = m.predict(X[:7], NAMES, batch_size=3)
    assert out.shape == (7, 15) and np.isfinite(out).all()
    np.testing.assert_allclose(out, m.predict(X[:7], NAMES, batch_size=500), rtol=1e-6)
    assert m.predict(np.empty((0, 11)), NAMES).shape == (0, 15)

def test_approved_model_rejects_tampering_and_bad_inputs(tiny):
    path, man, X = tiny
    bad = copy.deepcopy(man); bad['sha256'] = '0' * 64
    with pytest.raises(ValueError): ApprovedModel(path, bad)
    unapproved = copy.deepcopy(man); unapproved['approved'] = False
    with pytest.raises(ValueError): ApprovedModel(path, unapproved)
    m = ApprovedModel(path, man)
    with pytest.raises(ValueError): m.predict(X[:2], NAMES[::-1])
    with pytest.raises(ValueError): m.predict(X[:2, :10], NAMES)
    nan = X[:2].copy(); nan[0, 0] = np.nan
    with pytest.raises(ValueError): m.predict(nan, NAMES)

# ---- shipped research artifacts ----
ARTIFACTS = ['research', 'residual', 'multiyear', 'seasonal']

def load_art(name):
    manifest = json.loads((ART / f'nwic-{name}' / 'evaluation.json').read_text(encoding='utf-8'))
    return ART / f'nwic-{name}' / 'model.json', manifest

def cache_for(name):
    if name == 'research':
        return np.load(ART / 'nwic-research/benchmark_features.npz')
    own = ART / f'nwic-{name}' / 'training_cache.npz'
    return np.load(own if own.exists() else ART / 'nwic-multiyear/training_cache.npz')

@pytest.mark.parametrize('name', ARTIFACTS)
def test_artifact_hash_schema_and_prediction(name):
    path, man = load_art(name)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == man['sha256']
    assert man['feature_names'] == NAMES and man['horizons'] == list(range(1, 16))
    assert len(man['calibration_abs_error_quantile']) == 15
    model = XGBRegressor(); model.load_model(path)
    X = cache_for(name)['X'][:2000]
    out = predict_levels(model, X, man)
    assert out.shape == (2000, 15) and np.isfinite(out).all()
    # One-day-ahead forecasts must stay physically near the latest observation.
    assert np.abs(out[:, 0] - X[:, 0]).max() < 50

@pytest.mark.parametrize('name', ARTIFACTS)
def test_unapproved_artifacts_cannot_be_served(name):
    path, man = load_art(name)
    assert man['approved'] is False
    with pytest.raises(ValueError):
        ApprovedModel(path, man)

def test_seasonal_model_beats_persistence_on_held_out_rows():
    path, man = load_art('seasonal')
    model = XGBRegressor(); model.load_model(path)
    z = cache_for('seasonal')
    X, Y, D, G = z['X'], z['Y'], z['D'], z['G']
    start = date.fromisoformat(man['evaluation_start']).toordinal()
    held = list(map(str, man['geographic_holdout']))
    for label, mask in [('chronological', (D >= start) & ~np.isin(G, held)), ('geographic', (D >= start) & np.isin(G, held))]:
        idx = np.flatnonzero(mask)
        assert len(idx) > 500, label
        idx = idx[:: max(1, len(idx) // 20000)]
        pred = predict_levels(model, X[idx], man)
        persistence = np.repeat(X[idx, 0, None], 15, axis=1)
        q = np.asarray(man['calibration_abs_error_quantile'])
        m = evaluate(Y[idx], pred, persistence)
        wins = sum(m[str(h)]['mae'] < m[str(h)]['persistence_mae'] for h in range(1, 16))
        coverage = np.mean(np.abs(pred - Y[idx]) <= q, axis=0)
        assert wins >= 14, (label, wins)
        assert coverage.min() > .75, (label, coverage.min())

# ---- end to end: real seasonal artifact through the worker (approval forged in a temp copy only) ----
def test_worker_serves_real_seasonal_model_when_approved(setup, monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from services.api.db import Record
    from services.worker.main import daily_inference
    path, man = load_art('seasonal')
    (tmp_path / 'model.json').write_bytes(path.read_bytes())
    man = copy.deepcopy(man)
    man.update(approved=True, release_blockers=[], availability_verified=True, source_sign_verified=True, artifact='model.json')
    monkeypatch.setattr('services.worker.main.settings.model_artifact_root', str(tmp_path))
    client, factory, headers = setup
    X = cache_for('seasonal')['X'][0].astype(float).tolist()
    now = datetime.now(timezone.utc).isoformat()
    with factory() as db:
        db.add(Record(id='SEASONAL', kind='model', key='SEASONAL', payload=man))
        db.add(Record(kind='features', key='TEST-A', payload={'feature_names': NAMES, 'values': X, 'station_id': 'S', 'grid_id': 'G', 'mapping_verified': True, 'observed_at': now, 'issue_time': now}))
        db.commit()
        r = daily_inference(db, {'date': '2026-10-30'}); db.commit()
        assert r['villages'] == 2 and r['supported'] == 1
        f = db.scalar(select(Record).where(Record.kind == 'forecast', Record.key == 'TEST-A')).payload
        assert f['status'] == 'available' and len(f['daily']) == 15
        for d in f['daily']:
            assert d['interval_lower_m_bgl'] < d['groundwater_depth_m_bgl'] < d['interval_upper_m_bgl']
        other = db.scalar(select(Record).where(Record.kind == 'forecast', Record.key == 'TEST-B')).payload
        assert other['status'] == 'unavailable'

def test_worker_refuses_unapproved_real_model(setup, monkeypatch, tmp_path):
    from sqlalchemy import select
    from services.api.db import Record
    from services.worker.main import daily_inference
    path, man = load_art('seasonal')
    (tmp_path / 'model.json').write_bytes(path.read_bytes())
    man = copy.deepcopy(man); man.update(approved=True, artifact='model.json')  # blockers remain
    monkeypatch.setattr('services.worker.main.settings.model_artifact_root', str(tmp_path))
    client, factory, headers = setup
    with factory() as db:
        db.add(Record(kind='model', key='SEASONAL', payload=man)); db.commit()
        r = daily_inference(db, {'date': '2026-10-30'}); db.commit()
        assert r['supported'] == 0
        assert all(x.payload['status'] == 'unavailable' for x in db.scalars(select(Record).where(Record.kind == 'forecast')))
