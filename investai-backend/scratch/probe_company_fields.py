"""Second I-07 probe: expand the nested objects the first one only previewed.

``probe_company_info`` established that both endpoints answer for every symbol
tried, thin counters included, and that the payload is nested three deep. The
fields that matter for I-07 -- sector, EPS, P/E, shares outstanding, market cap --
are inside ``reqSymbolInfo``, ``reqSymbolBetaInfo`` and ``reqComSumInfo``, so this
prints those in full rather than truncated.

Read-only. See probe_company_info's docstring for why this lives in scratch/.

    python -m scratch.probe_company_fields
"""

import asyncio
import json

import httpx

from app.services.scraper import CSE_HEADERS

BASE = "https://www.cse.lk/api"

# One liquid name and one that barely trades. The comparison is the point: a field
# that is populated for JKH and null for CALC cannot back a tile that every stock
# in the app has.
SYMBOLS = ["JKH.N0000", "CALC.U0000"]

# The nested objects worth expanding, by endpoint. Logos, ads and PDFs are skipped
# -- they are assets, not fundamentals.
TARGETS = {
    "companyInfoSummery": ["reqSymbolInfo", "reqSymbolBetaInfo"],
    "companyProfile": ["reqComSumInfo", "infoCompanyBusinessSummary"],
}


def _show(obj, indent=6):
    """Print a dict's fields one per line, or a list's first element's."""
    pad = " " * indent
    if isinstance(obj, list):
        if not obj:
            print(f"{pad}(empty list)")
            return
        print(f"{pad}(list of {len(obj)}; first element:)")
        _show(obj[0], indent + 2)
        return
    if not isinstance(obj, dict):
        print(f"{pad}{obj!r}")
        return
    for key in sorted(obj):
        value = obj[key]
        if isinstance(value, str) and len(value) > 90:
            value = value[:87] + "…"
        print(f"{pad}{key:30} {type(obj[key]).__name__:9} "
              f"{json.dumps(value, default=str) if not isinstance(value, str) else value}")


async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for endpoint, keys in TARGETS.items():
            for symbol in SYMBOLS:
                r = await client.post(f"{BASE}/{endpoint}", data={"symbol": symbol},
                                      headers=CSE_HEADERS, timeout=20)
                body = r.json()
                for key in keys:
                    print("=" * 72)
                    print(f"{endpoint} · {key} · {symbol}")
                    print("=" * 72)
                    _show(body.get(key))
                    print()

asyncio.run(main())
