import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['AUTH_MODE']='local'
os.environ['ENVIRONMENT']='development'
os.environ['ALLOW_EXTERNAL_SEND']='false'
os.environ['REDIS_URL']=''
os.environ['LOCAL_SIGNING_KEY']='test-only-signing-key-never-for-real-accounts'
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from services.api.db import Base,session,User,Village
from services.api.main import app
from services.api.auth import token

@pytest.fixture()
def setup(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    def dependency():
        with factory() as db: yield db
    app.dependency_overrides[session]=dependency
    monkeypatch.setattr('services.worker.main.Session',factory)
    with factory() as db:
        for role,key,scope in [('farmer','f',[]),('farmer','f2',[]),('admin','a',['scope-a']),('official','o',['scope-a']),('official','o2',['scope-b']),('system_admin','s',[])]:
            db.add(User(id=key,email=key+'@test.local',role=role,jurisdictions=scope))
        for key,scope in [('TEST-A','scope-a'),('TEST-B','scope-b')]:db.add(Village(id=key,name='TEST FIXTURE ONLY',district='Test',taluka='Test',jurisdiction=scope,provenance={'fixture':True}))
        db.commit();headers={u.id:{'Authorization':'Bearer '+token(u)} for u in db.query(User).all()}
    yield TestClient(app),factory,headers
    app.dependency_overrides.clear();engine.dispose()
