"""Read-only probe of cse.lk's company endpoints, for I-07.

I-05's probe established that ``companyInfoSummery`` and ``companyProfile`` both
answer 200 to ``{"symbol": "ABAN.N0000"}``, but not what they carry. I-07 needs to
know exactly that before a ``company_info`` table can be designed: which of
sector, EPS, P/E, shares outstanding and market cap are actually served, whether
they are served for every symbol or only for the liquid ones, and whether the
sector value is a code that joins to ``market_index_latest`` or free text that
does not.

Nothing here writes. It is in ``scratch/`` and not ``scripts/`` deliberately --
it is a one-off investigation, not re-runnable evidence, and pytest.ini excludes
this directory from collection.

    python -m scratch.probe_company_info
"""

import asyncio
import json

import httpx

from app.services.scraper import CSE_HEADERS

BASE = "https://www.cse.lk/api"

# A deliberate spread rather than the blue chips only. If fundamentals are served
# for JKH and not for a thinly traded counter, a table built off the liquid names
# would look complete in testing and be full of holes in use. CALC.U0000 is one of
# the 19 symbols whose close falls outside its own range (I-06's finding), so it
# is the least-traded end of the market; ABAN is what I-05 probed with.
SYMBOLS = [
    "JKH.N0000",     # largest by market cap
    "HNB.N0000",     # a bank, 288 trades
    "SAMP.N0000",    # a bank, 536 trades
    "HAYC.N0000",    # busiest session stored
    "ABAN.N0000",    # what the I-05 probe used
    "CALC.U0000",    # 1 trade -- the thin end
    "CIT.N0000",     # 2 trades, close outside range
    "SOY.N0000",     # 2 trades, close outside range
]

# POST-with-symbol endpoints seen in cse.lk's own network traffic. companyInfo is
# included on the chance it exists alongside the misspelt Summery one.
POST_ENDPOINTS = ["companyInfoSummery", "companyProfile", "companyInfo"]


def _preview(value, width=70):
    """A one-line rendering, so a 40-field dict stays readable."""
    text = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


async def _post(client, endpoint, symbol):
    try:
        r = await client.post(f"{BASE}/{endpoint}", data={"symbol": symbol},
                              headers=CSE_HEADERS, timeout=20)
    except Exception as exc:                                  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        return r.json(), None
    except Exception:                                         # noqa: BLE001
        return None, f"non-JSON ({len(r.text)} bytes)"


async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:

        # ── which endpoints exist at all ────────────────────────────────────
        print("=" * 72)
        print("Endpoint availability (POST symbol=JKH.N0000)")
        print("=" * 72)
        live = []
        for endpoint in POST_ENDPOINTS:
            body, err = await _post(client, endpoint, "JKH.N0000")
            if err:
                print(f"  {endpoint:22} FAILED  {err}")
                continue
            live.append(endpoint)
            shape = (f"dict, {len(body)} keys" if isinstance(body, dict)
                     else f"list, {len(body)} items" if isinstance(body, list)
                     else type(body).__name__)
            print(f"  {endpoint:22} 200     {shape}")

        # ── the full shape of each, once ────────────────────────────────────
        for endpoint in live:
            body, _ = await _post(client, endpoint, "JKH.N0000")
            print()
            print("=" * 72)
            print(f"{endpoint} — full field list for JKH.N0000")
            print("=" * 72)
            if isinstance(body, dict):
                for key in sorted(body):
                    value = body[key]
                    print(f"  {key:34} {type(value).__name__:6} {_preview(value)}")
            else:
                print(f"  {_preview(body, 200)}")

        # ── coverage across the liquidity spectrum ──────────────────────────
        # The question this answers: is a company_info table populable for all
        # 271 symbols, or only for the ones anyone trades?
        for endpoint in live:
            print()
            print("=" * 72)
            print(f"{endpoint} — coverage across {len(SYMBOLS)} symbols")
            print("=" * 72)
            for symbol in SYMBOLS:
                body, err = await _post(client, endpoint, symbol)
                if err:
                    print(f"  {symbol:12} {err}")
                    continue
                if not isinstance(body, dict):
                    print(f"  {symbol:12} {type(body).__name__}: {_preview(body, 50)}")
                    continue
                # Count how much of the payload is actually filled in. A dict of
                # 30 keys that are all None is a 200 that carries nothing.
                filled = {k: v for k, v in body.items()
                          if v not in (None, "", [], {}, 0)}
                print(f"  {symbol:12} {len(filled):2}/{len(body):2} fields filled")
                for key in sorted(filled):
                    print(f"                 {key:32} {_preview(filled[key], 46)}")

asyncio.run(main())
