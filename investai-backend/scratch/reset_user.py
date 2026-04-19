import os
import sys
from supabase import create_client
from sqlalchemy import text, create_engine
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.getcwd())

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

TARGET_EMAIL = "sanjeevsivasuthakaran@gmail.com"

def reset_user():
    print(f"--- Final Reset for: {TARGET_EMAIL} ---")
    
    # 1. Supabase Admin Client
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    print("Deleting from Supabase Auth...")
    users_list = supabase.auth.admin.list_users()
    for user in users_list:
        if user.email == TARGET_EMAIL:
            supabase.auth.admin.delete_user(user.id)
            print(f"  - Deleted {user.id}")
            break
        
    # 2. Local Database
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn: # Automatically commits or rolls back
        # Get ID one last time
        res = conn.execute(text("SELECT user_id FROM users WHERE email = :email"), {"email": TARGET_EMAIL}).fetchone()
        if res:
            user_id = res[0]
            print(f"Deleting user {user_id} and related data from DB...")
            
            # Delete in order of dependencies if CASCADE is somehow failing
            conn.execute(text("DELETE FROM portfolios WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM chat_sessions WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM otp_codes WHERE email = :email"), {"email": TARGET_EMAIL})
            conn.execute(text("DELETE FROM users WHERE user_id = :uid"), {"uid": user_id})
            
            print("  - ALL related data and the user record have been purged.")
        else:
            # Maybe only OTPs left?
            conn.execute(text("DELETE FROM otp_codes WHERE email = :email"), {"email": TARGET_EMAIL})
            print("User record not found in DB (already deleted), but checked for leftover OTPs.")

    print("\n[COMPLETE] You can now register fresh from the mobile app.")

if __name__ == "__main__":
    reset_user()
