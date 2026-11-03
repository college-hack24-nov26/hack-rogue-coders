from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import current,require
from .db import session,User,Record,uid,now
from .schemas import Strict
from .config import settings
router=APIRouter(prefix='/api/v1')
class DeletionRequest(Strict):reason:str=Field(min_length=5,max_length=2000)
@router.get('/privacy')
def policy():return {'development_policy':True,'retention_days':settings.retention_days,'complaint_records':'Original reports and audit history are retained pending reviewed retention/deletion decisions','photos':'Private, decoded and re-encoded. Officials need individual evidence approval.','language_ai':'Question and retrieved evidence shared with Gemini only with explicit consent','whatsapp_identity':'A sender is not a verified farmer or landowner','production_policy_requires_review':True}
@router.post('/me/deletion-requests')
def request_deletion(body:DeletionRequest,u:User=Depends(current),db:Session=Depends(session)):
    r=Record(kind='deletion_request',key=uid(),payload={'requester':u.id,'reason':body.reason,'status':'pending_review','received_at':now()});db.add(r);db.commit();return {'request_id':r.id,'status':'pending_review','reason':'Retention and audit obligations require review before deletion'}
@router.get('/admin/deletion-requests')
def deletion_requests(u:User=Depends(current),db:Session=Depends(session)):
    require(u,['system_admin']);return [{'id':r.id,**r.payload} for r in db.scalars(select(Record).where(Record.kind=='deletion_request'))]
