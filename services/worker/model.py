"""Offline artifact evaluation and gated XGBoost inference. No training in the daily worker."""
import hashlib
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor

def model_inputs(features, manifest):
    data = np.asarray(features, dtype=np.float32)
    if data.ndim != 2 or not np.isfinite(data).all():
        raise ValueError('Expected finite rows of model features')
    if manifest.get('input_transform') == 'relative_lags_v1':
        if manifest.get('feature_names', [])[:6] != ['level_t','level_t_minus_1','level_t_minus_3','level_t_minus_7','level_t_minus_14','level_t_minus_28']:
            raise ValueError('Relative-lag feature schema mismatch')
        # Keep the original issue-time observation outside the booster. The booster
        # learns changes, so its predictions generalize across different well depths.
        data = data.copy()
        data[:, 1:6] -= data[:, 0, None]
        data[:, 0] = 0
    elif manifest.get('input_transform') not in (None, 'identity'):
        raise ValueError('Unknown model input transform')
    return data

def predict_levels(model, features, manifest):
    data = np.asarray(features, dtype=np.float32)
    out = np.asarray(model.predict(model_inputs(data, manifest)))
    if manifest.get('prediction_transform') == 'delta_from_latest_v1':
        weights = np.asarray(manifest.get('residual_weights', []), dtype=float)
        if weights.shape != (15,) or not np.isfinite(weights).all() or ((weights < 0) | (weights > 1)).any():
            raise ValueError('Fifteen bounded residual weights required')
        out = data[:, 0, None] + out * weights
    elif manifest.get('prediction_transform') not in (None, 'identity'):
        raise ValueError('Unknown prediction transform')
    if out.shape != (len(data), 15) or not np.isfinite(out).all():
        raise ValueError('Invalid output horizons')
    return out

def release_gate(manifest):
    if manifest.get('approved') is not True: raise ValueError('Not approved')
    if manifest.get('release_blockers'):raise ValueError('Outstanding model release blockers')
    if manifest.get('horizons')!=list(range(1,16)): raise ValueError('All 15 daily horizons required')
    if not manifest.get('issue_time_features') or not manifest.get('geographic_holdout') or manifest.get('purge_days',0)<15: raise ValueError('Leakage-safe chronological and geographic evaluation required')
    if manifest.get('availability_verified') is not True or manifest.get('source_sign_verified') is not True:raise ValueError('Verified availability and source sign conventions required')
    intervals=manifest.get('calibration_abs_error_quantile',[])
    if len(intervals)!=15 or not all(np.isfinite(x) and x>=0 for x in intervals):raise ValueError('Fifteen calibrated uncertainty offsets required')
    for h in range(1,16):
        m=manifest.get('metrics',{}).get(str(h),{})
        if not all(k in m for k in ['mae','rmse','persistence_mae','coverage','interval_width']): raise ValueError('Missing horizon metrics')
        if not all(np.isfinite(m[k]) and m[k]>=0 for k in ['mae','rmse','persistence_mae','coverage','interval_width']):raise ValueError('Invalid evaluation metrics')
        if m['persistence_mae']<=0 or m['mae']>=m['persistence_mae'] or not .8<=m['coverage']<=1: raise ValueError('Model fails persistence or uncertainty gate')
    evaluations=manifest.get('evaluations',{})
    for name in ['chronological','geographic']:
        if name not in evaluations:raise ValueError('Independent chronological and geographic evaluation required')
        for h in range(1,16):
            m=evaluations[name].get('metrics',{}).get(str(h),{})
            if not all(k in m for k in ['mae','persistence_mae','coverage']) or not 0<=m['mae']<m['persistence_mae'] or not .8<=m['coverage']<=1:raise ValueError(name+' evaluation failed release gates')
    return True

class ApprovedModel:
    def __init__(self,artifact,manifest):
        release_gate(manifest)
        if hashlib.sha256(Path(artifact).read_bytes()).hexdigest()!=manifest['sha256']: raise ValueError('Artifact hash mismatch')
        self.model=XGBRegressor();self.model.load_model(artifact);self.manifest=manifest
    def predict(self,features,feature_names,batch_size=500):
        if feature_names!=self.manifest['feature_names']: raise ValueError('Feature schema mismatch')
        data=np.asarray(features,dtype=float)
        if data.ndim!=2 or data.shape[1]!=len(feature_names) or not np.isfinite(data).all(): raise ValueError('Missing or nonfinite features are unsupported')
        batches=[predict_levels(self.model,data[i:i+batch_size],self.manifest) for i in range(0,len(data),batch_size)]
        out=np.concatenate(batches) if batches else np.empty((0,15))
        if out.shape!=(len(data),15) or not np.isfinite(out).all(): raise ValueError('Invalid output horizons')
        return out

def evaluate(actual,predicted,persistence):
    a,p,b=map(lambda x:np.asarray(x,dtype=float),(actual,predicted,persistence))
    if a.shape!=p.shape or a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=15 or not all(np.isfinite(x).all() for x in [a,p,b]): raise ValueError('Expected finite held-out samples by 15 horizons')
    return {str(h+1):{'mae':float(np.abs(a[:,h]-p[:,h]).mean()),'rmse':float(np.sqrt(np.square(a[:,h]-p[:,h]).mean())),'persistence_mae':float(np.abs(a[:,h]-b[:,h]).mean())} for h in range(15)}
