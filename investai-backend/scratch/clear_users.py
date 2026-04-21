import os
import sys
from supabase import create_client
from sqlalchemy import text

# Add parent directory to path to import app items
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.config import get_settings
from app.models.user import User

def clear_all_data():
    settings = get_settings()
    db = SessionLocal()
    
    print("--- Starting Full User Data Reset ---")
    
    # 1. Clear Local Database
    try:
        print("Clearing local database tables...")
        # Note: 'users' deletion will cascade to profiles, risk_profiles, portfolios, etc.
        db.query(User).delete()
        
        # Clear OTP codes (no cascade)
        db.execute(text("DELETE FROM otp_codes"))
        
        db.commit()
        print("Local database cleared successfully.")
    except Exception as e:
        print(f"Error clearing local DB: {e}")
        db.rollback()
    finally:
        db.close()

    # 2. Clear Supabase Auth Users
    try:
        print("\nConnecting to Supabase Admin API...")
        admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        
        # Get all users (page-by-page if necessary, but for dev 1 page is enough)
        users_resp = admin_client.auth.admin.list_users()
        
        # In newer versions of the SDK, list_users() might return the list directly or an object
        users = []
        if isinstance(users_resp, list):
            users = users_resp
        elif hasattr(users_resp, 'users'):
            users = users_resp.users
        else:
            # Try to see if it's an object we can iterate
            users = users_resp
            
        if users:
            print(f"Found {len(users)} users in Supabase Auth.")
            for u in users:
                # u might be a dict or a User object
                u_id = u.id if hasattr(u, 'id') else u.get('id')
                u_email = u.email if hasattr(u, 'email') else u.get('email')
                print(f"Deleting user: {u_email} ({u_id})")
                admin_client.auth.admin.delete_user(u_id)
            print("Supabase Auth cleared successfully.")
        else:
            print("No users found in Supabase.")
            
    except Exception as e:
        print(f"Error clearing Supabase Auth: {e}")

    print("\n--- Reset Complete ---")

if __name__ == "__main__":
    clear_all_data()
