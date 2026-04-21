import httpx
import json

CSE_TRADE_SUMMARY_URL = "https://www.cse.lk/api/tradeSummary"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/equity/trade-summary",
}

def check_cse_api():
    try:
        with httpx.Client(headers=DEFAULT_HEADERS, timeout=60) as c:
            response = c.post(CSE_TRADE_SUMMARY_URL)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Keys in data: {list(data.keys())}")
                raw_records = data.get('reqTradeSummery', [])
                print(f"Number of records in 'reqTradeSummery': {len(raw_records)}")
                if raw_records:
                    print("Sample record:", json.dumps(raw_records[0], indent=2))
                else:
                    print("Data returned:")
                    print(json.dumps(data, indent=2))
            else:
                print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_cse_api()
