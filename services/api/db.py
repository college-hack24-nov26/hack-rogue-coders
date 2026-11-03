from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, Text, JSON, Float, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(250), unique=True)
    password_hash: Mapped[str] = mapped_column(Text, default='')
    role: Mapped[str] = mapped_column(String(30), default='farmer')
    jurisdictions: Mapped[list] = mapped_column(JSON, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)

class Village(Base):
    __tablename__ = 'villages'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    district: Mapped[str] = mapped_column(String(200))
    taluka: Mapped[str] = mapped_column(String(200))
    jurisdiction: Mapped[str] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    provenance: Mapped[dict] = mapped_column(JSON)

class Farm(Base):
    __tablename__ = 'farms'
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    village_id: Mapped[str] = mapped_column(String(100), index=True)
    details: Mapped[dict] = mapped_column(JSON)

class Complaint(Base):
    __tablename__ = 'complaints'
    __table_args__ = (UniqueConstraint('reporter_id', 'idempotency_key'),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    reporter_id: Mapped[str] = mapped_column(String(150), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(150))
    request_hash: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(20), default='app')
    original: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    village_id: Mapped[str | None] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(50))
    review_status: Mapped[str] = mapped_column(String(30), default='submitted', index=True)
    service_status: Mapped[str] = mapped_column(String(30), default='pending_acknowledgement')
    jurisdiction: Mapped[str | None] = mapped_column(String(100), index=True)
    publishable: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[str | None] = mapped_column(String(100))
    admin_note: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    __mapper_args__ = {'version_id_col': version}

class Event(Base):
    __tablename__ = 'complaint_events'
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    complaint_id: Mapped[str] = mapped_column(String(100), index=True)
    actor_id: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(String(250), unique=True)
    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[float] = mapped_column(Float, default=0)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)

class ProviderMessage(Base):
    __tablename__ = 'provider_messages'
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    sender: Mapped[str] = mapped_column(String(150), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[str] = mapped_column(String(40), default=now)

class Record(Base):
    __tablename__ = 'records'
    __table_args__ = (UniqueConstraint('kind', 'key', 'version'),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    key: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class RateLimit(Base):
    __tablename__ = 'rate_limits'
    key: Mapped[str] = mapped_column(String(200),primary_key=True)
    count: Mapped[int] = mapped_column(Integer,default=0)
    expires_at: Mapped[float] = mapped_column(Float,index=True)

engine = create_engine(settings.database_url, connect_args={'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
def session():
    with Session() as db: yield db
