import hashlib,hmac,json,time
from sqlalchemy import select
from services.api.db import Complaint,Event,Job,Record
from services.api.config import settings
from services.worker.main import process_one

P='/api/v1'
def submit(c,h,v='TEST-A',key='fixture-key-0001'):
    return c.post(P+'/complaints',headers={**h,'Idempotency-Key':key},json={'village_id':v,'description':'TEST FIXTURE: water interrupted for this locality','category':'interruption','consent':True})
def accept(c,h,t):
    return c.post(P+f'/admin/complaints/{t["id"]}/review',headers=h,json={'status':'accepted','reason':'Reviewed test evidence','sanitized_description':'TEST FIXTURE: sanitized water interruption','expected_version':t['version'],'jurisdiction':'scope-a'})

def test_complete_flow_and_boundaries(setup):
    c,f,h=setup;t=submit(c,h['f']).json();key=t['id']
    for account in ['f2','o','o2']:
        assert c.get(P+'/complaints/'+key,headers=h[account]).status_code==404
    assert c.get(P+'/official/complaints/'+key,headers=h['o']).status_code==404
    assert c.post(P+f'/admin/complaints/{key}/review',headers=h['f'],json={'status':'accepted','reason':'bad privilege','expected_version':1}).status_code==403
    r=accept(c,h['a'],t);assert r.status_code==200,r.text;t=r.json()
    assert c.get(P+'/official/complaints/'+key,headers=h['o2']).status_code==404
    visible=c.get(P+'/official/complaints/'+key,headers=h['o']).json()
    assert 'original' not in visible and 'reporter_id' not in visible and 'request_hash' not in visible
    for state in ['acknowledged','assigned','in_progress','resolved']:
        r=c.post(P+f'/official/complaints/{key}/actions',headers=h['o'],json={'status':state,'note':'Demonstration fixture action','expected_version':t['version']});assert r.status_code==200,r.text;t=r.json()
    own=c.get(P+'/complaints/'+key,headers=h['f']).json();assert own['service_status']=='resolved';assert len(own['timeline'])==6
    r=c.post(P+f'/admin/complaints/{key}/review',headers=h['a'],json={'status':'withdrawn','reason':'Withdraw fixture publication','expected_version':t['version']});assert r.status_code==200
    assert c.get(P+'/official/complaints/'+key,headers=h['o']).status_code==404

def test_idempotency_version_scope_and_rejection(setup):
    c,f,h=setup;r=submit(c,h['f']);assert r.status_code==201;t=r.json()
    assert submit(c,h['f']).json()['id']==t['id']
    assert submit(c,h['f'],'TEST-B').status_code==409
    assert accept(c,h['a'],t).status_code==200
    assert accept(c,h['a'],t).status_code==409
    other=submit(c,h['f'],'TEST-B','fixture-key-0002').json();assert c.get(P+'/complaints/'+other['id'],headers=h['a']).status_code==404
    pending=submit(c,h['f'],'TEST-A','fixture-key-0003').json()
    r=c.post(P+f'/admin/complaints/{pending["id"]}/review',headers=h['a'],json={'status':'rejected','reason':'Insufficient fixture evidence','expected_version':1});assert r.status_code==200
    assert c.get(P+'/official/complaints/'+pending['id'],headers=h['o']).status_code==404

def test_signed_webhook_dedup_and_missing_location(setup,monkeypatch):
    c,f,h=setup;monkeypatch.setattr(settings,'whatsapp_app_secret','fixture-secret');monkeypatch.setattr(settings,'whatsapp_phone_number_id','fixture-number')
    def deliver(key,text):
        data={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'fixture-number'},'messages':[{'id':key,'from':'fixture-sender','timestamp':str(int(time.time())),'type':'text','text':{'body':text}}]}}]}]}
        raw=json.dumps(data).encode();sig='sha256='+hmac.new(b'fixture-secret',raw,hashlib.sha256).hexdigest()
        return c.post(P+'/webhooks/whatsapp',content=raw,headers={'x-hub-signature-256':sig,'Content-Type':'application/json'})
    assert c.post(P+'/webhooks/whatsapp',content=b'{}').status_code==403
    assert deliver('fixture-msg-1','TEST FIXTURE water leak without village').json()['received']==1
    assert deliver('fixture-msg-1','TEST FIXTURE water leak without village').json()['received']==0
    assert process_one()
    with f() as db:
        complaints=list(db.scalars(select(Complaint)));assert len(complaints)==1;assert complaints[0].review_status=='awaiting_location'
    deliver('fixture-msg-2','LGD:TEST-A TEST FIXTURE location and description')
    for _ in range(5):process_one()
    with f() as db:
        complaints=list(db.scalars(select(Complaint)));assert len(complaints)==1;assert complaints[0].review_status=='submitted';assert complaints[0].village_id=='TEST-A';assert complaints[0].original=='TEST FIXTURE water leak without village'
        assert any(j.status=='blocked' for j in db.scalars(select(Job)))

def test_worker_retry_and_dead_letter(setup):
    c,f,h=setup
    with f() as db:db.add(Job(key='bad-fixture',kind='unknown_fixture',payload={}));db.commit()
    for attempt in range(5):
        assert process_one()
        with f() as db:
            job=db.scalar(select(Job));assert job.attempts==attempt+1;job.available_at=0;db.commit()
    with f() as db:assert db.scalar(select(Job)).status=='dead'

def test_farm_ownership_and_auth(setup):
    c,f,h=setup
    assert c.get(P+'/villages').status_code==401
    assert c.post(P+'/auth/register',json={'email':'new@test.local','password':'long-test-password','role':'admin'}).status_code==422
    r=c.post(P+'/farms',headers=h['f'],json={'village_id':'TEST-A','crop':'TEST crop','area_ha':1,'sowing_date':'2026-10-01','irrigation_method':'drip'});assert r.status_code==200
    assert c.get(P+f'/farms/{r.json()["id"]}/irrigation-plan',headers=h['f2']).status_code==404
