"""Check real provider configuration and optional read-only connectivity, without secrets."""
import argparse,json,re
from pathlib import Path
import httpx
from sqlalchemy import create_engine,text
from botocore.config import Config
from services.api.config import settings
from services.api.db import now
from services.api.readiness import configuration_status

def probe(name):
    if name=='neon_database':
        engine=create_engine(settings.database_url,connect_args={'connect_timeout':5})
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                connection.execute(text('SELECT PostGIS_Version()'))
            return {'status':'database_and_postgis_verified','writes_verified':False}
        finally:engine.dispose()
    if name=='neon_auth':
        with httpx.Client(timeout=10,follow_redirects=False) as client:response=client.get(settings.neon_auth_jwks_url)
        response.raise_for_status();data=response.json()
        if not data.get('keys') or not all(k.get('kid') and k.get('kty') for k in data['keys']):raise ValueError('Invalid JWKS')
        return {'status':'jwks_retrieval_verified','signup_login_refresh_recovery_verified':False}
    if name=='gemini':
        if not re.fullmatch(r'[a-zA-Z0-9._-]+',settings.gemini_model):raise ValueError('Invalid model identifier')
        with httpx.Client(timeout=10) as client:response=client.get('https://generativelanguage.googleapis.com/v1beta/models/'+settings.gemini_model,headers={'x-goog-api-key':settings.gemini_api_key})
        response.raise_for_status()
        if not response.json().get('name'):raise ValueError('Invalid model metadata')
        return {'status':'model_access_verified','generation_verified':False}
    if name=='whatsapp':
        if not re.fullmatch(r'v\d+\.\d+',settings.whatsapp_api_version) or not settings.whatsapp_phone_number_id.isdigit():raise ValueError('Invalid version/phone ID')
        with httpx.Client(timeout=10) as client:response=client.get('https://graph.facebook.com/'+settings.whatsapp_api_version+'/'+settings.whatsapp_phone_number_id,params={'fields':'id'},headers={'Authorization':'Bearer '+settings.whatsapp_access_token})
        response.raise_for_status()
        if response.json().get('id')!=settings.whatsapp_phone_number_id:raise ValueError('Business phone mismatch')
        return {'status':'phone_access_verified','webhook_signature_and_delivery_verified':False,'messages_sent':0}
    if name=='private_neon_storage':
        import boto3
        client=boto3.client('s3',endpoint_url=settings.storage_endpoint,aws_access_key_id=settings.storage_access_key,aws_secret_access_key=settings.storage_secret_key,config=Config(connect_timeout=5,read_timeout=10,retries={'max_attempts':0}))
        client.head_bucket(Bucket=settings.storage_bucket)
        return {'status':'bucket_access_verified','private_policy_and_signed_put_verified':False}
    raise ValueError('Unknown provider')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--report',type=Path,default=Path('docs/READINESS.json'));args=parser.parse_args()
    report=configuration_status(settings);report['checked_at']=now();report['read_only_probes_requested']=args.live;report['external_messages_sent']=0
    if args.live:
        for name,provider in report['providers'].items():
            if provider['missing_env']:continue
            try:provider['probe']=probe(name)
            except Exception as error:
                # Provider exceptions can embed request URLs or credentials.
                # Store classes only, never exception text or response bodies.
                provider['probe']={'status':'failed','error_class':type(error).__name__}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
