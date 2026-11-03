import hashlib,secrets,json,base64
from datetime import datetime,timedelta,timezone
import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import session,Record,uid
from .config import settings

router=APIRouter(prefix='/api/v1/auth')
class Refresh(BaseModel):refresh_token:str=Field(min_length=32,max_length=200)
class Recovery(BaseModel):email:str=Field(min_length=3,max_length=250)
def endpoint(path):
    base=settings.neon_auth_url.rstrip('/')
    if not base.startswith('https://') or not settings.neon_auth_origin:raise HTTPException(503,'Neon Auth URL and allowed origin are not configured')
    return base+('' if base.endswith('/auth') else '/auth')+path
def cipher():
    key=settings.session_encryption_key
    if not key and settings.environment=='development':key=settings.local_signing_key
    if len(key)<32:raise HTTPException(503,'Server session encryption key not configured')
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))
def token_response(data):
    return data.get('token') or data.get('session',{}).get('access_token') or data.get('data',{}).get('session',{}).get('access_token')
async def provider_login(body,db,signup=False):
    try:
        async with httpx.AsyncClient(timeout=25,headers={'Origin':settings.neon_auth_origin}) as client:
            response=await client.post(endpoint('/sign-up/email' if signup else '/sign-in/email'),json={'email':body.email,'password':body.password,**({'name':body.email.split('@')[0]} if signup else {})})
            if response.status_code>=400:raise HTTPException(401 if response.status_code<500 else 503,'Neon sign-in failed; verify account or email verification')
            # Better Auth's sign-in `token` is an opaque session token, not
            # the signed JWT accepted by our API. Exchange the session cookie.
            r=await client.get(endpoint('/token'))
            if r.status_code>=500:raise HTTPException(503,'Neon authentication provider unavailable')
            jwt=token_response(r.json()) if r.status_code==200 else None
            if not jwt:raise HTTPException(409,'Account requires email verification before a session can be created')
            cookie='; '.join(f'{k}={v}' for k,v in client.cookies.items())
        refresh=secrets.token_urlsafe(48)
        db.add(Record(kind='auth_session',key=hashlib.sha256(refresh.encode()).hexdigest(),payload={'cookie':cipher().encrypt(cookie.encode()).decode(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()}));db.commit()
        return {'access_token':jwt,'refresh_token':refresh,'token_type':'bearer','provider':'neon'}
    except httpx.HTTPError:raise HTTPException(503,'Neon authentication provider unavailable')

@router.get('/capabilities')
def capabilities():
    local=settings.auth_mode=='local' and settings.environment=='development' and len(settings.local_signing_key)>=32
    neon=settings.auth_mode=='neon' and all([settings.neon_auth_url,settings.neon_auth_jwks_url,settings.neon_auth_issuer,settings.neon_auth_audience,settings.neon_auth_origin]) and (len(settings.session_encryption_key)>=32 or settings.environment=='development' and len(settings.local_signing_key)>=32)
    configured=bool(local or neon)
    return {'mode':settings.auth_mode,'email_login':configured,'email_signup':bool(local or neon and settings.allow_external_send),'phone_first_signup':False,'configured':configured,'production_mobile_verified':False}
@router.post('/refresh')
async def refresh(body:Refresh,db:Session=Depends(session)):
    if settings.auth_mode!='neon':raise HTTPException(409,'Local sessions require signing in again')
    key=hashlib.sha256(body.refresh_token.encode()).hexdigest();r=db.scalar(select(Record).where(Record.kind=='auth_session',Record.key==key))
    if not r or r.payload['expires_at']<datetime.now(timezone.utc).isoformat():raise HTTPException(401,'Session expired')
    try:
        cookie=cipher().decrypt(r.payload['cookie'].encode()).decode()
        async with httpx.AsyncClient(timeout=20) as client:
            response=await client.get(endpoint('/token'),headers={'Cookie':cookie,'Origin':settings.neon_auth_origin})
        if response.status_code!=200:raise HTTPException(401,'Provider session expired')
        jwt=token_response(response.json())
        if not jwt:raise HTTPException(401,'Provider did not return an API token')
        return {'access_token':jwt,'refresh_token':body.refresh_token}
    except httpx.HTTPError:raise HTTPException(503,'Authentication provider unavailable')
@router.post('/logout')
async def logout(body:Refresh,db:Session=Depends(session)):
    r=db.scalar(select(Record).where(Record.kind=='auth_session',Record.key==hashlib.sha256(body.refresh_token.encode()).hexdigest()))
    if r:
        if settings.auth_mode=='neon':
            try:
                async with httpx.AsyncClient(timeout=10) as client:await client.post(endpoint('/sign-out'),headers={'Cookie':cipher().decrypt(r.payload['cookie'].encode()).decode(),'Origin':settings.neon_auth_origin})
            except httpx.HTTPError:pass
        db.delete(r);db.commit()
    return {'status':'signed_out'}
@router.post('/recovery')
async def recovery(body:Recovery):
    # Sending account email is an external action; explicitly disabled with other outbound traffic.
    if not settings.allow_external_send:raise HTTPException(409,'External account-recovery email sending is disabled')
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post(endpoint('/request-password-reset'),headers={'Origin':settings.neon_auth_origin},json={'email':body.email,'redirectTo':settings.neon_auth_origin})
    if r.status_code>=500:raise HTTPException(503,'Recovery provider unavailable')
    return {'status':'If an eligible account exists, the provider will send recovery instructions'}
