import hashlib,secrets
from datetime import datetime,timedelta,timezone,date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from .db import session,User,Village,Record,Complaint,Event,Job,uid,now
from .auth import current,require,scoped
from .schemas import Strict

router=APIRouter(prefix='/api/v1')

@router.get('/admin/integration-readiness')
def integration_readiness(u:User=Depends(current),db:Session=Depends(session)):
    require(u,['system_admin'])
    from .readiness import configuration_status
    from .config import settings
    result=configuration_status(settings)
    latest_import=db.scalar(select(Record).where(Record.kind=='registry_import').order_by(Record.created_at.desc()).limit(1))
    result['registry']={'villages':db.scalar(select(func.count()).select_from(Village)),'last_import':latest_import.payload if latest_import else None}
    return result

class Invitation(Strict):
    email:str=Field(min_length=3,max_length=250)
    role:Literal['admin','official','farmer']
    jurisdictions:list[str]
class Redeem(Strict):code:str=Field(min_length=32,max_length=150)
class AccessUpdate(Strict):
    role:Literal['admin','official','farmer']
    jurisdictions:list[str]
    reason:str=Field(min_length=10)
class GeographicUpdate(Strict):
    expected_version:int
    latitude:float|None=Field(default=None,ge=-90,le=90)
    longitude:float|None=Field(default=None,ge=-180,le=180)
    boundary:dict|None=None
    crosswalks:dict=Field(default_factory=dict)
    source:str=Field(min_length=5)
    reason:str=Field(min_length=5)
class Notice(Strict):
    title:str=Field(min_length=3,max_length=300)
    passage:str=Field(min_length=10,max_length=8000)
    source:str=Field(pattern=r'^https://')
    source_date:date
    publication_date:date|None=None
    village_id:str
    valid_until:date
    applicability_note:str=Field(min_length=5)
class SupplySource(Strict):
    source_id:str
    source_url:str=Field(pattern=r'^https://')
    yield_litres_per_day:float=Field(ge=0)
    valid_until:date
    method:str=Field(min_length=10)
class SupplyAllocation(Strict):
    source_id:str
    sector:Literal['household','agriculture','livestock','other']
    litres_per_day:float=Field(ge=0)
    opening_storage_litres:float=Field(ge=0)
    storage_capacity_litres:float=Field(ge=0)
    delivery_limit_litres_per_day:float=Field(ge=0)
    valid_until:date
    source_evidence:str=Field(min_length=5)
    assumptions:str=Field(min_length=10)
class Ingest(Strict):
    source:Literal['weather','msamb','agmarknet','schemes','villages']
    village_id:str|None=None
    commodity_code:str|None=None
    district_code:str|None=None
class Release(Strict):
    sha256:str=Field(pattern='^[a-f0-9]{64}$')
    reason:str=Field(min_length=10)
@router.post('/admin/jobs/{key}/retry')
def retry_job(key:str,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['system_admin']);job=db.get(Job,key)
    if not job:raise HTTPException(404,'Job not found')
    if job.status not in ['blocked','dead']:raise HTTPException(409,'Only blocked or dead jobs can be retried')
    job.status='pending';job.attempts=0;job.available_at=0;job.error=None;db.add(Record(kind='audit',key=uid(),payload={'actor':u.id,'action':'retry_job','job_id':key}));db.commit();return {'id':key,'status':'pending'}

@router.get('/admin/access/users')
def users(u:User=Depends(current),db:Session=Depends(session)):
    require(u,['system_admin']);return [{'id':x.id,'email':x.email,'role':x.role,'jurisdictions':x.jurisdictions} for x in db.scalars(select(User))]
@router.patch('/admin/access/users/{key}')
def update_access(key:str,body:AccessUpdate,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['system_admin']);target=db.get(User,key)
    if not target:raise HTTPException(404,'Account not found')
    if target.role=='system_admin':raise HTTPException(409,'System administrator access is managed through the operator CLI')
    before={'role':target.role,'jurisdictions':target.jurisdictions};target.role=body.role;target.jurisdictions=body.jurisdictions;db.add(Record(kind='audit',key=uid(),payload={'action':'change_access','actor':u.id,'target':key,'before':before,'after':body.model_dump(),'reason':body.reason}));db.commit();return {'id':key,'role':target.role,'jurisdictions':target.jurisdictions}
@router.post('/admin/access/invitations')
def invite(body:Invitation,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['system_admin']);code=secrets.token_urlsafe(36)
    db.add(Record(kind='invitation',key=hashlib.sha256(code.encode()).hexdigest(),payload={**body.model_dump(),'email':body.email.lower(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(),'actor':u.id}))
    db.add(Record(kind='audit',key=uid(),payload={'action':'create_invitation','actor':u.id,'role':body.role,'jurisdictions':body.jurisdictions}));db.commit()
    return {'invitation_code':code,'expires_in_days':7,'email_sent':False}
@router.post('/access/redeem')
def redeem(body:Redeem,u:User=Depends(current),db:Session=Depends(session)):
    r=db.scalar(select(Record).where(Record.kind=='invitation',Record.key==hashlib.sha256(body.code.encode()).hexdigest()))
    if not r or r.payload['email']!=u.email.lower() or r.payload['expires_at']<now():raise HTTPException(404,'Invitation unavailable')
    from .config import settings
    if settings.auth_mode=='neon' and u.preferences.get('email_verified') is not True:raise HTTPException(403,'Verified provider email required')
    u.role=r.payload['role'];u.jurisdictions=r.payload['jurisdictions'];db.add(Record(kind='audit',key=uid(),payload={'action':'redeem_invitation','actor':u.id,'role':u.role}));db.delete(r);db.commit();return {'role':u.role,'jurisdictions':u.jurisdictions}
@router.get('/admin/villages/{key}/geography')
def geography(key:str,u:User=Depends(current),db:Session=Depends(session)):
    from .main import village,latest,raw
    require(u,['admin','system_admin']);v=village(db,key)
    if not scoped(u,v.jurisdiction):raise HTTPException(403,'Outside jurisdiction')
    r=latest(db,'geography',key);return {'village':raw(v),'geography':raw(r) if r else None}
@router.post('/admin/villages/{key}/geography')
def update_geography(key:str,body:GeographicUpdate,u:User=Depends(current),db:Session=Depends(session)):
    from .main import village,latest,raw
    require(u,['admin','system_admin']);v=village(db,key)
    if not scoped(u,v.jurisdiction):raise HTTPException(403,'Outside jurisdiction')
    old=latest(db,'geography',key)
    if body.expected_version!=(old.version if old else 0):raise HTTPException(409,'Geography version conflict')
    if body.boundary and body.boundary.get('type') not in ['Polygon','MultiPolygon']:raise HTTPException(422,'GeoJSON polygon required')
    r=Record(kind='geography',key=key,version=body.expected_version+1,payload={**body.model_dump(),'reviewer':u.id,'jurisdiction':v.jurisdiction});db.add(r)
    if body.latitude is not None:v.latitude=body.latitude
    if body.longitude is not None:v.longitude=body.longitude
    if body.boundary and db.bind.dialect.name=='postgresql':
        import json
        from sqlalchemy import text
        db.execute(text('UPDATE villages SET boundary=ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)) WHERE id=:id'),{'geometry':json.dumps(body.boundary),'id':key})
    db.add(Record(kind='audit',key=uid(),payload={'action':'geography_version','village_id':key,'actor':u.id,'reason':body.reason}));db.commit();return raw(r)
@router.get('/villages/{key}/map')
def public_map(key:str,u:User=Depends(current),db:Session=Depends(session)):
    from .main import village,latest
    v=village(db,key);r=latest(db,'geography',key)
    return {'type':'FeatureCollection','features':[{'type':'Feature','geometry':r.payload.get('boundary') if r and r.payload.get('boundary') else {'type':'Point','coordinates':[v.longitude,v.latitude]} if v.latitude is not None and v.longitude is not None else None,'properties':{'id':v.id,'name':v.name,'source':r.payload['source'] if r else v.provenance.get('source'),'boundary_available':bool(r and r.payload.get('boundary'))}}]}
@router.post('/admin/notices')
def create_notice(body:Notice,u:User=Depends(current),db:Session=Depends(session)):
    from .main import village,raw
    require(u,['admin','system_admin']);v=village(db,body.village_id)
    if not scoped(u,v.jurisdiction):raise HTTPException(403,'Outside jurisdiction')
    if body.valid_until<body.source_date:raise HTTPException(422,'Invalid notice dates')
    r=Record(kind='notice',key=uid(),payload={**body.model_dump(mode='json'),'reviewer':u.id,'jurisdiction':v.jurisdiction,'eligibility_verified':False});db.add(r);db.commit();return raw(r)
@router.get('/notices')
def notices(village_id:str,u:User=Depends(current),db:Session=Depends(session)):
    return [{'id':r.id,**r.payload} for r in db.scalars(select(Record).where(Record.kind=='notice')) if r.payload['village_id']==village_id and r.payload['valid_until']>=date.today().isoformat()]
@router.post('/admin/supply-sources')
def supply_source(body:SupplySource,u:User=Depends(current),db:Session=Depends(session)):
    from .main import latest,raw
    require(u,['system_admin']);old=latest(db,'supply_source',body.source_id)
    r=Record(kind='supply_source',key=body.source_id,version=old.version+1 if old else 1,payload={**body.model_dump(mode='json'),'reviewer':u.id,'units':'litres/day'});db.add(r);db.commit();return raw(r)
@router.post('/admin/villages/{key}/supply')
def allocation(key:str,body:SupplyAllocation,u:User=Depends(current),db:Session=Depends(session)):
    from .main import latest,village,raw
    require(u,['admin','system_admin']);v=village(db,key)
    if not scoped(u,v.jurisdiction):raise HTTPException(403,'Outside jurisdiction')
    source=latest(db,'supply_source',body.source_id)
    if not source or source.payload['valid_until']<date.today().isoformat():raise HTTPException(422,'A reviewed current supply source is required')
    if body.opening_storage_litres>body.storage_capacity_litres:raise HTTPException(422,'Opening storage exceeds capacity')
    if body.valid_until.isoformat()>source.payload['valid_until']:raise HTTPException(422,'Allocation cannot outlive source evidence')
    # Lock the common source to serialize cross-village allocation checks on PostgreSQL.
    db.scalar(select(Record).where(Record.id==source.id).with_for_update())
    current={}
    for r in db.scalars(select(Record).where(Record.kind=='supply').order_by(Record.version)):
        if r.payload['source_id']==body.source_id and r.payload['valid_until']>=date.today().isoformat():current[r.key]=r
    target=key+':'+body.sector
    used=sum(r.payload['litres_per_day'] for k,r in current.items() if k!=target)
    if used+body.litres_per_day>source.payload['yield_litres_per_day']:raise HTTPException(422,'Shared source allocations exceed reviewed yield')
    old=latest(db,'supply',target);r=Record(kind='supply',key=target,version=old.version+1 if old else 1,payload={**body.model_dump(mode='json'),'source_record_id':source.id,'reviewer':u.id,'village_id':key,'units':'litres/day','status':'reviewed_supply_scenario'});db.add(r);db.commit();return raw(r)
@router.post('/admin/ingestion-runs')
def ingestion(body:Ingest,u:User=Depends(current),db:Session=Depends(session)):
    from .main import enqueue,village,raw
    from .planning import weather_grid
    require(u,['system_admin']);payload=body.model_dump();kind=body.source+'_ingest'
    if body.source=='villages' and (not body.district_code or not body.district_code.isdigit() or len(body.district_code)!=3):raise HTTPException(422,'An explicit three-digit official district code is required')
    if body.source=='weather':
        if not body.village_id:raise HTTPException(422,'Village required')
        v=village(db,body.village_id);grid=weather_grid(v.latitude,v.longitude)
        if not grid:raise HTTPException(422,'Reviewed village coordinates unavailable')
        lat,lon=map(float,grid.split(':'));payload={'grid_id':grid,'latitude':lat,'longitude':lon}
    job=enqueue(db,kind+':'+uid(),kind,payload);db.commit();return raw(job)
@router.get('/admin/models/{key}/metrics')
def model_metrics(key:str,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin']);r=db.get(Record,key)
    if not r or r.kind!='model':raise HTTPException(404,'Model not found')
    return {'model_id':key,'approved':r.payload.get('approved',False),'metrics':r.payload.get('metrics'),'evaluations':r.payload.get('evaluations'),'release_blockers':r.payload.get('release_blockers',[])}
@router.post('/admin/models/{key}/release')
def release_model(key:str,body:Release,u:User=Depends(current),db:Session=Depends(session)):
    from pathlib import Path
    from .config import settings
    from ..worker.model import ApprovedModel
    from .main import latest,raw
    require(u,['system_admin']);r=db.get(Record,key)
    if not r or r.kind!='model':raise HTTPException(404,'Model not found')
    if r.payload.get('sha256')!=body.sha256:raise HTTPException(409,'Artifact changed; review exact hash')
    candidate={**r.payload,'approved':True,'release_actor':u.id,'release_reason':body.reason}
    root=Path(settings.model_artifact_root).resolve();artifact=(root/candidate.get('artifact','')).resolve()
    if not artifact.is_relative_to(root):raise HTTPException(422,'Artifact path outside model root')
    try:ApprovedModel(artifact,candidate)
    except (ValueError,OSError,KeyError) as e:raise HTTPException(422,'Model cannot be released: '+str(e))
    old=latest(db,'model',r.key);new=Record(kind='model',key=r.key,version=old.version+1,payload=candidate);db.add(new);db.add(Record(kind='audit',key=uid(),payload={'actor':u.id,'action':'model_release','sha256':body.sha256,'reason':body.reason}));db.commit();return raw(new)
@router.get('/admin/quality')
def quality(u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin'])
    q=select(Complaint)
    if u.role!='system_admin':q=q.where(Complaint.jurisdiction.in_(u.jurisdictions))
    complaints=list(db.scalars(q));ids=[c.id for c in complaints];events=list(db.scalars(select(Event).where(Event.complaint_id.in_(ids))))
    durations=[]
    for c in complaints:
        accepted=next((e for e in events if e.complaint_id==c.id and e.kind=='review:accepted'),None)
        if accepted:durations.append((datetime.fromisoformat(accepted.created_at)-datetime.fromisoformat(c.created_at)).total_seconds())
    traces=list(db.scalars(select(Record).where(Record.kind=='ai_trace')))
    return {'complaints_in_scope':len(complaints),'average_review_seconds':sum(durations)/len(durations) if durations else None,'official_publication':'transactional_on_acceptance','resolution_count':sum(c.service_status=='resolved' for c in complaints),'ai_requests':len(traces),'ai_failures':sum(r.payload.get('status')!='ok' for r in traces),'ai_traces':[{'id':r.id,'created_at':r.created_at,**r.payload} for r in traces[-100:]],'water_saved_litres':None}
