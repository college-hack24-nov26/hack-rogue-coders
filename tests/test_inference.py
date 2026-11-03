from datetime import datetime,timezone
from sqlalchemy import select
import numpy as np
from services.api.db import Record
from services.worker.main import daily_inference

def test_daily_supported_and_unsupported_lineage(setup,monkeypatch):
    client,factory,headers=setup
    class FixtureModel:
        def __init__(self,artifact,manifest):self.manifest=manifest
        def predict(self,features,names):return np.array([[float(i) for i in range(15)] for _ in features])
    monkeypatch.setattr('services.worker.model.ApprovedModel',FixtureModel)
    with factory() as db:
        db.add(Record(id='TEST-MODEL',kind='model',key='TEST',payload={'approved':True,'artifact':'fixture-only.json','feature_names':['x'],'metrics':{'fixture':True}}))
        db.add(Record(id='TEST-FEATURES',kind='features',key='TEST-A',payload={'feature_names':['x'],'values':[1.0],'station_id':'TEST-STATION','grid_id':'TEST-GRID','mapping_verified':True,'observed_at':datetime.now(timezone.utc).isoformat(),'issue_time':datetime.now(timezone.utc).isoformat()}));db.commit()
        r=daily_inference(db,{'date':'2026-10-30'});db.commit();assert r['villages']==2;assert r['supported']==1
        available=db.scalar(select(Record).where(Record.kind=='forecast',Record.key=='TEST-A'))
        assert len(available.payload['daily'])==15;assert available.payload['feature_record_id']=='TEST-FEATURES';assert available.payload['model_id']=='TEST-MODEL';assert available.payload['budget_15']['shortage_litres'] is None
        assert daily_inference(db,{'date':'2026-10-30'})['villages']==0

def test_stale_inputs_not_published_as_fresh(setup,monkeypatch):
    client,factory,headers=setup
    class FixtureModel:
        def __init__(self,artifact,manifest):self.manifest=manifest
        def predict(self,*a):raise AssertionError('Must not infer stale observations')
    monkeypatch.setattr('services.worker.model.ApprovedModel',FixtureModel)
    with factory() as db:
        db.add(Record(kind='model',key='TEST',payload={'approved':True,'artifact':'test.json','feature_names':['x']}))
        db.add(Record(kind='features',key='TEST-A',payload={'feature_names':['x'],'values':[1],'observed_at':'2000-01-01T00:00:00+00:00','issue_time':datetime.now(timezone.utc).isoformat(),'mapping_verified':True,'station_id':'TEST','grid_id':'TEST'}));db.commit()
        r=daily_inference(db,{'date':'2026-10-30'});db.commit();assert r['supported']==0
