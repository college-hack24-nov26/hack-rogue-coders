"""Explicit isolated test fixtures only; never run against an application database."""
import json,os,tempfile
from pathlib import Path
testdir=tempfile.TemporaryDirectory(prefix='jalsathi-e2e-')
os.environ['DATABASE_URL']='sqlite:///'+str(Path(testdir.name)/'test.db')
os.environ['LOCAL_SIGNING_KEY']='e2e-fixture-signing-key-not-for-real-accounts'
os.environ['CORS_ORIGINS']='http://localhost:5183,http://localhost:5184,http://localhost:8088'
os.environ['ENVIRONMENT']='development'
os.environ['AUTH_MODE']='local'
os.environ['ALLOW_EXTERNAL_SEND']='false'
os.environ['GEMINI_API_KEY']=''
os.environ['GEMINI_MODEL']=''
artifact_root=Path(testdir.name)/'artifacts'
artifact_root.mkdir()
os.environ['MODEL_ARTIFACT_ROOT']=str(artifact_root)
from services.worker.village_supply_predictions import SNAPSHOT
(artifact_root/SNAPSHOT).write_text(json.dumps({'schema':1,'generated_at':'2026-01-01T00:00:00Z',
    'model_run':'test-run','villages':{'TEST-E2E':{'households':100,'household_basis':'district_median',
        'reference_date':'2025-12-31','scenarios':{'tight_supply':{'7':3,'15':4},'lower_supply':{'7':4,'15':5}}}}}),encoding='utf-8')
from services.api.db import Base,engine,Session,User,Village
from services.api.auth import hash_password
Base.metadata.create_all(engine)
with Session() as db:
    for key,role in [('farmer','farmer'),('admin','admin'),('official','official'),('operator','system_admin')]:db.add(User(id='TEST-'+key,email=key+'@fixture.test',password_hash=hash_password('fixture-password-123'),role=role,jurisdictions=['TEST-SCOPE'] if role!='farmer' else []))
    db.add(Village(id='TEST-E2E',name='TEST FIXTURE VILLAGE',district='TEST district',taluka='TEST taluka',jurisdiction='TEST-SCOPE',provenance={'fixture':True}));db.commit()
if __name__=='__main__':
    import uvicorn
    uvicorn.run('services.api.main:app',host='127.0.0.1',port=8011)
