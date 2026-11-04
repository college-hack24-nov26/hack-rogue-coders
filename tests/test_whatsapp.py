import hashlib
import hmac
import json
import time
import io
import pytest
import httpx
from PIL import Image
from sqlalchemy import select
from services.api.config import settings
from services.api.db import Complaint, Record, Job, ProviderMessage
from services.worker.main import process_one, send_reply
from services.worker.whatsapp import intake
from services.worker.whatsapp_media import import_media
from test_workflow import accept, submit

P = '/api/v1'


@pytest.fixture
def wa(setup, monkeypatch):
    client, factory, headers = setup
    monkeypatch.setattr(settings, 'whatsapp_app_secret', 'test-secret')
    monkeypatch.setattr(settings, 'whatsapp_phone_number_id', 'test-business')
    counter = 0

    def send(text='', phone='919000000001', message=None, event_id=None):
        nonlocal counter
        counter += 1
        msg = {'id': event_id or 'wa-test-'+str(counter), 'from': phone, 'timestamp': str(int(time.time())),
               **(message or {'type': 'text', 'text': {'body': text}})}
        body = {'entry': [{'changes': [{'value': {'metadata': {'phone_number_id': 'test-business'}, 'messages': [msg]}}]}]}
        raw = json.dumps(body).encode()
        r = client.post(P+'/webhooks/whatsapp', content=raw, headers={'x-hub-signature-256': 'sha256='+hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()})
        assert r.status_code == 200, r.text
        for _ in range(25):
            if not process_one():
                break
        with factory() as db:
            job = db.scalar(select(Job).where(Job.key == 'reply:'+msg['id']))
            return job.payload['text'] if job else ''
    return client, factory, headers, send


def register(send):
    send('Hi')
    send('My soybean crop is drying due to insufficient irrigation water.')
    summary = send('LGD:TEST-A')
    assert 'YES' in summary and 'TEST FIXTURE ONLY' in summary
    return send('YES').split('Reference ID: ')[1].splitlines()[0]


def test_shared_workflow_linking_tracking_permissions_and_notifications(wa):
    c, f, h, send = wa
    key = register(send)
    with f() as db:
        ticket = db.get(Complaint, key)
        assert ticket.channel == 'whatsapp' and ticket.review_status == 'submitted'
        assert ticket.category == 'irrigation'
    assert key in send('STATUS '+key)
    assert 'unavailable' in send('STATUS '+key, phone='919000000002')
    assert c.get(P+'/complaints/'+key, headers=h['f']).status_code == 404
    command = c.post(P+'/whatsapp/link-code', headers=h['f']).json()['command']
    assert 'Linked' in send(command)
    assert 'invalid' in send(command)
    assert key in send('STATUS '+key)
    app_ticket = submit(c, h['f']).json()
    mine = c.get(P+'/complaints/mine', headers=h['f']).json()
    assert {key, app_ticket['id']} == {t['id'] for t in mine}
    assert c.get(P+'/complaints/'+key, headers=h['f2']).status_code == 404
    inbox = c.get(P+'/admin/complaints?channel=whatsapp', headers=h['a']).json()
    assert [t['id'] for t in inbox] == [key]
    assert c.get(P+'/official/complaints/'+key, headers=h['o']).status_code == 404
    send('SUBSCRIBE')
    ticket = accept(c, h['a'], inbox[0]).json()
    assert c.get(P+'/official/complaints/'+key, headers=h['o']).status_code == 200
    assert c.get(P+'/official/complaints/'+key, headers=h['o2']).status_code == 404
    for state in ['acknowledged', 'assigned', 'in_progress', 'resolved']:
        r = c.post(P+f'/official/complaints/{key}/actions', headers=h['o'], json={'status': state, 'note': 'Fixture official action', 'expected_version': ticket['version']})
        assert r.status_code == 200, r.text
        ticket = r.json()
    for _ in range(25):
        if not process_one(): break
    assert c.get(P+'/complaints/'+key, headers=h['f']).json()['service_status'] == 'resolved'
    assert 'resolved' in send('STATUS '+key)
    with f() as db:
        notifications = list(db.scalars(select(Job).where(Job.kind == 'whatsapp_reply')))
        assert any(j.payload.get('notification') and j.payload['to'] == '919000000001' for j in notifications)
        assert all(j.status == 'blocked' for j in notifications)


def test_draft_recovery_edits_cancel_marathi_and_multiple_complaints(wa):
    c, f, h, send = wa
    assert 'नमस्कार' in send('नमस्कार')
    send('शेतीसाठी पाण्याची टंचाई आहे')
    with f() as db: assert not list(db.scalars(select(Complaint)))
    assert 'LGD:' in send('unknown village')
    send('LGD:TEST-A')
    assert 'दुरुस्ती' in send('EDIT ISSUE पिकासाठी सिंचनाचे पाणी उपलब्ध नाही')
    assert 'in progress' in send('NEW')
    assert 'रद्द' in send('CANCEL')
    send('ENGLISH')
    first = register(send)
    second = register(send)
    assert first != second
    with f() as db: assert len(list(db.scalars(select(Complaint)))) == 2


def test_duplicate_worker_and_webhook_do_not_create_second_complaint(wa):
    c, f, h, send = wa
    send('A long enough fixture problem LGD:TEST-A')
    send('YES', event_id='confirmed')
    send('YES', event_id='confirmed')
    with f() as db:
        assert intake(db, {'message_id': 'confirmed'})['status'] == 'already_processed'
        db.commit()
        assert len(list(db.scalars(select(Complaint)))) == 1


def test_consent_delivery_window_allowlist_templates_and_transport_retry(wa, monkeypatch):
    c, f, h, send = wa
    monkeypatch.setattr(settings, 'allow_external_send', True)
    monkeypatch.setattr(settings, 'whatsapp_access_token', 'mock-token')
    monkeypatch.setattr(settings, 'whatsapp_api_version', 'test-version')
    monkeypatch.setattr(settings, 'whatsapp_approved_recipients', '919000000001')
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs['json'])
        return httpx.Response(200, json={'messages': [{'id': 'meta-mock'}]}, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx, 'post', post)
    payload = {'to': '919000000001', 'text': 'Test reply', 'inbound_timestamp': str(int(time.time()))}
    assert send_reply({**payload, 'to': '919000000002'})['status'] == 'blocked'
    assert send_reply({**payload, 'notification': True, 'opt_in': False})['status'] == 'blocked'
    assert send_reply(payload)['status'] == 'sent'
    stale = {**payload, 'inbound_timestamp': str(time.time()-90000), 'opt_in': True}
    assert send_reply(stale)['status'] == 'blocked'
    monkeypatch.setattr(settings, 'whatsapp_status_template', 'mock_approved_template')
    monkeypatch.setattr(settings, 'whatsapp_template_approved', True)
    assert send_reply(stale)['status'] == 'sent'
    assert calls[-1]['type'] == 'template'
    def fail(*args, **kwargs): raise httpx.ConnectError('Fixture outage')
    monkeypatch.setattr(httpx, 'post', fail)
    key = register(send)
    with f() as db:
        assert db.get(Complaint, key)
        jobs = list(db.scalars(select(Job).where(Job.kind == 'whatsapp_reply')))
        assert any(j.attempts == 1 and j.status == 'pending' for j in jobs)
        for j in jobs: j.available_at = 0
        db.commit()
    monkeypatch.setattr(httpx, 'post', post)
    for _ in range(25):
        if not process_one(): break
    with f() as db: assert len(list(db.scalars(select(Complaint)))) == 1


def test_unsubscribe_rechecks_queued_notifications(wa, monkeypatch):
    c, f, h, send = wa
    send('UNSUBSCRIBE')
    with f() as db:
        db.add(Job(key='queued-before-optout', kind='whatsapp_reply', payload={'to': '919000000001', 'text': 'Old update', 'notification': True, 'opt_in': True, 'inbound_timestamp': str(time.time())}))
        db.commit()
    monkeypatch.setattr(settings, 'allow_external_send', True)
    monkeypatch.setattr(settings, 'whatsapp_access_token', 'fixture')
    monkeypatch.setattr(settings, 'whatsapp_api_version', 'fixture')
    monkeypatch.setattr(settings, 'whatsapp_approved_recipients', '919000000001')
    monkeypatch.setattr(httpx, 'post', lambda *a, **k: pytest.fail('Must not send after unsubscribe'))
    process_one()
    with f() as db: assert db.scalar(select(Job).where(Job.key == 'queued-before-optout')).result['reason'] == 'Notification consent required'


def test_natural_location_gps_and_admin_clarification(wa):
    c, f, h, send = wa
    send('There is a water shortage in the village.')
    send(message={'type': 'location', 'location': {'latitude': 17.9, 'longitude': 74.3}})
    send('TEST FIXTURE ONLY, Test, Test')  # Ambiguous fixture villages must not route.
    send('LGD:TEST-A')
    key = send('YES').split('Reference ID: ')[1].splitlines()[0]
    ticket = c.get(P+'/admin/complaints', headers=h['a']).json()[0]
    r = c.post(P+f'/admin/complaints/{key}/review', headers=h['a'], json={'status': 'needs_information', 'reason': 'Please provide the affected crop', 'expected_version': ticket['version']})
    assert r.status_code == 200
    assert 'Please provide' in send('STATUS '+key)
    assert 'saved' in send('REPLY '+key+' Soybean at flowering stage')
    assert c.get(P+'/admin/complaints', headers=h['a']).json()[0]['review_status'] == 'submitted'
    with f() as db:
        record = db.scalar(select(Record).where(Record.kind == 'whatsapp_complaint', Record.key == key))
        assert record.payload['gps']['latitude'] == 17.9


def test_media_import_uses_existing_private_attachments(wa, monkeypatch, tmp_path):
    c, f, h, send = wa
    monkeypatch.setattr(settings, 'private_storage_root', str(tmp_path))
    monkeypatch.setattr(settings, 'whatsapp_access_token', 'fixture')
    monkeypatch.setattr(settings, 'whatsapp_api_version', 'fixture')
    out = io.BytesIO(); Image.new('RGB', (8, 8), 'green').save(out, 'PNG'); data = out.getvalue()
    def handler(request):
        if request.url.host == 'graph.facebook.com':
            return httpx.Response(200, json={'url': 'https://lookaside.fbsbx.com/image', 'mime_type': 'image/png', 'file_size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        return httpx.Response(200, content=data)
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    send(message={'type': 'image', 'image': {'id': '12345', 'mime_type': 'image/png', 'caption': 'Fixture soybean crop has insufficient water'}})
    send('LGD:TEST-A')
    key = send('YES').split('Reference ID: ')[1].splitlines()[0]
    command = c.post(P+'/whatsapp/link-code', headers=h['f']).json()['command']; send(command)
    attachments = c.get(P+f'/complaints/{key}/attachments', headers=h['f']).json()
    assert len(attachments) == 1 and attachments[0]['inspection'] == 'decoded_reencoded_metadata_removed'
    with f() as db: assert import_media(db, {'complaint_id': key, 'media_id': '12345'})['status'] == 'already_imported'


def test_database_failure_rolls_back_success_reply_and_keeps_draft(wa, monkeypatch):
    c, f, h, send = wa
    send('There is no irrigation water LGD:TEST-A')
    def fail(*a, **kw): raise RuntimeError('Fixture database failure')
    monkeypatch.setattr('services.worker.whatsapp.create_complaint', fail)
    assert send('YES', event_id='db-failure') == ''
    with f() as db:
        assert not list(db.scalars(select(Complaint)))
        assert not db.scalar(select(Job).where(Job.key == 'reply:db-failure'))
        assert db.scalar(select(Job).where(Job.key == 'wa:db-failure')).status == 'pending'


def test_signed_delivery_receipts_deduplicate_and_retry_transient_failures(wa):
    c, f, h, send = wa
    with f() as db:
        db.add(Job(key='receipt-job',kind='whatsapp_reply',payload={'to':'919000000001','text':'fixture'},status='completed',attempts=1,result={'status':'sent','provider_ids':['meta-receipt-id']}))
        db.commit()
    receipt={'id':'meta-receipt-id','status':'failed','timestamp':str(int(time.time())),'errors':[{'code':131016}]}
    data={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'test-business'},'statuses':[receipt]}}]}]}
    raw=json.dumps(data).encode();headers={'x-hub-signature-256':'sha256='+hmac.new(b'test-secret',raw,hashlib.sha256).hexdigest()}
    assert c.post(P+'/webhooks/whatsapp',content=raw,headers=headers).status_code==200
    assert c.post(P+'/webhooks/whatsapp',content=raw,headers=headers).status_code==200
    with f() as db:
        assert len(list(db.scalars(select(Record).where(Record.kind=='whatsapp_receipt'))))==1
        job=db.scalar(select(Job).where(Job.key=='receipt-job'))
        assert job.status=='pending' and job.available_at>time.time()


def test_link_expiry_staff_restriction_and_natural_location(wa):
    from services.api.db import Village
    c,f,h,send=wa
    assert c.post(P+'/whatsapp/link-code',headers=h['a']).status_code==403
    command=c.post(P+'/whatsapp/link-code',headers=h['f']).json()['command']
    with f() as db:
        r=db.scalar(select(Record).where(Record.kind=='whatsapp_link_code'))
        r.payload={**r.payload,'expires_at':time.time()-1}
        v=db.get(Village,'TEST-A');v.name='Unique fixture village';db.commit()
    assert 'expired' in send(command)
    send('This fixture village has insufficient water')
    summary=send('Unique fixture village, Test, Test')
    assert 'YES' in summary and 'Unique fixture village' in summary
    send('CANCEL')
    assert 'STATUS <ID>' in send('HELP')
    with f() as db: assert not list(db.scalars(select(Complaint)))


def test_long_summary_and_unsupported_media_are_safe(wa):
    c,f,h,send=wa
    send('Water shortage ' * 600)
    summary=send('LGD:TEST-A')
    assert len(summary)<=4096
    assert 'Please send text' in send(message={'type':'audio','audio':{'id':'123'}})
    assert 'JPEG or PNG' in send(message={'type':'image','image':{'id':'123','mime_type':'application/pdf'}})
    assert 'Invalid GPS' in send(message={'type':'location','location':{'latitude':1000,'longitude':74}})
    send('YES')
    with f() as db:
        assert len(list(db.scalars(select(Complaint))))==1


def test_unprocessed_messages_preserve_sender_order(wa):
    c,f,h,send=wa
    with f() as db:
        db.add(ProviderMessage(id='earlier',sender='order-test',received_at='2026-01-01T00:00:00',payload={'type':'text','text':{'body':'Hi'}}))
        db.add(ProviderMessage(id='later',sender='order-test',received_at='2026-01-01T00:00:01',payload={'type':'text','text':{'body':'An irrigation water shortage'}}))
        db.commit()
        with pytest.raises(ValueError,match='Earlier sender'): intake(db,{'message_id':'later'})
        db.rollback()
        intake(db,{'message_id':'earlier'});db.commit()
        intake(db,{'message_id':'later'});db.commit()
        state=db.scalar(select(Record).where(Record.kind=='whatsapp_conversation',Record.version==2))
        assert state.payload['issue']=='An irrigation water shortage'
