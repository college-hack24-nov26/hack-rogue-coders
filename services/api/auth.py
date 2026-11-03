import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import User, session

bearer = HTTPBearer(auto_error=False)
def hash_password(password):
    salt = secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
def verify_password(password, encoded):
    try:
        salt, expected = encoded.split(':')
        return hmac.compare_digest(expected, hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex())
    except ValueError: return False
def local_enabled():
    if settings.environment != 'development' or settings.auth_mode != 'local' or len(settings.local_signing_key) < 32:
        raise HTTPException(503, 'Local auth unavailable; configure Neon Auth or a development signing key')
def token(user):
    local_enabled()
    return jwt.encode({'sub': user.id, 'iss': 'jalsathi-local', 'aud': 'jalsathi', 'exp': datetime.now(timezone.utc) + timedelta(hours=8)}, settings.local_signing_key, algorithm='HS256')
def current(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(session)):
    if not credentials: raise HTTPException(401, 'Sign in required')
    try:
        if settings.auth_mode == 'local':
            local_enabled()
            claims = jwt.decode(credentials.credentials, settings.local_signing_key, algorithms=['HS256'], issuer='jalsathi-local', audience='jalsathi', options={'require': ['exp', 'sub']})
        else:
            if not all([settings.neon_auth_jwks_url, settings.neon_auth_issuer, settings.neon_auth_audience]):
                raise HTTPException(503, 'Neon authentication configuration unavailable')
            key = jwt.PyJWKClient(settings.neon_auth_jwks_url).get_signing_key_from_jwt(credentials.credentials)
            claims = jwt.decode(credentials.credentials, key.key, algorithms=['RS256', 'ES256', 'EdDSA'], issuer=settings.neon_auth_issuer, audience=settings.neon_auth_audience, options={'require': ['exp', 'sub']})
    except jwt.PyJWTError: raise HTTPException(401, 'Invalid or expired session')
    user = db.get(User, claims['sub'])
    if not user:
        user = User(id=claims['sub'], email=claims.get('email',claims['sub'] + '@auth.local'), role='farmer', jurisdictions=[],preferences={'email_verified':claims.get('emailVerified',False) is True})
        db.add(user); db.commit()
    elif settings.auth_mode=='neon':
        user.preferences={**user.preferences,'email_verified':claims.get('emailVerified',False) is True}
    from .security import limit
    limit(db,'requests:'+user.id,300,60)
    return user
def require(user, roles):
    if user.role not in roles: raise HTTPException(403, 'Role not permitted')
def scoped(user, jurisdiction):
    return user.role == 'system_admin' or jurisdiction in user.jurisdictions
