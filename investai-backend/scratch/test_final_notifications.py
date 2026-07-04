import httpx
import json

# --- CONFIGURATION (UPDATE THESE) ---
BASE_URL = "http://localhost:8000"
EMAIL = "test@example.com"  # Your test user email
PASSWORD = "password123"    # Your test user password
# ------------------------------------

def run_final_test():
    print("🌟 --- INVESTAI CONSOLIDATED NOTIFICATION TEST --- 🌟")
    
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        # 1. Login
        print(f"\n[1] Logging in as {EMAIL}...")
        login_res = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        
        if login_res.status_code != 200:
            print(f"❌ FAILED: Login failed. Status: {login_res.status_code}")
            return

        token = login_res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Success: Token received.")

        # 2. Register Firebase Token
        print("\n[2] Registering mobile device token for Push Alerts...")
        reg_res = client.post("/notifications/token", json={"fcm_token": "my-firebase-mobile-id-123"}, headers=headers)
        print(f"✅ Status: {reg_res.status_code} | msg: {reg_res.json().get('message')}")

        # 3. Trigger a REAL Market Alert (One function!)
        print("\n[3] Triggering 'Top Gainer' Alert from Market Data...")
        alert_res = client.post("/notifications/trigger-market-alert", headers=headers)
        
        if alert_res.status_code == 200:
            notif = alert_res.json()
            print("✅ Success: Market alert triggered!")
            print(f"📢 Notification Sent: {notif['message']}")
        else:
            print(f"❌ FAILED: Could not trigger alert. Status: {alert_res.status_code}")
            print(alert_res.text)

        # 4. Verify in List
        print("\n[4] Verifying the notification appears in your app list...")
        list_res = client.get("/notifications/", headers=headers)
        if list_res.status_code == 200:
            count = len(list_res.json())
            print(f"✅ Success: You have {count} notifications in your database.")
        else:
            print("❌ FAILED: Could not fetch list.")

if __name__ == "__main__":
    print("Note: Make sure your server is running (uvicorn) before starting this test.")
    try:
        run_final_test()
    except Exception as e:
        print(f"Error: {e}")
