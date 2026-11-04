from pathlib import Path
from dotenv import dotenv_values
from services.api.config import Settings, ENV_FILE
from scripts.prepare_whatsapp import prepare


def test_placeholder_credentials_are_inactive_and_env_path_is_absolute():
    settings = Settings(_env_file=None, whatsapp_access_token='REPLACE_WITH_META_ACCESS_TOKEN',
                        whatsapp_app_secret='REPLACE_WITH_META_APP_SECRET',
                        whatsapp_phone_number_id='REPLACE_WITH_META_PHONE_NUMBER_ID',
                        whatsapp_api_version='REPLACE_WITH_META_GRAPH_API_VERSION')
    assert not settings.whatsapp_access_token
    assert not settings.whatsapp_app_secret
    assert not settings.whatsapp_phone_number_id
    assert not settings.whatsapp_api_version
    assert ENV_FILE.is_absolute() and ENV_FILE.parent == Path(__file__).resolve().parents[1]


def test_preparation_preserves_secrets_and_forces_sending_off(tmp_path):
    template = Path(__file__).resolve().parents[1]/'.env.example'
    (tmp_path/'.env.example').write_text(template.read_text(encoding='utf-8'), encoding='utf-8')
    mobile = tmp_path/'apps'/'farmer-mobile'
    mobile.mkdir(parents=True)
    (mobile/'.env.example').write_text('EXPO_PUBLIC_API_URL=http://127.0.0.1:8000\n')
    (tmp_path/'.env').write_text("WHATSAPP_ACCESS_TOKEN='fixture-existing-token'\nWHATSAPP_VERIFY_TOKEN='fixture-existing-verification-token'\nLOCAL_SIGNING_KEY='fixture-existing-signing-key'\nDATABASE_URL=sqlite:///./existing.db\nALLOW_EXTERNAL_SEND=true\n")
    result = prepare(tmp_path)
    values = dotenv_values(tmp_path/'.env')
    assert values['WHATSAPP_ACCESS_TOKEN'] == 'fixture-existing-token'
    assert values['WHATSAPP_VERIFY_TOKEN'] == 'fixture-existing-verification-token'
    assert values['LOCAL_SIGNING_KEY'] == 'fixture-existing-signing-key'
    assert values['DATABASE_URL'] == 'sqlite:///./existing.db'
    assert values['ALLOW_EXTERNAL_SEND'] == 'false'
    assert values['WHATSAPP_APP_SECRET'].startswith('REPLACE_WITH_')
    assert not result['external_sending_enabled']
    prepare(tmp_path)
    assert dotenv_values(tmp_path/'.env') == values


def test_webhook_gateway_forwards_raw_signed_body_and_hides_other_routes(monkeypatch):
    import httpx
    from fastapi.testclient import TestClient
    from scripts.whatsapp_gateway import create_gateway
    captured = []
    def handler(request):
        captured.append(request)
        if request.method == 'GET':
            return httpx.Response(200, text=request.url.params['hub.challenge'])
        return httpx.Response(200, json={'received': 1})
    real_async = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: real_async(transport=httpx.MockTransport(handler), **kw))
    c = TestClient(create_gateway())
    assert c.get('/docs').status_code == 404
    assert c.get('/api/v1/complaints/mine').status_code == 404
    r = c.get('/api/v1/webhooks/whatsapp', params={'hub.mode':'subscribe','hub.verify_token':'fixture-only','hub.challenge':'fixture-challenge'})
    assert r.text == 'fixture-challenge'
    raw = b'{ "entry": [] }'
    r = c.post('/api/v1/webhooks/whatsapp', content=raw, headers={'x-hub-signature-256':'sha256=fixture', 'content-type':'application/json'})
    assert r.json()['received'] == 1
    assert captured[-1].content == raw
    assert captured[-1].headers['x-hub-signature-256'] == 'sha256=fixture'
