# nuke_supabase_and_local.py
import sys
import os

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.config import get_settings
from supabase import create_client
from sqlalchemy import text

def nuke():
    settings = get_settings()
    db = SessionLocal()
    
    try:
        # 1. Connect to Supabase Admin
        print("Connecting to Supabase Admin API...")
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        
        # 2. Fetch all users from Supabase Auth
        print("Fetching all users from Supabase Auth...")
        response = supabase.auth.admin.list_users()
        users = response # In some versions it returns the list directly, in others an object
        
        # Handle different supabase-py versions
        user_list = getattr(users, 'users', users)
        
        print(f"Found {len(user_list)} users in Supabase.")
        
        # 3. Delete Supabase Users
        for user in user_list:
            print(f"- Deleting Supabase User: {user.email} ({user.id})")
            supabase.auth.admin.delete_user(user.id)
            
        print("\nSupabase Auth cleared.")
        
        # 4. Clear Local DB
        print("\nClearing local database tables...")
        print("- Deleting OTP codes...")
        db.execute(text("DELETE FROM otp_codes"))
        print("- Deleting local User records...")
        db.execute(text("DELETE FROM users"))
        
        db.commit()
        print("\nSUCCESS: Entire authentication system has been NUKED.")
        print("All users removed from Supabase and Local DB.")
        
    except Exception as e:
        db.rollback()
        print(f"ERROR: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    nuke()
