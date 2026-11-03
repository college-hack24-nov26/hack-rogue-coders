import httpx
from sqlalchemy import select
from services.api.db import Record
from services.api.config import settings

def test_neon_proxy_refresh_and_encrypted_session(setup,monkeypatch):
    client,factory,headers=setup
    monkeypatch.setattr(settings,'auth_mode','neon');monkeypatch.setattr(settings,'neon_auth_url','https://auth.fixture.test');monkeypatch.setattr(settings,'neon_auth_origin','http://localhost:5173')
    real_client=httpx.AsyncClient
    def handler(request):
        if request.url.path=='/auth/sign-in/email':return httpx.Response(200,json={'token':'TEST-opaque-session-not-a-jwt','user':{'id':'TEST-NEON'}},headers={'set-cookie':'neon_session=private-fixture-cookie; Path=/; Secure; HttpOnly'})
        if request.url.path=='/auth/token':
            assert 'neon_session=private-fixture-cookie' in request.headers.get('cookie','')
            return httpx.Response(200,json={'token':'TEST-provider-issued-jwt'})
        if request.url.path=='/auth/sign-out':return httpx.Response(200,json={'success':True})
        return httpx.Response(404)
    monkeypatch.setattr('services.api.neon_auth.httpx.AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    response=client.post('/api/v1/auth/login',json={'email':'fixture@example.test','password':'fixture-password'});assert response.status_code==200,response.text
    body=response.json();assert body['access_token']=='TEST-provider-issued-jwt'
    with factory() as db:
        record=db.scalar(select(Record).where(Record.kind=='auth_session'));assert 'private-fixture-cookie' not in record.payload['cookie']
    refresh={'refresh_token':body['refresh_token']}
    assert client.post('/api/v1/auth/refresh',json=refresh).status_code==200
    assert client.post('/api/v1/auth/logout',json=refresh).status_code==200
    assert client.post('/api/v1/auth/refresh',json=refresh).status_code==401

def test_failed_research_model_cannot_be_promoted(setup):
    c,f,h=setup
    with f() as db:
        r=Record(id='TEST-FAILED-MODEL',kind='model',key='TEST',payload={'approved':False,'sha256':'a'*64,'artifact':'not-real.json','horizons':list(range(1,16))});db.add(r);db.commit()
    body={'sha256':'a'*64,'reason':'TEST attempted release of invalid candidate'}
    assert c.post('/api/v1/admin/models/TEST-FAILED-MODEL/release',headers=h['a'],json=body).status_code==403
    assert c.post('/api/v1/admin/models/TEST-FAILED-MODEL/release',headers=h['s'],json=body).status_code==422
