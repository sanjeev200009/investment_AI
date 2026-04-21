import httpx
import asyncio
import json

async def debug_cse():
    url = "https://www.cse.lk/api/tradeSummary"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.cse.lk",
        "Referer": "https://www.cse.lk/equity/trade-summary",
    }
    
    print(f"Connecting to {url}...")
    try:
        # We use verify=False just in case the SSL issue returns during debug
        async with httpx.AsyncClient(headers=headers, timeout=30, verify=False) as client:
            r = await client.post(url)
            print(f"Status Code: {r.status_code}")
            try:
                data = r.json()
                print("--- JSON Keys Found ---")
                print(list(data.keys()))
                
                # Check for the two most likely key names
                records = data.get('reqTradeSummery') or data.get('reqTradeSummary')
                if records:
                    print(f"Found {len(records)} records!")
                    print("Sample Record:", json.dumps(records[0], indent=2))
                else:
                    print("No records found in known keys.")
                    print("Full Response Sample (First 200 chars):", str(data)[:200])
                    
            except Exception as e:
                print(f"Response is not JSON: {e}")
                print("First 500 chars of response:", r.text[:500])
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_cse())
