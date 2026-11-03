import argparse
import hashlib
import json
import time
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, or_, update
from services.api.db import Session, Job, ProviderMessage, Complaint, Event, Village, Record, uid, now
from services.api.main import enqueue, latest
from services.api.config import settings

def intake(db,payload):
    msg=db.get(ProviderMessage,payload['message_id'])
    sender='whatsapp:'+msg.sender
    text=msg.payload.get('text',{}).get('body','')
    if text.strip().upper() in ['SUBSCRIBE','UNSUBSCRIBE']:
        record_key=hashlib.sha256(msg.sender.encode()).hexdigest();old=latest(db,'whatsapp_consent',record_key)
        opt_in=text.strip().upper()=='SUBSCRIBE';db.add(Record(kind='whatsapp_consent',key=record_key,version=old.version+1 if old else 1,payload={'opt_in':opt_in,'provider_message_id':msg.id,'purpose':'complaint_status_updates'}))
        enqueue(db,'reply:'+msg.id,'whatsapp_reply',{'to':msg.sender,'text':'Status update consent saved: '+str(opt_in),'inbound_timestamp':msg.payload.get('timestamp'),'consent':'reply_to_consent_request'});return {'status':'consent_updated'}
    if text.upper().startswith('STATUS '):
        key=text.split(maxsplit=1)[1].strip();c=db.get(Complaint,key)
        reply=f'Ticket {c.id}: review={c.review_status}; service demo={c.service_status}' if c and c.reporter_id==sender else 'Ticket unavailable for this WhatsApp sender.'
        enqueue(db,'reply:'+msg.id,'whatsapp_reply',{'to':msg.sender,'text':reply,'inbound_timestamp':msg.payload.get('timestamp'),'consent':'reply_to_inbound_status_request'})
        return {'status':'status_request_processed','identity':'same_provider_sender_only'}
    # Explicit official ID is required; do not infer from a name or phone number.
    parts=text.split()
    village_id=next((p.split(':',1)[1] for p in parts if p.startswith('LGD:')),None)
    v=db.get(Village,village_id) if village_id else None
    existing=db.scalar(select(Complaint).where(Complaint.reporter_id==sender,Complaint.review_status.in_(['awaiting_location','needs_information'])).order_by(Complaint.created_at.desc()))
    if existing:
        c=existing
        if v:
            c.village_id=v.id;c.jurisdiction=v.jurisdiction;c.review_status='submitted'
        db.add(Event(complaint_id=c.id,actor_id=sender,kind='message',note=text or 'Unsupported media preserved for review'))
    else:
        c=Complaint(id=uid(),reporter_id=sender,idempotency_key=msg.id,request_hash=hashlib.sha256(json.dumps(msg.payload,sort_keys=True).encode()).hexdigest(),channel='whatsapp',original=text or json.dumps(msg.payload,ensure_ascii=False),description=text or 'Media report requires text and location review',category='other',village_id=v.id if v else None,jurisdiction=v.jurisdiction if v else None,review_status='submitted' if v and len(text)>=10 else 'awaiting_location')
        db.add(c);db.add(Event(complaint_id=c.id,actor_id=sender,kind='submitted',note='Original provider message retained; sender is not a verified landowner'))
    db.flush()
    reply=('तक्रार नोंदवली. Ticket: '+c.id) if c.review_status=='submitted' else ('कृपया गावाचा अधिकृत कोड LGD:<code>, जिल्हा आणि समस्येचे वर्णन पाठवा. Please provide the village code and details. Ticket: '+c.id)
    enqueue(db,'reply:'+msg.id,'whatsapp_reply',{'to':msg.sender,'text':reply,'inbound_timestamp':msg.payload.get('timestamp'),'consent':'reply_to_inbound_report'})
    return {'complaint_id':c.id,'status':c.review_status}

def send_reply(payload):
    if not settings.allow_external_send: return {'status':'blocked','reason':'External sending explicitly disabled'}
    if not all([settings.whatsapp_access_token,settings.whatsapp_phone_number_id,settings.whatsapp_api_version]): return {'status':'blocked','reason':'WhatsApp credentials unavailable'}
    outside=not payload.get('inbound_timestamp') or time.time()-float(payload['inbound_timestamp'])>86400
    if outside and not (payload.get('opt_in') is True and settings.whatsapp_status_template and settings.whatsapp_template_approved):return {'status':'blocked','reason':'Outside reply window; approved template and consent required'}
    body={'messaging_product':'whatsapp','to':payload['to'],'type':'template' if outside else 'text'}
    if outside:body['template']={'name':settings.whatsapp_status_template,'language':{'code':settings.whatsapp_template_language},'components':[{'type':'body','parameters':[{'type':'text','text':payload['text']}]}]}
    else:body['text']={'body':payload['text']}
    import httpx
    r=httpx.post(f'https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages',headers={'Authorization':'Bearer '+settings.whatsapp_access_token},json=body,timeout=30)
    r.raise_for_status();return {'status':'sent','provider_ids':[m['id'] for m in r.json().get('messages',[])]}

def daily_inference(db,payload):
    """Load once, batch supported locations, retain unsupported rows and reproducible lineage."""
    from pathlib import Path
    from services.worker.model import ApprovedModel
    from services.api.main import baseline_data
    started=time.perf_counter();count=0;supported=0;model=None;model_record=None;model_error='No approved compatible model';run_key=payload.get('run_key',payload['date'])
    candidates=list(db.scalars(select(Record).where(Record.kind=='model').order_by(Record.created_at.desc())))
    for candidate in candidates:
        if not candidate.payload.get('approved'):continue
        try:
            root=Path(settings.model_artifact_root).resolve();artifact=(root/candidate.payload['artifact']).resolve()
            if not artifact.is_relative_to(root):raise ValueError('Artifact outside approved root')
            model=ApprovedModel(artifact,candidate.payload);model_record=candidate;break
        except (ValueError,OSError,KeyError):model_error='Approved artifact unavailable or release gate failed'
    # Reuse latest baselines and preserve their exact version IDs in each snapshot.
    batch=[]
    def publish_batch():
        nonlocal count,supported
        valid=[]
        for v,old in batch:
            features=latest(db,'features',v.id) if model else None
            reason=model_error
            if model and features:
                p=features.payload
                try:
                    observed=datetime.fromisoformat(p['observed_at'].replace('Z','+00:00'))
                    issued=datetime.fromisoformat(p['issue_time'].replace('Z','+00:00'))
                    age=(datetime.now(timezone.utc)-observed).total_seconds()
                    if not 0<=age<=172800 or issued>datetime.now(timezone.utc) or observed>issued:raise ValueError('Stale or future input')
                    if p['feature_names']!=model.manifest['feature_names']:raise ValueError('Schema mismatch')
                    if p.get('station_id') is None or p.get('mapping_verified') is not True or not p.get('grid_id'):raise ValueError('Unverified source mapping')
                    valid.append((v,old,features));continue
                except (KeyError,ValueError,TypeError):reason='Freshness, issue-time, schema or verified mapping gate failed'
            elif model:reason='Location-specific features unavailable'
            db.add(Record(kind='forecast',key=v.id,version=old.version+1 if old else 1,payload={'status':'unavailable','run_key':run_key,'reason':reason,'daily':[],'model_id':model_record.id if model_record else None,'source_dates':[]}));count+=1
        if valid:
            try:
                predictions=model.predict([f.payload['values'] for _,_,f in valid],model.manifest['feature_names'])
                for (v,old,features),prediction in zip(valid,predictions):
                    issue=date.fromisoformat(payload['date'])
                    uncertainty=model.manifest.get('calibration_abs_error_quantile')
                    daily=[{'day':h+1,'date':(issue+timedelta(days=h+1)).isoformat(),'groundwater_depth_m_bgl':float(value),'interval_lower_m_bgl':float(value-uncertainty[h]) if uncertainty else None,'interval_upper_m_bgl':float(value+uncertainty[h]) if uncertainty else None} for h,value in enumerate(prediction)]
                    snapshot={'status':'available','run_key':run_key,'model_id':model_record.id,'feature_record_id':features.id,'station_id':features.payload['station_id'],'grid_id':features.payload['grid_id'],'source_dates':[features.payload['observed_at']],'resolution':'station_supported_not_village_measurement','daily':daily,'budget_7':baseline_data(db,v.id,7),'budget_15':baseline_data(db,v.id,15),'evaluation_metrics':model.manifest['metrics'],'confidence':None,'limitations':'Groundwater depth is not consumption or deliverable supply. Uncertainty metrics describe held-out evaluation, not a per-village guarantee.'}
                    db.add(Record(kind='forecast',key=v.id,version=old.version+1 if old else 1,payload=snapshot));count+=1;supported+=1
            except ValueError:
                for v,old,features in valid:
                    db.add(Record(kind='forecast',key=v.id,version=old.version+1 if old else 1,payload={'status':'unavailable','run_key':run_key,'reason':'Numerical feature/output validation failed','daily':[],'model_id':model_record.id}));count+=1
        db.flush();batch.clear()
    for v in db.scalars(select(Village).execution_options(yield_per=500)):
        old=latest(db,'forecast',v.id)
        if old and old.payload.get('run_key')==run_key:continue
        batch.append((v,old))
        if len(batch)>=500:publish_batch()
    if batch:publish_batch()
    return {'status':'completed' if supported==count and count else 'completed_with_unavailable_outputs','villages':count,'supported':supported,'total_seconds':time.perf_counter()-started,'training_performed':False}

def process_one():
    stamp=time.time()
    with Session() as db:
        query=select(Job).where(or_((Job.status=='pending') & (Job.available_at<=stamp),(Job.status=='running') & (Job.lease_until<stamp))).order_by(Job.available_at).limit(1)
        if db.bind.dialect.name=='postgresql': query=query.with_for_update(skip_locked=True)
        job=db.scalar(query)
        if not job: return False
        # Conditional claim supports multiple workers even on local SQLite.
        result=db.execute(update(Job).where(Job.id==job.id,Job.status==job.status,Job.lease_until==job.lease_until).values(status='running',lease_until=stamp+900,attempts=Job.attempts+1))
        if result.rowcount!=1: db.rollback();return True
        key=job.id;db.commit()
    with Session() as db:
        job=db.get(Job,key)
        try:
            if job.kind=='whatsapp_intake': result=intake(db,job.payload)
            elif job.kind=='whatsapp_reply': result=send_reply(job.payload)
            elif job.kind=='daily_inference': result=daily_inference(db,job.payload)
            elif job.kind=='audit_delivery':
                c=db.get(Complaint,job.payload['complaint_id'])
                if c and c.channel=='whatsapp':
                    phone=c.reporter_id.removeprefix('whatsapp:');messages=list(db.scalars(select(ProviderMessage).where(ProviderMessage.sender==phone).order_by(ProviderMessage.received_at.desc()).limit(1)))
                    consent=latest(db,'whatsapp_consent',hashlib.sha256(phone.encode()).hexdigest())
                    enqueue(db,'status:'+job.key,'whatsapp_reply',{'to':phone,'text':f'Ticket {c.id}: review {c.review_status}; service DEMO {c.service_status}.','inbound_timestamp':messages[0].payload.get('timestamp') if messages else None,'opt_in':bool(consent and consent.payload['opt_in'])})
                result={'status':'recorded','external_handoff':False}
            elif job.kind in ['schemes_ingest','msamb_ingest','agmarknet_ingest','villages_ingest']:
                from . import sources
                result=getattr(sources,job.kind.replace('_ingest',''))(db,job.payload)
            elif job.kind=='weather_ingest':
                import asyncio
                from services.api.integrations import fetch_weather
                result=asyncio.run(fetch_weather(job.payload['latitude'],job.payload['longitude']))
                old=latest(db,'weather',job.payload['grid_id'])
                db.add(Record(kind='weather',key=job.payload['grid_id'],version=old.version+1 if old else 1,payload=result))
                db.add(Record(kind='source_fetch',key=uid(),payload={'source':'Open-Meteo','retrieved_at':now(),'grid_id':job.payload['grid_id'],'units':result['units'],'date_range':result['daily']['time'],'status':'ok'}))
            else: raise ValueError('Unsupported job kind')
            job.result=result;job.status='blocked' if result.get('status')=='blocked' else 'completed';job.error=None;db.commit()
        except Exception as exc:
            db.rollback();job=db.get(Job,key)
            job.status='dead' if job.attempts>=5 else 'pending'
            job.available_at=time.time()+min(3600,2**job.attempts*10)
            # Never persist exception text containing provider URLs, credentials or report bodies.
            job.error=type(exc).__name__;db.commit()
            if job.kind.endswith('_ingest'):
                db.add(Record(kind='source_fetch',key=uid(),payload={'source':job.kind,'status':'failed','retrieved_at':now(),'error_class':type(exc).__name__}));db.commit()
    return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    scheduled=None
    while True:
        # Durable local-calendar run key. External weather refresh is an independent job.
        from zoneinfo import ZoneInfo
        run_date=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
        with Session() as db:
            if settings.enable_daily_ingestion and scheduled!=run_date:
                from services.api.planning import weather_grid
                seen=set()
                for v in db.scalars(select(Village)):
                    grid=weather_grid(v.latitude,v.longitude)
                    if grid and grid not in seen:
                        lat,lon=map(float,grid.split(':'));enqueue(db,'weather:'+grid+':'+run_date,'weather_ingest',{'grid_id':grid,'latitude':lat,'longitude':lon});seen.add(grid)
                enqueue(db,'schemes:'+run_date,'schemes_ingest',{})
                if settings.agmarknet_api_key:enqueue(db,'agmarknet:'+run_date,'agmarknet_ingest',{})
                scheduled=run_date
            enqueue(db,'scheduled-inference:'+run_date,'daily_inference',{'date':run_date});db.commit()
        worked=process_one()
        if args.once: break
        if not worked: time.sleep(2)
if __name__=='__main__': main()
