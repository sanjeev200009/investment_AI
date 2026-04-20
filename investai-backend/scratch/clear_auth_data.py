# clear_auth_data.py
import sys
import os

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    try:
        print("Clearing authentication data...")
        
        # Disable foreign key checks for SQLite if needed, 
        # but here we just delete in order.
        
        print("- Deleting OTP codes...")
        db.execute(text("DELETE FROM otp_codes"))
        
        print("- Deleting Users...")
        db.execute(text("DELETE FROM users"))
        
        db.commit()
        print("\nSUCCESS: Local authentication tables cleared.")
        print("You can now test the registration flow from a fresh state.")
        
    except Exception as e:
        db.rollback()
        print(f"ERROR: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
