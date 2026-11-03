"""Versioned village-source reviews. A connection never implies measured delivery."""
import hashlib
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, or_, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import current, require, scoped
from .db import Record, User, Village, now, session, uid
from .schemas import Strict

router = APIRouter(prefix='/api/v1')


class SourceReview(Strict):
    expected_version: int = Field(default=0, ge=0)
    asset_id: str = Field(min_length=1, max_length=100)
    source_name: str = Field(min_length=2, max_length=250)
    kind: Literal['groundwater', 'river', 'canal', 'reservoir', 'pipeline', 'industrial_pipeline', 'tank', 'treatment', 'intake', 'pump', 'valve', 'meter', 'other']
    scheme_id: str = Field(min_length=2, max_length=150)
    connection_status: Literal['documented', 'not_connected', 'unresolved']
    evidence_method: Literal['official_scheme_record', 'authority_gis', 'field_inspection']
    evidence_url: str = Field(pattern=r'^https://[^\s]+$', max_length=2000)
    evidence_note: str = Field(min_length=20, max_length=4000)
    evidence_date: date
    valid_until: date
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    delivery_status: Literal['unknown', 'measured', 'reported_stopped'] = 'unknown'
    delivered_litres_per_day: float | None = Field(default=None, ge=0)
    delivery_observed_at: datetime | None = None
    delivery_evidence_url: str | None = Field(default=None, pattern=r'^https://[^\s]+$', max_length=2000)
    delivery_method: str | None = Field(default=None, min_length=10, max_length=1000)

    @model_validator(mode='after')
    def validate_evidence(self):
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        if not date(2021, 1, 1) <= self.evidence_date <= today:
            raise ValueError('Evidence must be dated from 2021 through today')
        if not today <= self.valid_until or (self.valid_until - self.evidence_date).days > 366:
            raise ValueError('Review must be current and expire within 366 days of its evidence')
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Both coordinates are required together')
        if self.delivery_status != 'unknown':
            if self.connection_status != 'documented':
                raise ValueError('Delivery evidence requires a documented source connection')
            if not all([self.delivery_observed_at, self.delivery_evidence_url, self.delivery_method]):
                raise ValueError('Delivery requires a dated reading, evidence link and measurement/report method')
            if self.delivery_observed_at.tzinfo is None:
                raise ValueError('Delivery timestamp must include its time zone')
            if not date(2021, 1, 1) <= self.delivery_observed_at.astimezone(ZoneInfo('Asia/Kolkata')).date() <= today or self.delivery_observed_at > datetime.now(timezone.utc):
                raise ValueError('Invalid delivery observation date')
            if self.delivery_status == 'measured' and self.delivered_litres_per_day is None:
                raise ValueError('Measured delivery requires litres/day; zero is a valid measurement')
        elif any(x is not None for x in [self.delivered_litres_per_day, self.delivery_observed_at, self.delivery_evidence_url, self.delivery_method]):
            raise ValueError('Unknown delivery must not contain measured delivery values')
        if self.delivery_status == 'reported_stopped' and self.delivered_litres_per_day not in (None, 0):
            raise ValueError('A stopped-supply report cannot contain positive delivery')
        return self


def review_key(village_id, asset_id):
    return village_id + ':' + hashlib.sha256(asset_id.encode()).hexdigest()


def reviews_for(db, village_id):
    records = db.scalars(select(Record).where(Record.kind == 'water_connection', or_(
        Record.key.startswith(village_id + ':', autoescape=True),
        and_(func.length(Record.key) == 64, Record.payload['village_id'].as_string() == village_id)))
                         .order_by(Record.version.desc()))
    latest = {}
    for record in records:
        asset_id = record.payload.get('asset_id', record.key)
        if record.payload.get('village_id') == village_id and asset_id not in latest:
            latest[asset_id] = record
    result = []
    for record in latest.values():
        item = {**record.payload, 'version': record.version, 'recorded_at': record.created_at}
        item['current'] = item['valid_until'] >= datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
        observed = item.get('delivery_observed_at')
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(observed)).total_seconds() if observed else None
        item['delivery_current'] = bool(item['current'] and age is not None and 0 <= age <= 48 * 3600)
        # An old reading is retained as evidence, never displayed as today's delivery.
        item['effective_delivery_status'] = item['delivery_status'] if item['delivery_current'] else 'unknown'
        result.append(item)
    return result


@router.post('/admin/villages/{key}/water-connections')
def save_review(key: str, body: SourceReview, u: User = Depends(current), db: Session = Depends(session)):
    require(u, ['system_admin', 'admin', 'official'])
    village = db.scalar(select(Village).where(Village.id == key).with_for_update())
    if not village:
        raise HTTPException(404, 'Village not found')
    if not scoped(u, village.jurisdiction):
        raise HTTPException(403, 'Outside jurisdiction')
    identity = review_key(key, body.asset_id)
    old = db.scalar(select(Record).where(Record.kind == 'water_connection', Record.key == identity)
                    .order_by(Record.version.desc()).limit(1))
    if not old:
        legacy_key = hashlib.sha256((key + '|' + body.asset_id).encode()).hexdigest()
        old = db.scalar(select(Record).where(Record.kind == 'water_connection', Record.key == legacy_key,
                        Record.payload['village_id'].as_string() == key).order_by(Record.version.desc()).limit(1))
    if body.expected_version != (old.version if old else 0):
        raise HTTPException(409, 'Review changed. Reload the village before saving.')
    payload = {**body.model_dump(mode='json', exclude={'expected_version'}), 'village_id': key,
               'reviewer': u.id, 'reviewed_at': now(), 'jurisdiction': village.jurisdiction,
               'prediction_use': False}
    record = Record(kind='water_connection', key=identity, version=body.expected_version + 1, payload=payload)
    db.add(record)
    db.add(Record(kind='audit', key=uid(), payload={'action': 'water_connection_review', 'village_id': key,
                'asset_id': body.asset_id, 'actor': u.id, 'version': record.version}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Review changed. Reload the village before saving.')
    return {'version': record.version, 'status': 'recorded', 'prediction_use': False}
