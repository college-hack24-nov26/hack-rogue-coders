"""Prepare ignored local configuration without printing any secret values."""
from pathlib import Path
import secrets
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDERS = {
    'WHATSAPP_APP_SECRET': 'REPLACE_WITH_META_APP_SECRET',
    'WHATSAPP_ACCESS_TOKEN': 'REPLACE_WITH_META_ACCESS_TOKEN',
    'WHATSAPP_PHONE_NUMBER_ID': 'REPLACE_WITH_META_PHONE_NUMBER_ID',
    'WHATSAPP_API_VERSION': 'REPLACE_WITH_META_GRAPH_API_VERSION',
    'WHATSAPP_APPROVED_RECIPIENTS': 'REPLACE_WITH_META_APPROVED_TEST_RECIPIENTS',
    'WHATSAPP_STATUS_TEMPLATE': 'REPLACE_WITH_META_APPROVED_STATUS_TEMPLATE',
}


def missing(value):
    return not value or str(value).strip().upper().startswith('REPLACE_WITH_')


def prepare(root=ROOT):
    target = root / '.env'
    fresh = not target.exists()
    if fresh:
        target.write_text((root / '.env.example').read_text(encoding='utf-8'), encoding='utf-8')
    values = dotenv_values(target)
    defaults = dotenv_values(root / '.env.example')
    for name, value in defaults.items():
        if name not in values:
            set_key(target, name, value or '', quote_mode='always')
    values = dotenv_values(target)
    for name, value in PLACEHOLDERS.items():
        if missing(values.get(name)):
            set_key(target, name, value, quote_mode='always')
    # Locally generated keys are real random local secrets, never fabricated Meta credentials.
    for name in ['WHATSAPP_VERIFY_TOKEN', 'LOCAL_SIGNING_KEY']:
        if missing(values.get(name)):
            set_key(target, name, secrets.token_urlsafe(48), quote_mode='always')
    # Explicitly required by this preparation task, even if a previous file enabled it.
    set_key(target, 'ALLOW_EXTERNAL_SEND', 'false', quote_mode='never')
    # Resolve the fresh development database consistently across launch directories.
    if fresh and values.get('DATABASE_URL') == 'sqlite:///./jalsathi.db':
        set_key(target, 'DATABASE_URL', 'sqlite:///'+(root/'jalsathi.db').as_posix(), quote_mode='always')
    mobile = root/'apps'/'farmer-mobile'/'.env'
    if not mobile.exists():
        mobile.write_text((mobile.parent/'.env.example').read_text(encoding='utf-8'), encoding='utf-8')
    final = dotenv_values(target)
    return {'env_path': str(target), 'missing_meta_values': [k for k in PLACEHOLDERS if missing(final.get(k))],
            'external_sending_enabled': False}


if __name__ == '__main__':
    import json
    print(json.dumps(prepare(), indent=2))
