import numpy as np
import pytest
from services.api.config import Settings
from services.api.readiness import configuration_status
from services.worker.directory import validate_rows
from services.worker.model import model_inputs,predict_levels
from scripts.repair_forecast import FEATURES,partitions

def test_source_directory_identity_and_count_reconciliation():
    row={'districtcode':'473','subdistrictcode':'4064','villagecode':'540148  ','villagenameenglish':'TEST FIXTURE ONLY'}
    assert list(validate_rows([row,row], '473',1))==['540148']
    with pytest.raises(ValueError):validate_rows([row], '474')
    with pytest.raises(ValueError):validate_rows([row], '473',2)
    with pytest.raises(ValueError):validate_rows([row,{**row,'villagenameenglish':'Conflicting identity'}], '473')
    with pytest.raises(ValueError):validate_rows([], '473',1)
    assert validate_rows([], '482',0)=={}

def test_residual_inference_uses_issue_time_reference_and_stored_shrinkage():
    manifest={'feature_names':FEATURES,'input_transform':'relative_lags_v1','prediction_transform':'delta_from_latest_v1','residual_weights':[.5]*15}
    features=np.array([[100,99,98,97,96,95,3,0,1,20,76]],dtype=np.float32)
    class Booster:
        def predict(self,values):
            assert values[0,:6].tolist()==[0,-1,-2,-3,-4,-5]
            return np.ones((len(values),15))*2
    assert (predict_levels(Booster(),features,manifest)==101).all()
    assert features[0,0]==100 # Input data/cache is immutable.
    manifest['residual_weights']=[float('nan')]*15
    with pytest.raises(ValueError):predict_levels(Booster(),features,manifest)
    with pytest.raises(ValueError):model_inputs([[float('nan')]*11],manifest)

def test_tuning_calibration_and_test_are_purged_and_geography_is_held_out():
    dates=np.repeat(np.arange(738000,738800),4);groups=np.tile(['1','2','3','4'],800)
    masks,held_out=partitions(dates,groups)
    for early,late in [('train','tuning'),('tuning','calibration'),('calibration','chronological')]:
        assert dates[masks[early]].max()+15<dates[masks[late]].min()
    assert not np.isin(groups[masks['train']|masks['tuning']|masks['calibration']],held_out).any()
    assert np.isin(groups[masks['geographic']],held_out).all()

def test_missing_provider_settings_are_not_mistaken_for_working_integrations():
    config=Settings(_env_file=None,gemini_api_key='TEST-SECRET',gemini_model='')
    result=configuration_status(config)
    assert result['providers']['gemini']['missing_env']==['GEMINI_MODEL']
    assert result['providers']['neon_database']['status']=='missing_configuration'
    assert 'TEST-SECRET' not in str(result)
    assert result['live_verified'] is False

def test_readiness_requires_system_admin_and_directory_jobs_require_location(setup):
    c,f,h=setup
    assert c.get('/api/v1/admin/integration-readiness',headers=h['f']).status_code==403
    assert c.get('/api/v1/admin/integration-readiness',headers=h['a']).status_code==403
    assert c.get('/api/v1/admin/integration-readiness',headers=h['s']).json()['registry']['villages']==2
    assert c.post('/api/v1/admin/ingestion-runs',headers=h['s'],json={'source':'villages'}).status_code==422
    assert c.post('/api/v1/admin/ingestion-runs',headers=h['s'],json={'source':'villages','district_code':'473'}).status_code==200

def test_one_unreachable_document_does_not_discard_the_other_source(setup,monkeypatch):
    import httpx
    from sqlalchemy import select
    from services.api.db import Record
    from services.worker.sources import schemes
    c,f,h=setup
    class OfficialPages:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url):
            if 'mahadbt' in url:raise httpx.ConnectError('TEST connection failure')
            return httpx.Response(200,text='<p>'+('TEST FIXTURE dated official passage. '*8)+'</p>',request=httpx.Request('GET',url))
    monkeypatch.setattr('services.worker.sources.httpx.Client',OfficialPages)
    with f() as db:
        result=schemes(db,{});db.commit()
        assert result['status']=='partial' and result['documents']==1
        assert len(db.scalars(select(Record).where(Record.kind=='document')).all())==1
        assert len(db.scalars(select(Record).where(Record.kind=='source_fetch')).all())==2

def test_directory_resume_does_not_silently_keep_conflicting_jurisdiction(setup,monkeypatch):
    from services.api.db import Village
    from scripts import import_official_directory as importer
    c,f,h=setup;monkeypatch.setattr(importer,'Session',f)
    with f() as db:
        db.add(Village(id='540148',name='TEST FIXTURE ONLY',district='TEST',taluka='TEST',jurisdiction='other-jurisdiction',provenance={'fixture':True}));db.commit()
    row={'districtcode':'473','subdistrictcode':'4064','villagecode':'540148','villagenameenglish':'TEST FIXTURE ONLY'}
    with pytest.raises(ValueError,match='different jurisdiction'):importer.import_rows('473',[row],'TEST-HASH','2026-10-30T00:00:00+00:00',1)
