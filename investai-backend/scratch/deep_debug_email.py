# deep_debug_email.py
import sys
import os
import asyncio
import httpx

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.email_service import _send
from app.config import get_settings

async def debug():
    settings = get_settings()
    print(f"Target Email: sanjeevsivasuthakaran@gmail.com")
    print(f"Sender Email: {settings.BREVO_FROM_EMAIL}")
    print(f"Using API Key: {settings.BREVO_API_KEY[:5]}...***")
    
    # Let's see if we can reach Google first to check connectivity
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get("https://www.google.com", timeout=5.0)
            print(f"Internet Connectivity: OK (Google responded with {res.status_code})")
    except Exception as e:
        print(f"Internet Connectivity: FAILED ({str(e)})")
        return

    # Now test Brevo
    print("\nAttempting Brevo API call...")
    html = "<h1>OTP Test</h1><p>Your code is 123456</p>"
    result = await _send("sanjeevsivasuthakaran@gmail.com", "Deep Debug Test", html)
    
    if result:
        print("\nRESULT: SUCCESS! Brevo says the email was sent.")
    else:
        print("\nRESULT: FAILED. Check the error logs above.")

if __name__ == "__main__":
    asyncio.run(debug())
