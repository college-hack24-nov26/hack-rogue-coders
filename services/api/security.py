import hashlib,time
from fastapi import HTTPException
from sqlalchemy import delete
from .db import RateLimit

def limit(db,identity,maximum,period):
    """Atomic database-backed fixed-window limiter shared across API processes."""
    stamp=time.time();window=int(stamp//period)
    key=hashlib.sha256(identity.encode()).hexdigest()+':'+str(window)
    if db.bind.dialect.name=='postgresql':from sqlalchemy.dialects.postgresql import insert
    else:from sqlalchemy.dialects.sqlite import insert
    statement=insert(RateLimit).values(key=key,count=1,expires_at=(window+1)*period)
    count=db.scalar(statement.on_conflict_do_update(index_elements=[RateLimit.key],set_={'count':RateLimit.count+1}).returning(RateLimit.count))
    db.execute(delete(RateLimit).where(RateLimit.expires_at<stamp-period));db.commit()
    if count>maximum:raise HTTPException(429,'Request limit reached; try again later',headers={'Retry-After':str(period)})
