import hashlib
import hmac
import json
import time
from datetime import date
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from .config import settings
from .db import session, User, Village, Farm, Complaint, Event, Job, Record, ProviderMessage, now, uid
from .auth import current, require, scoped, local_enabled, token, hash_password, verify_password
from .schemas import Credentials, ComplaintInput, Review, Action, Message, FarmInput, BaselineInput, PlanInput, AssistantInput, UploadInput, EconomicsInput, ValidationResponse
from .calculations import irrigation, budget
from .security import limit

app = FastAPI(title='JalSathi API', version='0.1.0', description='Officials actions are demonstration records, not government service actions.',responses={422:{'model':ValidationResponse,'description':'Invalid input; submitted values are omitted.'}})
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(','), allow_credentials=True, allow_methods=['GET','POST','PATCH','PUT','DELETE'], allow_headers=['Authorization','Content-Type','Idempotency-Key'])
P = '/api/v1'

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    # Pydantic's default response includes submitted input (including passwords).
    # Return field names and safe validation messages without those values.
    errors=[{'field':'.'.join(str(part) for part in item['loc'] if part not in ('body','query','path')),'message':item['msg'].removeprefix('Value error, '),'type':item['type']} for item in exc.errors()]
    return JSONResponse(status_code=422,content={'detail':'Please check the form fields.','errors':errors})

@app.middleware('http')
async def limit_account_endpoints(request:Request,call_next):
    if request.method=='POST' and request.url.path in [P+'/auth/login',P+'/auth/register',P+'/auth/recovery']:
        # Use the actual peer. Never trust client-supplied X-Forwarded-For without a trusted proxy.
        provider=app.dependency_overrides.get(session,session);generator=provider();db=next(generator)
        try:
            limit(db,'account-ip:'+(request.client.host if request.client else 'unknown'),30,60)
        except HTTPException as e:return JSONResponse(status_code=e.status_code,content={'detail':e.detail},headers=e.headers)
        finally:generator.close()
    return await call_next(request)

def horizon(days:int=Query(7)):
    if days not in (7,15): raise HTTPException(422,'Horizon must be 7 or 15 days')
    return days

@app.exception_handler(StaleDataError)
async def stale(request, exc): return JSONResponse(status_code=409, content={'detail': 'Record changed; refresh before retrying'})
@app.exception_handler(IntegrityError)
async def conflict(request, exc): return JSONResponse(status_code=409, content={'detail': 'Concurrent or duplicate operation; refresh and retry'})

def rows(db, cls, *where): return list(db.scalars(select(cls).where(*where)))
def raw(obj): return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
def safe_job(job): return {k:raw(job)[k] for k in ['id','kind','status','attempts','available_at','error']}
def village(db, key):
    v = db.get(Village, key)
    if not v: raise HTTPException(404, 'Village not found; import an official directory first')
    return v
def event(db, complaint, actor, kind, note):
    db.add(Event(complaint_id=complaint.id, actor_id=actor, kind=kind, note=note))
def enqueue(db, key, kind, payload):
    existing = db.scalar(select(Job).where(Job.key == key))
    if existing: return existing
    job = Job(id=uid(), key=key, kind=kind, payload=payload)
    try:
        with db.begin_nested():db.add(job);db.flush()
        return job
    except IntegrityError:
        return db.scalar(select(Job).where(Job.key==key))
def latest(db, kind, key):
    return db.scalar(select(Record).where(Record.kind == kind, Record.key == key).order_by(Record.version.desc()).limit(1))
def visible(c, user):
    if user.role in ['admin','system_admin']: return scoped(user, c.jurisdiction)
    if user.role == 'official': return c.review_status == 'accepted' and c.publishable and scoped(user,c.jurisdiction)
    return user.id == c.reporter_id
def get_complaint(db, key, user):
    c = db.get(Complaint,key)
    if not c or not visible(c,user): raise HTTPException(404,'Complaint not found')
    return c
def detail(db,c,user):
    data = raw(c)
    events = rows(db, Event, Event.complaint_id == c.id)
    events.sort(key=lambda x:x.created_at)
    if user.role == 'official':
        data = {k:data[k] for k in ['id','description','village_id','category','review_status','service_status','jurisdiction','version','created_at','admin_note']}
        events = [e for e in events if e.kind.startswith('service:')]
        data['timeline'] = [{k:raw(e)[k] for k in ['kind','note','created_at']} for e in events]
        data['demo'] = True
    else: data['timeline'] = [raw(e) for e in events]
    return data
def check_version(c, expected):
    if c.version != expected: raise HTTPException(409, 'Version conflict; refresh before retrying')

@app.get('/health')
def health(): return {'status':'ok','demo_government_connection':False}
@app.post(P+'/auth/register')
async def register(body: Credentials, db: Session=Depends(session)):
    if settings.auth_mode=='neon':
        from .neon_auth import provider_login
        if not settings.allow_external_send:raise HTTPException(409,'Enable external account email delivery before Neon signup')
        return await provider_login(body,db,signup=True)
    local_enabled()
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'An account with this email already exists. Sign in instead.')
    u=User(email=email,password_hash=hash_password(body.password),role='farmer',jurisdictions=[])
    db.add(u)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'An account with this email already exists. Sign in instead.')
    return {'access_token':token(u),'token_type':'bearer'}
@app.post(P+'/auth/login')
async def login(body: Credentials, db: Session=Depends(session)):
    if settings.auth_mode=='neon':
        from .neon_auth import provider_login
        limit(db,'login:'+body.email.strip().lower(),10,60)
        return await provider_login(body,db)
    local_enabled()
    limit(db,'login:'+body.email.strip().lower(),10,60)
    u=db.scalar(select(User).where(User.email==body.email.strip().lower()))
    if not u or not verify_password(body.password,u.password_hash): raise HTTPException(401,'Invalid credentials')
    return {'access_token':token(u),'token_type':'bearer'}
@app.get(P+'/me')
def me(u: User=Depends(current)): return {'id':u.id,'email':u.email,'role':u.role,'jurisdictions':u.jurisdictions,'preferences':u.preferences}
@app.patch(P+'/me')
def preferences(body: dict, u: User=Depends(current),db:Session=Depends(session)):
    allowed={'language','notifications','consent','village_id'}
    if set(body)-allowed: raise HTTPException(422,'Unsupported preference')
    if body.get('village_id'): village(db,body['village_id'])
    u.preferences={**u.preferences,**body};db.commit();return u.preferences
@app.get(P+'/villages')
def villages(q:str='',limit:int=Query(100,ge=1,le=500),u:User=Depends(current),db:Session=Depends(session)):
    statement=select(Village).where(or_(Village.name.ilike('%'+q+'%'),Village.district.ilike('%'+q+'%'),Village.id==q)).limit(limit)
    return [raw(v) for v in db.scalars(statement)]

@app.post(P+'/complaints',status_code=201)
def submit(body:ComplaintInput,idempotency_key:str=Header(min_length=8,max_length=150),u:User=Depends(current),db:Session=Depends(session)):
    require(u,['farmer'])
    limit(db,'submit:'+u.id,20,3600)
    v=village(db,body.village_id)
    digest=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    old=db.scalar(select(Complaint).where(Complaint.reporter_id==u.id,Complaint.idempotency_key==idempotency_key))
    if old:
        if old.request_hash!=digest: raise HTTPException(409,'Idempotency key reused for different content')
        return detail(db,old,u)
    c=Complaint(id=uid(),reporter_id=u.id,idempotency_key=idempotency_key,request_hash=digest,original=body.description,description=body.description,village_id=v.id,jurisdiction=v.jurisdiction,category=body.category)
    db.add(c);event(db,c,u.id,'submitted','Report submitted by app with consent')
    enqueue(db,'complaint:'+c.id,'audit_delivery',{'complaint_id':c.id})
    db.commit();return detail(db,c,u)
@app.get(P+'/complaints/mine')
def mine(u:User=Depends(current),db:Session=Depends(session)):
    return [detail(db,c,u) for c in rows(db,Complaint,Complaint.reporter_id==u.id)]
@app.get(P+'/complaints/{key}')
def complaint(key:str,u:User=Depends(current),db:Session=Depends(session)): return detail(db,get_complaint(db,key,u),u)
@app.post(P+'/complaints/{key}/messages')
def message(key:str,body:Message,u:User=Depends(current),db:Session=Depends(session)):
    c=get_complaint(db,key,u)
    if u.role=='official': raise HTTPException(403,'Use demonstration action endpoint')
    if body.village_id and body.village_id!=c.village_id:
        if c.review_status not in ['needs_information','awaiting_location','submitted']: raise HTTPException(409,'Cannot reroute accepted report')
        v=village(db,body.village_id);c.village_id=v.id;c.jurisdiction=v.jurisdiction
        if u.role in ['admin','system_admin'] and not scoped(u,v.jurisdiction):raise HTTPException(403,'Location outside review jurisdiction')
    if c.reporter_id==u.id and c.review_status in ['needs_information','awaiting_location'] and c.village_id: c.review_status='submitted'
    event(db,c,u.id,'message',body.text);c.version+=1;db.commit();return detail(db,c,u)
@app.get(P+'/admin/complaints')
def inbox(status:str|None=None,category:str|None=None,channel:str|None=None,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin'])
    query=select(Complaint)
    if u.role!='system_admin': query=query.where(Complaint.jurisdiction.in_(u.jurisdictions))
    if status: query=query.where(Complaint.review_status==status)
    if category: query=query.where(Complaint.category==category)
    if channel: query=query.where(Complaint.channel==channel)
    return [detail(db,c,u) for c in db.scalars(query)]
@app.post(P+'/admin/complaints/{key}/review')
def review(key:str,body:Review,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin']);c=get_complaint(db,key,u);check_version(c,body.expected_version)
    allowed={'submitted':{'accepted','rejected','needs_information','duplicate'},'awaiting_location':{'needs_information','rejected','submitted'},'needs_information':{'submitted','rejected','duplicate','accepted'},'accepted':{'withdrawn','needs_information'},'rejected':{'submitted'},'duplicate':{'submitted'},'withdrawn':{'submitted'}}
    if body.status not in allowed.get(c.review_status,set()): raise HTTPException(409,'Invalid review transition')
    if body.status=='accepted':
        if not c.village_id: raise HTTPException(422,'Verified village required')
        v=village(db,c.village_id)
        if body.jurisdiction!=v.jurisdiction or not scoped(u,body.jurisdiction): raise HTTPException(403,'Routing must match authorized village jurisdiction')
        if not body.sanitized_description: raise HTTPException(422,'Reviewed sanitized description required for publication')
        c.description=body.sanitized_description;c.jurisdiction=body.jurisdiction
    if body.status=='submitted' and not c.village_id: raise HTTPException(422,'Location still incomplete')
    if body.status=='duplicate':
        target=get_complaint(db,body.duplicate_of,u) if body.duplicate_of else None
        if not target or target.id==c.id or target.review_status=='duplicate': raise HTTPException(422,'Valid canonical complaint required')
        c.duplicate_of=target.id
    c.review_status=body.status;c.publishable=body.status=='accepted';c.admin_note=body.reason
    event(db,c,u.id,'review:'+body.status,body.reason)
    enqueue(db,f'review:{c.id}:{c.version}', 'audit_delivery',{'complaint_id':c.id})
    db.commit();return detail(db,c,u)
@app.get(P+'/official/complaints')
def official_queue(u:User=Depends(current),db:Session=Depends(session)):
    require(u,['official'])
    return [detail(db,c,u) for c in rows(db,Complaint,Complaint.review_status=='accepted',Complaint.publishable==True,Complaint.jurisdiction.in_(u.jurisdictions))]
@app.get(P+'/official/complaints/{key}')
def official_detail(key:str,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['official']);return detail(db,get_complaint(db,key,u),u)
@app.post(P+'/official/complaints/{key}/actions')
def action(key:str,body:Action,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['official','admin','system_admin']);c=get_complaint(db,key,u);check_version(c,body.expected_version)
    if not c.publishable or c.review_status!='accepted': raise HTTPException(404,'Accepted complaint not found')
    allowed={'pending_acknowledgement':{'acknowledged'},'acknowledged':{'assigned','in_progress','needs_clarification'},'assigned':{'in_progress','needs_clarification'},'in_progress':{'resolved','needs_clarification'},'needs_clarification':{'in_progress','assigned'},'resolved':{'reopened'},'reopened':{'assigned','in_progress'}}
    if body.status not in allowed.get(c.service_status,set()): raise HTTPException(409,'Invalid service transition')
    if body.status=='reopened': require(u,['admin','system_admin'])
    c.service_status=body.status;event(db,c,u.id,'service:'+body.status,body.note)
    enqueue(db,f'action:{c.id}:{c.version}','audit_delivery',{'complaint_id':c.id});db.commit();return detail(db,c,u)

@app.get(P+'/farms')
def farms(u:User=Depends(current),db:Session=Depends(session)): return [raw(f) for f in rows(db,Farm,Farm.owner_id==u.id)]
@app.post(P+'/farms')
def create_farm(body:FarmInput,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['farmer']);village(db,body.village_id)
    f=Farm(owner_id=u.id,village_id=body.village_id,details=body.model_dump(mode='json'));db.add(f);db.commit();return raw(f)
@app.patch(P+'/farms/{key}')
def edit_farm(key:str,body:FarmInput,u:User=Depends(current),db:Session=Depends(session)):
    f=db.get(Farm,key)
    if not f or f.owner_id!=u.id: raise HTTPException(404,'Farm not found')
    village(db,body.village_id);f.details=body.model_dump(mode='json');f.village_id=body.village_id;db.commit();return raw(f)
@app.post(P+'/calculations/irrigation')
def scenario(body:PlanInput,u:User=Depends(current)):
    return {'status':'user_assumption_scenario','units':'litres',**irrigation(body.area_ha,body.et0,body.kc,body.effective_rain,body.efficiency,body.soil_contribution,body.cap_litres)}
@app.post(P+'/calculations/economics')
def economics(body:EconomicsInput,u:User=Depends(current)):
    revenue=body.yield_kg*body.price_per_kg
    return {'status':'user_assumption_scenario','currency':'INR','revenue':revenue,'margin':revenue-body.cultivation_cost-body.transport_cost,'inputs':body.model_dump(),'warning':'Assumed price and yield are not harvest forecasts'}
@app.get(P+'/farms/{key}/irrigation-plan')
def farm_plan(key:str,days:int=Depends(horizon),u:User=Depends(current),db:Session=Depends(session)):
    f=db.get(Farm,key)
    if not f or f.owner_id!=u.id: raise HTTPException(404,'Farm not found')
    from .planning import weather_grid,farm_plan as calculate_plan
    v=village(db,f.village_id);grid=weather_grid(v.latitude,v.longitude)
    w=latest(db,'weather',grid) if grid else None;a=latest(db,'agronomy',f.details['crop'].strip().lower())
    if not w or not a:return {'status':'unavailable','days':days,'reason':'Reviewed crop-stage coefficients, efficiency and dated grid weather required','farm':raw(f)}
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(w.created_at)).total_seconds()
    if age>172800:return {'status':'unavailable','reason':'Weather inputs are stale','source_date':w.created_at}
    try:result=calculate_plan(f.details,w.payload,a.payload,days,datetime.now(ZoneInfo('Asia/Kolkata')).date())
    except (ValueError,KeyError,TypeError) as e:return {'status':'unavailable','reason':str(e)}
    return {**result,'farm_id':f.id,'weather_record_id':w.id,'weather_retrieved_at':w.created_at,'weather_grid_id':grid,'weather_source':w.payload.get('source'),'agronomy_record_id':a.id,'agronomy_source':a.payload.get('source')}

def baseline_data(db,key,days,*,records=None,issue=None):
    start=issue or datetime.now(ZoneInfo('Asia/Kolkata')).date();today=start.isoformat();end=(start+timedelta(days=days)).isoformat();components=[]
    def find(kind, record_key):
        return latest(db, kind, record_key) if records is None else records.get((kind, record_key))
    for sector in ['household','agriculture','livestock','other']:
        r=find('baseline',key+':'+sector)
        if r and r.payload['valid_from']<=today and r.payload['valid_to']>=end:
            supply=find('supply',key+':'+sector);inputs=None
            if supply and supply.payload['valid_until']>=end:
                source=find('supply_source',supply.payload['source_id'])
                if source and source.id==supply.payload['source_record_id'] and source.payload['valid_until']>=end:inputs=supply.payload
            calculated=budget([r.payload['litres_per_day']]*days,[inputs['litres_per_day']]*days if inputs else None,opening=inputs['opening_storage_litres'] if inputs else 0,capacity=inputs['storage_capacity_litres'] if inputs else None,delivery_limit=inputs['delivery_limit_litres_per_day'] if inputs else None)
            components.append({'sector':sector,'baseline_id':r.id,'version':r.version,'baseline_recorded_at':r.created_at,'reference_period':r.payload['reference_start']+' – '+r.payload['reference_end'],**calculated,'supply_record_id':supply.id if inputs else None,'supply_assumptions':inputs['assumptions'] if inputs else None,'storage_partition_verified':inputs.get('storage_partition_verified',False) if inputs else False,'net_supply_after_losses':inputs.get('net_supply_after_losses',False) if inputs else False,'opening_storage_litres':inputs['opening_storage_litres'] if inputs else None,'assumptions':r.payload['assumptions'],'source':r.payload['source']})
    comparable=bool(components) and all(c['unmet_litres'] is not None for c in components)
    return {'status':'reviewed_supply_scenario' if comparable else 'demand_only' if components else 'unavailable','days':days,'components':components,'shortage_litres':sum(c['unmet_litres'] for c in components) if comparable else None,'reason':'Scenario for listed sectors only; future inflow uses reviewed allocation assumptions' if comparable else 'Sector-matched verified supply unavailable; missing sectors are not zero','sectors_covered':[c['sector'] for c in components]}
@app.get(P+'/villages/{key}/water-budget')
def water_budget(key:str,days:int=Depends(horizon),u:User=Depends(current),db:Session=Depends(session)):
    village(db,key);return baseline_data(db,key,days)
@app.get(P+'/villages/{key}/outlook')
def outlook(key:str,days:int=Depends(horizon),u:User=Depends(current),db:Session=Depends(session)):
    village(db,key);r=latest(db,'forecast',key)
    if not r: return {'status':'unavailable','days':days,'reason':'No approved model and fresh compatible observations','issued_at':None}
    age_hours=(datetime.now(timezone.utc)-datetime.fromisoformat(r.created_at)).total_seconds()/3600
    return {'snapshot_id':r.id,'issued_at':r.created_at,**r.payload,'freshness':'stale' if age_hours>26 else 'current','age_hours':round(age_hours,1),'requested_days':days,'daily':r.payload.get('daily',[])[:days]}
@app.get(P+'/admin/villages/{key}/baselines')
def baselines(key:str,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin']);v=village(db,key)
    if not scoped(u,v.jurisdiction): raise HTTPException(403,'Outside jurisdiction')
    return [raw(r) for r in db.scalars(select(Record).where(Record.kind=='baseline',Record.key.like(key+':%')))]

@app.get(P+'/admin/villages/{key}/research-predictions')
def research_predictions(key:str,days:int=Depends(horizon),u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin'])
    v=village(db,key)
    if not scoped(u,v.jurisdiction):raise HTTPException(403,'Outside jurisdiction')
    r=latest(db,'research_predictions',v.jurisdiction)
    if not r:return {'status':'unavailable','reason':'No historical station predictions for this district','samples':[]}
    experimental=latest(db,'experimental_forecasts',v.jurisdiction)
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
    preview=None
    if experimental and experimental.payload.get('forecast_date')==today:
        preview={**experimental.payload,'samples':[{**s,'horizons':s['horizons'][:days]} for s in experimental.payload['samples']]}
    return {**r.payload,'village_name':v.name,'district_name':v.district,
            'experimental_current':preview,
            'samples':[{**s,'horizons':s['horizons'][:days]} for s in r.payload['samples']]}
@app.post(P+'/admin/villages/{key}/baselines')
def baseline(key:str,body:BaselineInput,u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin']);v=village(db,key)
    if not scoped(u,v.jurisdiction): raise HTTPException(403,'Outside jurisdiction')
    if body.reference_start>body.reference_end or body.valid_from>body.valid_to: raise HTTPException(422,'Invalid reference or validity dates')
    old=latest(db,'baseline',key+':'+body.sector)
    r=Record(kind='baseline',key=key+':'+body.sector,version=old.version+1 if old else 1,payload={**body.model_dump(mode='json'),'reviewer':u.id,'units':'litres/day'})
    db.add(r);db.add(Record(kind='audit',key=uid(),payload={'actor':u.id,'action':'baseline_version','village_id':key,'sector':body.sector}));db.commit();return raw(r)

@app.get(P+'/markets')
def markets(market:str|None=None,variety:str|None=None,quote_date:str|None=None,units:str|None=None,u:User=Depends(current),db:Session=Depends(session)):
    data=rows(db,Record,Record.kind=='market')
    for key,value in [('market',market),('variety',variety),('source_date',quote_date),('units',units)]:
        if value:data=[r for r in data if str(r.payload.get(key,''))==value]
    return {'status':'available' if data else 'unavailable','quotes':[raw(r) for r in data],'source':'https://www.msamb.com/ApmcDetail/APMCPriceInformation','reason':None if data else 'No verified dated market quotes imported'}
@app.get(P+'/schemes')
def schemes(u:User=Depends(current),db:Session=Depends(session)):
    return {'status':'official_links_only','eligibility_verified':False,'documents':[raw(r) for r in rows(db,Record,Record.kind=='document')],'links':[{'title':'MahaDBT Farmer','url':'https://mahadbt.maharashtra.gov.in/Farmer/AgriLogin/AgriLogin'},{'title':'GSDA resolutions','url':'https://gsda.maharashtra.gov.in/en-important-government-resolutions/'}]}
@app.post(P+'/assistant/messages')
async def assistant(body:AssistantInput,u:User=Depends(current),db:Session=Depends(session)):
    limit(db,'assistant:'+u.id,10,60)
    village(db,body.village_id)
    from .integrations import explain
    from .retrieval import retrieve_documents
    passages=retrieve_documents(db,body.question)
    from .supply_outlook import supply_outlook
    supply=supply_outlook(body.village_id,u,db)
    selected=next(r for r in supply['outlooks'] if r['days']==body.days)
    evidence={'budget':baseline_data(db,body.village_id,body.days),'outlook':{**selected,'target':'water_supply_sufficiency','status':'unavailable' if selected['status']=='insufficient_data' else selected['status'],'assumptions':supply['assumptions']},'official_documents':passages}
    result=await explain(body,evidence)
    db.add(Record(kind='ai_trace',key=uid(),payload={k:v for k,v in result.items() if k not in ['text','evidence']}));db.commit();return result

@app.get(P+'/admin/operations')
def operations(u:User=Depends(current),db:Session=Depends(session)):
    require(u,['admin','system_admin'])
    return {'jobs':[safe_job(j) for j in rows(db,Job)],'models':[raw(r) for r in rows(db,Record,Record.kind=='model')],'sources':[raw(r) for r in rows(db,Record,Record.kind=='source_fetch')],'audit':[raw(r) for r in rows(db,Record,Record.kind=='audit') if u.role=='system_admin' or scoped(u,(db.get(Village,r.payload.get('village_id')) or type('V',(),{'jurisdiction':None})()).jurisdiction)],'flow':['Sources','Identity / units / freshness validation','Location-specific features','Approved model','Sector budgets','Published snapshot'],'integrations':{'neon_auth':'configured_unverified' if settings.neon_auth_jwks_url else 'unavailable','storage':'configured_unverified' if settings.storage_bucket else 'unavailable','gemini':'configured_unverified' if settings.gemini_api_key else 'unavailable','whatsapp':'configured_unverified' if settings.whatsapp_app_secret else 'unavailable'}}
@app.get(P+'/admin/models')
@app.get(P+'/admin/sources')
@app.get(P+'/admin/forecast-runs')
@app.get(P+'/admin/audit')
def diagnostics(request:Request,u:User=Depends(current),db:Session=Depends(session)):
    resource=request.url.path.rsplit('/',1)[1]
    return operations(u,db)[{'forecast-runs':'jobs'}.get(resource,resource)]
@app.post(P+'/admin/forecast-runs')
def run_forecast(idempotency_key:str=Header(min_length=8),u:User=Depends(current),db:Session=Depends(session)):
    require(u,['system_admin']);j=enqueue(db,'forecast:'+idempotency_key,'daily_inference',{'date':datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat(),'run_key':idempotency_key});db.commit();return raw(j)

@app.get(P+'/webhooks/whatsapp')
def verify_webhook(request:Request):
    q=request.query_params
    if not settings.whatsapp_verify_token or q.get('hub.mode')!='subscribe' or not hmac.compare_digest(q.get('hub.verify_token',''),settings.whatsapp_verify_token): raise HTTPException(403,'Verification failed')
    return PlainTextResponse(q.get('hub.challenge',''))
@app.post(P+'/webhooks/whatsapp')
async def whatsapp(request:Request,db:Session=Depends(session)):
    payload=await request.body()
    if len(payload)>1048576: raise HTTPException(413,'Webhook too large')
    signature='sha256='+hmac.new(settings.whatsapp_app_secret.encode(),payload,hashlib.sha256).hexdigest()
    if not settings.whatsapp_app_secret or not hmac.compare_digest(signature,request.headers.get('x-hub-signature-256','')): raise HTTPException(403,'Invalid signature')
    try: data=json.loads(payload)
    except ValueError: raise HTTPException(400,'Invalid JSON')
    count=0
    for entry in data.get('entry',[]):
        for change in entry.get('changes',[]):
            value=change.get('value',{})
            if value.get('metadata',{}).get('phone_number_id')!=settings.whatsapp_phone_number_id: raise HTTPException(403,'Wrong business number')
            for msg in value.get('messages',[]):
                if not msg.get('id') or not msg.get('from'): continue
                if db.get(ProviderMessage,msg['id']): continue
                db.add(ProviderMessage(id=msg['id'],sender=msg['from'],payload=msg));enqueue(db,'wa:'+msg['id'],'whatsapp_intake',{'message_id':msg['id']});db.flush();count+=1
    db.commit();return {'received':count}

@app.post(P+'/uploads/presign')
def presign(body:UploadInput,u:User=Depends(current),db:Session=Depends(session)):
    from .attachments import create_upload
    return create_upload(body,u,db)

from .attachments import router as attachment_router
app.include_router(attachment_router)
from .neon_auth import router as auth_router
app.include_router(auth_router)
from .administration import router as administration_router
app.include_router(administration_router)
from .privacy import router as privacy_router
app.include_router(privacy_router)
from .water_map import router as water_map_router
app.include_router(water_map_router)
from .water_evidence import router as water_evidence_router
app.include_router(water_evidence_router)

from .supply_outlook import router as supply_outlook_router
app.include_router(supply_outlook_router)
