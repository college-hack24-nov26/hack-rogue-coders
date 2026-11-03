import pytest
from sqlalchemy import select,func
from services.api.config import settings
from services.api.db import User
from services.api.auth import verify_password

P='/api/v1'

@pytest.mark.parametrize('email,password',[
    ('',''),
    ('not-an-email','TEST-only-long-password'),
    ('farmer@','TEST-only-long-password'),
    ('farmer@example.test','          '),
])
def test_invalid_signup_does_not_create_an_account(setup,email,password):
    client,factory,_=setup
    with factory() as db:before=db.scalar(select(func.count()).select_from(User))
    response=client.post(P+'/auth/register',json={'email':email,'password':password})
    assert response.status_code==422
    assert response.json()['errors']
    assert all(set(error)=={'field','message','type'} for error in response.json()['errors'])
    with factory() as db:assert db.scalar(select(func.count()).select_from(User))==before

def test_signup_then_login_normalizes_email_and_preserves_the_password(setup):
    client,factory,_=setup;password='  TEST-password-with-spaces  '
    response=client.post(P+'/auth/register',json={'email':' New.Farmer+test@Example.test ','password':password})
    assert response.status_code==200,response.text
    me=client.get(P+'/me',headers={'Authorization':'Bearer '+response.json()['access_token']}).json()
    assert me['email']=='new.farmer+test@example.test' and me['role']=='farmer' and me['jurisdictions']==[]
    with factory() as db:
        user=db.get(User,me['id']);assert user.password_hash!=password and verify_password(password,user.password_hash)
    assert client.post(P+'/auth/login',json={'email':'NEW.FARMER+TEST@example.test','password':password}).status_code==200
    assert client.post(P+'/auth/login',json={'email':me['email'],'password':password.strip()}).status_code==401
    duplicate=client.post(P+'/auth/register',json={'email':me['email'],'password':password})
    assert duplicate.status_code==409 and 'Sign in instead' in duplicate.json()['detail']

def test_validation_errors_never_return_submitted_passwords(setup):
    client,_,_=setup;private_value='TEST123'
    response=client.post(P+'/auth/register',json={'email':'farmer@example.test','password':private_value,'role':'admin'})
    assert response.status_code==422
    assert private_value not in response.text and '"input"' not in response.text and '"ctx"' not in response.text
    assert {error['field'] for error in response.json()['errors']}=={'password','role'}

def test_auth_capabilities_reflect_sign_up_availability(setup,monkeypatch):
    client,_,_=setup
    assert client.get(P+'/auth/capabilities').json()['email_signup'] is True
    monkeypatch.setattr(settings,'environment','production')
    assert client.get(P+'/auth/capabilities').json()['email_signup'] is False
    assert client.post(P+'/auth/register',json={'email':'blocked@example.test','password':'TEST-only-long-password'}).status_code==503
    monkeypatch.setattr(settings,'auth_mode','neon')
    for field,value in {'neon_auth_url':'https://auth.fixture.test','neon_auth_jwks_url':'https://auth.fixture.test/jwks','neon_auth_issuer':'https://auth.fixture.test','neon_auth_audience':'TEST-AUDIENCE','neon_auth_origin':'https://app.fixture.test','session_encryption_key':'TEST-ONLY-'+'x'*32}.items():monkeypatch.setattr(settings,field,value)
    capabilities=client.get(P+'/auth/capabilities').json()
    assert capabilities['email_login'] is True and capabilities['email_signup'] is False
    monkeypatch.setattr(settings,'allow_external_send',True)
    assert client.get(P+'/auth/capabilities').json()['email_signup'] is True
