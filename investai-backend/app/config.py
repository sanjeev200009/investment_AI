# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # Database
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Redis
    CELERY_BROKER_URL: str = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND: str = 'redis://localhost:6379/1'

    # App
    ENVIRONMENT: str = 'development'
    DEBUG: bool = False
    API_VERSION: str = 'v1'

    # Firebase Cloud Messaging
    FCM_SERVER_KEY: str = ''

    # Brevo Mail (Using HTTP API)
    BREVO_API_KEY: str = ''
    BREVO_FROM_EMAIL: str = 'noreply@yourdomain.com'
    BREVO_FROM_NAME: str = 'InvestAI'

    FRONTEND_URL: str = 'http://localhost:19006'


@lru_cache
def get_settings() -> Settings:
    return Settings()
