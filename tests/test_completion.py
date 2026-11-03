import hashlib,io
from PIL import Image
from services.api.config import settings

P='/api/v1'
def complaint(client,headers):return client.post(P+'/complaints',headers={**headers,'Idempotency-Key':'TEST-attachment-key'},json={'village_id':'TEST-A','description':'TEST FIXTURE complaint for attachment inspection','category':'leakage','consent':True}).json()
def test_private_attachment_inspection_and_publication(setup,tmp_path,monkeypatch):
    c,f,h=setup;monkeypatch.setattr(settings,'private_storage_root',str(tmp_path));monkeypatch.setattr(settings,'storage_mode','local')
    ticket=complaint(c,h['f']);out=io.BytesIO();Image.new('RGB',(16,16),'green').save(out,format='PNG');data=out.getvalue()
    pending=c.post(P+'/uploads/presign',headers=h['f'],json={'complaint_id':ticket['id'],'size':len(data),'content_type':'image/png','sha256':hashlib.sha256(data).hexdigest()}).json()
    assert c.put(pending['upload']['url'],headers=h['f2'],content=data).status_code==404
    assert c.put(pending['upload']['url'],headers=h['f'],content=data).status_code==200
    finalized=c.post(P+'/uploads/'+pending['attachment_id']+'/finalize',headers=h['f']);assert finalized.status_code==200,finalized.text;key=finalized.json()['attachment_id']
    assert c.get(P+'/attachments/'+key+'/content',headers=h['f']).headers['content-type']=='image/jpeg'
    assert c.get(P+'/attachments/'+key+'/content',headers=h['o']).status_code==404
    c.post(P+'/admin/complaints/'+ticket['id']+'/review',headers=h['a'],json={'status':'accepted','reason':'Reviewed test photo report','sanitized_description':'TEST reviewed photo report','expected_version':1,'jurisdiction':'scope-a'})
    assert c.get(P+'/attachments/'+key+'/content',headers=h['o']).status_code==404
    assert c.post(P+'/admin/attachments/'+key+'/approve',headers=h['a']).status_code==200
    assert c.get(P+'/attachments/'+key+'/content',headers=h['o']).status_code==200
    assert c.get(P+'/attachments/'+key+'/content',headers=h['o2']).status_code==404
def test_invalid_photo_does_not_publish(setup,tmp_path,monkeypatch):
    c,f,h=setup;monkeypatch.setattr(settings,'private_storage_root',str(tmp_path));ticket=complaint(c,h['f']);data=b'not a real image'
    p=c.post(P+'/uploads/presign',headers=h['f'],json={'complaint_id':ticket['id'],'size':len(data),'content_type':'image/jpeg','sha256':hashlib.sha256(data).hexdigest()}).json()
    c.put(p['upload']['url'],headers=h['f'],content=data)
    assert c.post(P+'/uploads/'+p['attachment_id']+'/finalize',headers=h['f']).status_code==422
    assert c.get(P+'/complaints/'+ticket['id']+'/attachments',headers=h['f']).json()==[]
def test_invitation_cannot_be_redeemed_by_other_identity(setup):
    c,f,h=setup
    body={'email':'f@test.local','role':'official','jurisdictions':['scope-a']}
    assert c.post(P+'/admin/access/invitations',headers=h['a'],json=body).status_code==403
    code=c.post(P+'/admin/access/invitations',headers=h['s'],json=body).json()['invitation_code']
    assert c.post(P+'/access/redeem',headers=h['f2'],json={'code':code}).status_code==404
    assert c.post(P+'/access/redeem',headers=h['f'],json={'code':code}).status_code==200
    assert c.get(P+'/me',headers=h['f']).json()['role']=='official'
    assert c.post(P+'/access/redeem',headers=h['f'],json={'code':code}).status_code==404
def test_shared_supply_allocation_and_daily_shortage(setup):
    c,f,h=setup
    source={'source_id':'TEST-SUPPLY','source_url':'https://example.test/source','yield_litres_per_day':100,'valid_until':'2030-01-01','method':'TEST reviewed flow records'}
    assert c.post(P+'/admin/supply-sources',headers=h['s'],json=source).status_code==200
    allocation={'source_id':'TEST-SUPPLY','sector':'household','litres_per_day':80,'opening_storage_litres':0,'storage_capacity_litres':200,'delivery_limit_litres_per_day':80,'valid_until':'2030-01-01','source_evidence':'TEST FIXTURE operator records','assumptions':'TEST constant delivery scenario'}
    assert c.post(P+'/admin/villages/TEST-A/supply',headers=h['a'],json=allocation).status_code==200
    assert c.post(P+'/admin/villages/TEST-B/supply',headers=h['s'],json=allocation).status_code==422
    baseline={'sector':'household','litres_per_day':100,'method':'TEST normative','source':'TEST source','reference_start':'2026-01-01','reference_end':'2026-02-01','valid_from':'2026-01-01','valid_to':'2030-01-01','uses_covered':'domestic','assumptions':'TEST assumption','uncertainty':'unknown'}
    c.post(P+'/admin/villages/TEST-A/baselines',headers=h['a'],json=baseline)
    result=c.get(P+'/villages/TEST-A/water-budget?days=7',headers=h['f']).json();assert result['shortage_litres']==140;assert result['status']=='reviewed_supply_scenario'
def test_revoking_staff_access_takes_effect_for_existing_token(setup):
    c,f,h=setup
    assert c.get(P+'/official/complaints',headers=h['o']).status_code==200
    assert c.patch(P+'/admin/access/users/o',headers=h['a'],json={'role':'farmer','jurisdictions':[],'reason':'TEST revoke staff access'}).status_code==403
    assert c.patch(P+'/admin/access/users/o',headers=h['s'],json={'role':'farmer','jurisdictions':[],'reason':'TEST revoke staff access'}).status_code==200
    assert c.get(P+'/official/complaints',headers=h['o']).status_code==403
def test_quality_and_privacy_routes_are_accessible_only_to_authorized_roles(setup):
    c,f,h=setup
    assert c.get(P+'/admin/quality',headers=h['a']).status_code==200
    assert c.get(P+'/admin/quality',headers=h['f']).status_code==403
    assert c.get(P+'/admin/deletion-requests',headers=h['s']).status_code==200
    assert c.get(P+'/admin/deletion-requests',headers=h['a']).status_code==403
