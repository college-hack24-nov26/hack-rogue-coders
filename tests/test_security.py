import pytest
from sqlalchemy import select
from fastapi import HTTPException
from services.api.security import limit
from services.api.db import Job

def test_database_limiter_is_shared_across_sessions(setup):
    _,factory,_=setup
    with factory() as db:limit(db,'fixture-identity',2,60)
    with factory() as db:limit(db,'fixture-identity',2,60)
    with factory() as db:
        with pytest.raises(HTTPException) as error:limit(db,'fixture-identity',2,60)
        assert error.value.status_code==429

def test_operations_redacts_provider_payloads(setup):
    client,factory,headers=setup
    with factory() as db:db.add(Job(key='TEST-private',kind='whatsapp_reply',payload={'to':'TEST-private-phone','text':'TEST-private-body'}));db.commit()
    response=client.get('/api/v1/admin/operations',headers=headers['a'])
    assert response.status_code==200
    assert 'TEST-private-phone' not in response.text and 'TEST-private-body' not in response.text
def test_ingestion_failure_is_visible_and_does_not_invent_a_source_refresh(setup,monkeypatch):
    import httpx
    from services.api.db import Record
    from services.worker.main import process_one
    c,f,h=setup
    def fail(*args):raise httpx.ConnectError('TEST FIXTURE provider unavailable')
    monkeypatch.setattr('services.worker.sources.msamb',fail)
    with f() as db:db.add(Job(key='TEST-failed-source',kind='msamb_ingest',payload={'commodity_code':'08035'}));db.commit()
    assert process_one()
    with f() as db:
        job=db.scalar(select(Job));assert job.status=='pending';assert job.error=='ConnectError'
        receipt=db.scalar(select(Record).where(Record.kind=='source_fetch'));assert receipt.payload['status']=='failed'
