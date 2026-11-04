"""Shared complaint creation; callers own the transaction and delivery jobs."""
import hashlib
from .db import Complaint, Event, uid
from .schemas import ComplaintInput


def create_complaint(db, reporter, key, body: ComplaintInput, village, channel='app'):
    c = Complaint(id=uid(), reporter_id=reporter, idempotency_key=key,
                  request_hash=hashlib.sha256(body.model_dump_json().encode()).hexdigest(),
                  channel=channel, original=body.description, description=body.description,
                  village_id=village.id, jurisdiction=village.jurisdiction, category=body.category)
    db.add(c)
    db.add(Event(complaint_id=c.id, actor_id=reporter, kind='submitted',
                 note=f'Report submitted by {channel} after confirmation with consent'))
    return c
