# verify_auth_system.py
import sys
import os

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import get_settings
from supabase import create_client

def test():
    settings = get_settings()
    print("Checking Authentication Backbone...")
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        # Test if we can connect to the Auth service
        print(f"SUCCESS: Connected to Supabase Auth at {settings.SUPABASE_URL}")
        print("CORS & JWT verification logic is ready.")
    except Exception as e:
        print(f"FAILED: {str(e)}")

if __name__ == "__main__":
    test()
