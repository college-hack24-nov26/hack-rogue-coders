import hashlib,io,warnings
from pathlib import Path
from PIL import Image,UnidentifiedImageError
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import session,Record,User,uid
from .auth import current,require
from .config import settings

router=APIRouter(prefix='/api/v1')
MAX_BYTES=5242880
Image.MAX_IMAGE_PIXELS=20000000

def local_path(key):
    if settings.storage_mode!='local' or settings.environment!='development':raise HTTPException(503,'Local private storage is development only')
    root=Path(settings.private_storage_root).resolve();path=(root/key).resolve()
    if not path.is_relative_to(root):raise HTTPException(400,'Invalid object key')
    return path
def put_bytes(key,data,content_type):
    if settings.storage_mode=='local':
        p=local_path(key);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    else:
        from .integrations import storage
        storage().put_object(Bucket=settings.storage_bucket,Key=key,Body=data,ContentType=content_type)
def get_bytes(key):
    if settings.storage_mode=='local':
        p=local_path(key)
        if not p.exists():raise HTTPException(409,'Upload not yet available')
        if p.stat().st_size>MAX_BYTES:raise HTTPException(413,'Attachment too large')
        return p.read_bytes()
    from .integrations import storage
    obj=storage().get_object(Bucket=settings.storage_bucket,Key=key)
    if obj['ContentLength']>MAX_BYTES:raise HTTPException(413,'Attachment too large')
    return obj['Body'].read(MAX_BYTES+1)
def inspect_image(data,expected_hash,expected_type):
    if not 0<len(data)<=MAX_BYTES:raise HTTPException(413,'Attachment too large or empty')
    if hashlib.sha256(data).hexdigest()!=expected_hash:raise HTTPException(422,'Attachment checksum mismatch')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                actual={'JPEG':'image/jpeg','PNG':'image/png'}.get(image.format)
                if actual!=expected_type:raise ValueError('Content type mismatch')
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                clean=image.convert('RGB');out=io.BytesIO();clean.save(out,format='JPEG',quality=88)
        if len(out.getvalue())>MAX_BYTES:raise ValueError('Normalized image too large')
        return out.getvalue()
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):raise HTTPException(422,'Image inspection failed')

def create_upload(body,u,db):
    from .main import get_complaint
    c=get_complaint(db,body.complaint_id,u)
    if c.reporter_id!=u.id:raise HTTPException(403,'Only reporter may upload')
    r=Record(id=uid(),kind='attachment_pending',key=f'quarantine/{uid()}',payload={**body.model_dump(),'owner_id':u.id,'inspection':'pending'})
    db.add(r);db.commit()
    if settings.storage_mode=='local':
        local_path(r.key)
        upload={'method':'PUT','url':f'/api/v1/uploads/{r.id}/content','headers':{'Content-Type':body.content_type},'authenticated':True}
    else:
        from .integrations import storage
        url=storage().generate_presigned_url('put_object',Params={'Bucket':settings.storage_bucket,'Key':r.key,'ContentType':body.content_type,'ContentLength':body.size},ExpiresIn=300)
        upload={'method':'PUT','url':url,'headers':{'Content-Type':body.content_type},'authenticated':False}
    return {'upload':upload,'attachment_id':r.id,'expires_seconds':300,'status':'quarantined_until_inspected'}

@router.put('/uploads/{key}/content')
async def upload_local(key:str,request:Request,u:User=Depends(current),db:Session=Depends(session)):
    r=db.get(Record,key)
    if not r or r.kind!='attachment_pending' or r.payload['owner_id']!=u.id:raise HTTPException(404,'Upload not found')
    local_path(r.key)
    content=bytearray()
    async for part in request.stream():
        content.extend(part)
        if len(content)>r.payload['size']:raise HTTPException(413,'Upload exceeds declared size')
    if len(content)!=r.payload['size']:raise HTTPException(422,'Upload size mismatch')
    put_bytes(r.key,bytes(content),r.payload['content_type']);return {'status':'quarantined'}

@router.post('/uploads/{key}/finalize')
def finalize(key:str,u:User=Depends(current),db:Session=Depends(session)):
    r=db.get(Record,key)
    if not r or r.kind!='attachment_pending' or r.payload['owner_id']!=u.id:raise HTTPException(404,'Upload not found')
    existing=db.scalar(select(Record).where(Record.kind=='attachment',Record.key==key))
    if existing:return {'attachment_id':existing.id,'status':'inspected_private'}
    data=get_bytes(r.key)
    if len(data)!=r.payload['size']:raise HTTPException(422,'Upload size mismatch')
    clean=inspect_image(data,r.payload['sha256'],r.payload['content_type']);object_key=f'inspected/{r.id}.jpg';put_bytes(object_key,clean,'image/jpeg')
    a=Record(kind='attachment',key=key,payload={'complaint_id':r.payload['complaint_id'],'owner_id':u.id,'object_key':object_key,'content_type':'image/jpeg','source_sha256':r.payload['sha256'],'sha256':hashlib.sha256(clean).hexdigest(),'inspection':'decoded_reencoded_metadata_removed','size':len(clean)})
    db.add(a);db.commit();return {'attachment_id':a.id,'status':'inspected_private'}

@router.get('/complaints/{key}/attachments')
def list_attachments(key:str,u:User=Depends(current),db:Session=Depends(session)):
    from .main import get_complaint,raw
    get_complaint(db,key,u);result=[]
    for r in db.scalars(select(Record).where(Record.kind=='attachment')):
        if r.payload['complaint_id']!=key:continue
        approved=db.scalar(select(Record).where(Record.kind=='attachment_approval',Record.key==r.id)) is not None
        if u.role=='official' and not approved:continue
        result.append({'id':r.id,'content_type':r.payload['content_type'],'size':r.payload['size'],'inspection':r.payload['inspection'],'approved_for_officials':approved})
    return result

@router.post('/admin/attachments/{key}/approve')
def approve(key:str,u:User=Depends(current),db:Session=Depends(session)):
    from .main import get_complaint
    require(u,['admin','system_admin']);r=db.get(Record,key)
    if not r or r.kind!='attachment':raise HTTPException(404,'Attachment not found')
    get_complaint(db,r.payload['complaint_id'],u)
    if not db.scalar(select(Record).where(Record.kind=='attachment_approval',Record.key==key)):
        db.add(Record(kind='attachment_approval',key=key,payload={'reviewer':u.id,'complaint_id':r.payload['complaint_id']}));db.commit()
    return {'status':'approved'}

@router.get('/attachments/{key}/content')
def download(key:str,u:User=Depends(current),db:Session=Depends(session)):
    from .main import get_complaint
    r=db.get(Record,key)
    if not r or r.kind!='attachment':raise HTTPException(404,'Attachment not found')
    get_complaint(db,r.payload['complaint_id'],u)
    if u.role=='official' and not db.scalar(select(Record).where(Record.kind=='attachment_approval',Record.key==key)):raise HTTPException(404,'Attachment not published')
    return Response(get_bytes(r.payload['object_key']),media_type='image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
