# debug_register.py
import sys
import os

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.routers.auth import register
from app.schemas.auth import RegisterRequest
from pydantic import EmailStr
import asyncio

async def debug():
    db = SessionLocal()
    try:
        print("Debugging Register Flow...")
        payload = RegisterRequest(
            email="debug_register_test@example.com",
            password="password123",
            full_name="Debug Test"
        )
        
        # We need to mock BackgroundTasks for the async call
        from fastapi import BackgroundTasks
        bt = BackgroundTasks()
        
        result = await register(payload, bt, db)
        print(f"SUCCESS: {result}")
        
    except Exception as e:
        print("CRASHED!")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug())
