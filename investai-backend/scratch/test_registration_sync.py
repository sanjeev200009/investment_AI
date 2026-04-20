# test_registration_sync.py
import sys
import os
import uuid

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models.user import User
from sqlalchemy import text

def test():
    db = SessionLocal()
    try:
        print("Testing local user insertion with string UUID...")
        test_id = str(uuid.uuid4())
        new_user = User(
            user_id=test_id,
            email="test_sync@example.com",
            full_name="Test Sync",
            password_hash="[TEST]",
            is_email_verified=False
        )
        db.add(new_user)
        db.commit()
        print(f"SUCCESS: User inserted with ID {test_id}")
        
        # Cleanup
        db.delete(new_user)
        db.commit()
    except Exception as e:
        print(f"FAILED: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    test()
