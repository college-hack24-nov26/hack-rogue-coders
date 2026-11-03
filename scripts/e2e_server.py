"""Explicit isolated test fixtures only; never run against an application database."""
import os,tempfile
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
from services.api.db import Base,engine,Session,User,Village
from services.api.auth import hash_password
Base.metadata.create_all(engine)
with Session() as db:
    for key,role in [('farmer','farmer'),('admin','admin'),('official','official'),('operator','system_admin')]:db.add(User(id='TEST-'+key,email=key+'@fixture.test',password_hash=hash_password('fixture-password-123'),role=role,jurisdictions=['TEST-SCOPE'] if role!='farmer' else []))
    db.add(Village(id='TEST-E2E',name='TEST FIXTURE VILLAGE',district='TEST district',taluka='TEST taluka',jurisdiction='TEST-SCOPE',provenance={'fixture':True}));db.commit()
if __name__=='__main__':
    import uvicorn
    uvicorn.run('services.api.main:app',host='127.0.0.1',port=8011)
