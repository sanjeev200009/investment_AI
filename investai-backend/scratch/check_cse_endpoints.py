import httpx
import json

ENDPOINTS = [
    "https://www.cse.lk/api/marketStatus",
    "https://www.cse.lk/api/tradeSummary",
    "https://www.cse.lk/api/latestPrice"
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/equity/trade-summary",
}

def check_endpoints():
    for url in ENDPOINTS:
        print(f"\n--- Checking {url} ---")
        try:
            with httpx.Client(headers=DEFAULT_HEADERS, timeout=30) as c:
                if "tradeSummary" in url or "latestPrice" in url or "marketStatus" in url:
                    response = c.post(url)
                else:
                    response = c.get(url)
                
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(json.dumps(data, indent=2)[:500] + "...")
                else:
                    print(response.text[:200])
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_endpoints()
