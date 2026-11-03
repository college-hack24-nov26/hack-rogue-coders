"""Secret-free configuration diagnostics. Presence is never live verification."""

REQUIRED={
    'neon_database':['DATABASE_URL'],
    'neon_auth':['NEON_AUTH_URL','NEON_AUTH_JWKS_URL','NEON_AUTH_ISSUER','NEON_AUTH_AUDIENCE','NEON_AUTH_ORIGIN','SESSION_ENCRYPTION_KEY'],
    'gemini':['GEMINI_API_KEY','GEMINI_MODEL'],
    'private_neon_storage':['STORAGE_ENDPOINT','STORAGE_BUCKET','STORAGE_ACCESS_KEY','STORAGE_SECRET_KEY'],
    'whatsapp':['WHATSAPP_APP_SECRET','WHATSAPP_VERIFY_TOKEN','WHATSAPP_ACCESS_TOKEN','WHATSAPP_PHONE_NUMBER_ID','WHATSAPP_API_VERSION'],
}

def configuration_status(settings):
    providers={}
    for name,keys in REQUIRED.items():
        missing=[key for key in keys if not str(getattr(settings,key.lower(),'')).strip()]
        if name=='neon_database' and not settings.database_url.startswith('postgresql+psycopg://'):
            missing=['DATABASE_URL']
        providers[name]={'status':'missing_configuration' if missing else 'configured_unverified','missing_env':missing,'required_env':keys}
    return {'providers':providers,'modes':{'environment':settings.environment,'auth':settings.auth_mode,'storage':settings.storage_mode,'external_sending_enabled':settings.allow_external_send},'local_services':{'database':'sqlite' if settings.database_url.startswith('sqlite') else 'postgresql','photos':settings.storage_mode},'configuration_complete':all(not p['missing_env'] for p in providers.values()),'live_verified':False,'next_step':'Set the listed variables in the local .env, then run python -m scripts.check_readiness --live. Never paste credentials into chat.'}
