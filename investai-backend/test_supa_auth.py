import asyncio
from supabase import create_client, Client
from app.config import get_settings

settings = get_settings()
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

test_token = "invalid_token_123"

try:
    user = supabase.auth.get_user(test_token)
    print("User:", user)
except Exception as e:
    print("Error:", e)
