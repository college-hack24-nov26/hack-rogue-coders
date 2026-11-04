"""Discover the local Quick Tunnel URL and check the public Meta verification path."""
import json
import re
from pathlib import Path
import httpx
from services.api.config import settings

ROOT = Path(__file__).resolve().parents[1]


def verify():
    log = (ROOT/'work/whatsapp-tunnel-error.log').read_text(encoding='utf-8', errors='replace')
    matches = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', log)
    if not matches:
        return {'public_webhook_verified': False, 'reason': 'Tunnel has not published a URL yet'}
    url = matches[-1]+'/api/v1/webhooks/whatsapp'
    report = {'callback_url': url, 'public_webhook_verified': False, 'meta_dashboard_verified': False,
              'real_delivery_verified': False, 'external_sending_enabled': settings.allow_external_send}
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.get(url, params={'hub.mode': 'subscribe', 'hub.verify_token': settings.whatsapp_verify_token,
                                              'hub.challenge': 'jalsathi-public-readiness-check'})
            report['public_webhook_verified'] = response.status_code == 200 and response.text == 'jalsathi-public-readiness-check'
            report['public_challenge_http_status'] = response.status_code
            report['unsigned_post_rejected'] = client.post(url, content=b'{}').status_code == 403
            report['non_webhook_routes_hidden'] = client.get(matches[-1]+'/docs').status_code == 404
    except httpx.HTTPError as exc:
        report['error_class'] = type(exc).__name__
    (ROOT/'work/whatsapp-public.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), indent=2))
    except Exception as exc:
        print(json.dumps({'public_webhook_verified': False, 'error_class': type(exc).__name__}))
        raise SystemExit(1)
