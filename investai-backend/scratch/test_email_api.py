# test_email_api.py
import sys
import os
import asyncio

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.email_service import send_registration_otp
from app.config import get_settings

async def test():
    settings = get_settings()
    print(f"Testing Brevo API with Sender: {settings.BREVO_FROM_EMAIL}")
    print(f"Using API Key: {settings.BREVO_API_KEY[:5]}...{settings.BREVO_API_KEY[-5:]}")
    
    try:
        # Pass a real-looking email and name for the test
        result = await send_registration_otp("test_otp_check@example.com", "123456", "Test User")
        if result:
            print("SUCCESS: Brevo accepted the email request!")
        else:
            print("FAILED: Check the logs above for the Brevo error message.")
    except Exception as e:
        print(f"UNHANDLED ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test())
