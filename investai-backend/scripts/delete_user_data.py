import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User
from app.config import get_settings
from supabase import create_client, Client

def main(email: str):
    print(f"Deleting user {email}...")
    
    # 1. Database Deletion
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user_id = str(user.user_id)
            print(f"Found user in DB: {user_id}")
            # Delete from DB
            db.delete(user)
            db.commit()
            print("Deleted user from database (cascaded to related records).")
        else:
            user_id = None
            print("User not found in database.")
    except Exception as e:
        print(f"Error deleting from database: {e}")
        db.rollback()
        user_id = None
    finally:
        db.close()
        
    # 2. Supabase Auth Deletion
    try:
        settings = get_settings()
        if not settings.SUPABASE_SERVICE_KEY:
            print("SUPABASE_SERVICE_KEY not set. Cannot delete from auth.")
            return

        supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        
        if user_id:
            try:
                supabase.auth.admin.delete_user(user_id)
                print(f"Deleted user {user_id} from Supabase Auth.")
            except Exception as e:
                print(f"Error deleting from Supabase Auth: {e}")
        else:
            print("Listing all users from auth to find by email...")
            try:
                page = supabase.auth.admin.list_users()
                users = page.users if hasattr(page, 'users') else page
                for u in users:
                    if u.email == email:
                        print(f"Found user in Auth: {u.id}")
                        supabase.auth.admin.delete_user(u.id)
                        print("Deleted user from Supabase Auth.")
                        break
                else:
                    print("User not found in Supabase Auth.")
            except Exception as e:
                print(f"Could not list/delete from auth: {e}")

    except Exception as e:
        print(f"Error with Supabase Auth admin client: {e}")

if __name__ == "__main__":
    email_to_delete = sys.argv[1] if len(sys.argv) > 1 else "sanjayhsanjeev2000@gmail.com"
    main(email_to_delete)
