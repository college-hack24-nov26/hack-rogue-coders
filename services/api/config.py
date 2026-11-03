from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./jalsathi.db'
    environment: str = 'development'
    auth_mode: str = 'local'
    local_signing_key: str = ''
    neon_auth_jwks_url: str = ''
    neon_auth_issuer: str = ''
    neon_auth_audience: str = ''
    cors_origins: str = 'http://localhost:5173,http://localhost:5174,http://localhost:8081,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:8081'
    whatsapp_app_secret: str = ''
    whatsapp_verify_token: str = ''
    whatsapp_access_token: str = ''
    whatsapp_phone_number_id: str = ''
    whatsapp_api_version: str = ''
    allow_external_send: bool = False
    gemini_api_key: str = ''
    gemini_model: str = ''
    storage_endpoint: str = ''
    storage_bucket: str = ''
    storage_access_key: str = ''
    storage_secret_key: str = ''
    agmarknet_api_key: str = ''
    model_artifact_root: str = './artifacts'
    storage_mode: str = 'local'
    private_storage_root: str = './.private'
    neon_auth_url: str = ''
    neon_auth_origin: str = ''
    agmarknet_resource_id: str = '9ef84268-d588-465a-a308-a864a43d0070'
    enable_daily_ingestion: bool = False
    retention_days: int = 365
    water_data_root: str = './data/water'
    session_encryption_key: str = ''
    whatsapp_status_template: str = ''
    whatsapp_template_language: str = 'en_US'
    whatsapp_template_approved: bool = False

settings = Settings()
