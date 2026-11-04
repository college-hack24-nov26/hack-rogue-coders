"""Local-only readiness checks; no credentials or verification URLs are printed."""
import argparse
import json
from urllib.parse import urlparse
import httpx
from sqlalchemy import select, func
from services.api.config import settings, ENV_FILE
from services.api.db import Session, Village, User, Job


def check(api_url):
    parsed = urlparse(api_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1'):
        raise ValueError('This check only accepts a local HTTP API URL')
    keys = ['whatsapp_app_secret', 'whatsapp_access_token', 'whatsapp_phone_number_id',
            'whatsapp_api_version', 'whatsapp_approved_recipients']
    report = {'env_file': str(ENV_FILE), 'missing_meta_values': [k.upper() for k in keys if not getattr(settings, k)],
              'verification_token_configured': bool(settings.whatsapp_verify_token),
              'external_sending_enabled': settings.allow_external_send, 'real_delivery_verified': False}
    with httpx.Client(timeout=5, trust_env=False) as client:
        report['api_healthy'] = client.get(api_url+'/health').status_code == 200
        routes = client.get(api_url+'/openapi.json').json().get('paths', {})
        report['linking_route_available'] = '/api/v1/whatsapp/link-code' in routes
        challenge = 'jalsathi-local-readiness-check'
        response = client.get(api_url+'/api/v1/webhooks/whatsapp', params={
            'hub.mode': 'subscribe', 'hub.verify_token': settings.whatsapp_verify_token, 'hub.challenge': challenge})
        report['local_webhook_challenge_verified'] = response.status_code == 200 and response.text == challenge
        response = client.post(api_url+'/api/v1/webhooks/whatsapp', content=b'{}')
        report['unsigned_webhook_rejected'] = response.status_code == 403
    with Session() as db:
        report['database_connected'] = db.scalar(select(1)) == 1
        report['imported_villages'] = db.scalar(select(func.count()).select_from(Village))
        report['staff_accounts'] = db.scalar(select(func.count()).select_from(User).where(User.role.in_(['admin','official','system_admin'])))
        report['worker_completed_jobs'] = db.scalar(select(func.count()).select_from(Job).where(Job.status=='completed'))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-url', default='http://127.0.0.1:8002')
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.api_url.rstrip('/')), indent=2))
    except Exception as exc:
        # HTTP exceptions can contain a URL with the verification token.
        print(json.dumps({'check_failed': type(exc).__name__, 'secret_values_omitted': True}))
        raise SystemExit(1)
