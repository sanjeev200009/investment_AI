import httpx
import json

URL = "https://www.cse.lk/api/indexSummary"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://www.cse.lk",
}

def check():
    try:
        with httpx.Client(headers=DEFAULT_HEADERS) as c:
            r = c.post(URL)
            print(f"POST {URL} -> {r.status_code}")
            if r.status_code == 200:
                print(json.dumps(r.json(), indent=2)[:1000])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
