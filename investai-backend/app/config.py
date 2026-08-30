# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Database
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Retained only so an existing .env with this key still loads. Clerk was
    # removed in the I-02 auth cutover; nothing reads this.
    CLERK_SECRET_KEY: str = ""

    # ---- Supabase access-token verification (app/dependencies.py) ----
    # Supabase signs user tokens one of two ways depending on project age:
    #   * legacy  — HS256 with this shared secret (Dashboard -> Project Settings
    #     -> API -> JWT Keys -> "JWT Secret"). Required for HS* tokens.
    #   * current — asymmetric ES256/RS256, verified via the project's JWKS. No
    #     secret needed; leave SUPABASE_JWT_SECRET blank.
    # Both paths are implemented, selected by the token header's `alg`, so this
    # works before and after a project migrates.
    SUPABASE_JWT_SECRET: str = ''
    # Supabase user tokens carry aud='authenticated'. Blank disables the check.
    SUPABASE_JWT_AUDIENCE: str = 'authenticated'
    # Blank derives '{SUPABASE_URL}/auth/v1', which is what Supabase issues.
    SUPABASE_JWT_ISSUER: str = ''
    SUPABASE_JWKS_TTL_SECONDS: int = 3600

    # Redis
    CELERY_BROKER_URL: str = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND: str = 'redis://localhost:6379/1'

    # App
    ENVIRONMENT: str = 'development'
    DEBUG: bool = False
    API_VERSION: str = 'v1'

    # Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_PATH: str = 'firebase-key.json'
    FCM_SERVER_KEY: str = ''

    # AI Agent
    ANTHROPIC_API_KEY: str = ''
    OPENAI_API_KEY: str = ''
    GOOGLE_API_KEY: str = ''
    GROQ_API_KEY: str = ''
    OPENROUTER_API_KEY: str = ''
    NVIDIA_API_KEY: str = ''

    # ---- LLM provider chain: NVIDIA primary, OpenRouter fallback ----
    # Both are OpenAI-compatible, so app/services/llm.py serves both with one
    # client type. Model ids are settings rather than constants because free-tier
    # availability changes without notice: 'google/gemini-flash-1.5' (previously
    # hardcoded in sentiment.py and rules_tasks.py) is now a 404, and
    # 'google/gemini-2.5-flash' (previously in agent/core.py) now returns 402.
    NVIDIA_BASE_URL: str = 'https://integrate.api.nvidia.com/v1'
    OPENROUTER_BASE_URL: str = 'https://openrouter.ai/api/v1'

    # Chosen by measurement, not by reputation — see docs/MODEL_SELECTION.md.
    # AGENT needs reliable multi-tool calling + streaming deltas; UTILITY only
    # needs short prose, but must not be a reasoning model that starves its own
    # output budget.
    NVIDIA_AGENT_MODEL: str = 'openai/gpt-oss-20b'
    NVIDIA_UTILITY_MODEL: str = 'nvidia/nemotron-3-nano-30b-a3b'
    OPENROUTER_AGENT_MODEL: str = 'minimax/minimax-m3:free'
    OPENROUTER_UTILITY_MODEL: str = 'minimax/minimax-m3:free'

    # Short enough that a hung primary fails over inside the NFR-4 budget
    # (<5s perceived response), long enough not to abandon a healthy slow reply.
    LLM_TIMEOUT_SECONDS: float = 20.0

    # Utility calls previously passed max_tokens=150..250. On reasoning models
    # that budget was consumed by hidden reasoning and the visible content came
    # back empty with finish_reason='length'. Headroom is the real fix.
    LLM_UTILITY_MAX_TOKENS: int = 700

    # Embeddings. nvidia/nv-embedqa-e5-v5 (1024-dim) reached end of life and now
    # returns 410 Gone; nemotron-3-embed-1b is the available replacement and
    # emits 2048 dims, which is why migration b2c3d4e5f6a7 widens the column.
    NVIDIA_EMBED_MODEL: str = 'nvidia/nemotron-3-embed-1b'
    EMBED_DIM: int = 2048

    # Brevo Mail (Using HTTP API)
    BREVO_API_KEY: str = ''
    BREVO_FROM_EMAIL: str = 'noreply@yourdomain.com'
    BREVO_FROM_NAME: str = 'InvestAI'

    FRONTEND_URL: str = 'http://localhost:19006'


@lru_cache
def get_settings() -> Settings:
    return Settings()
