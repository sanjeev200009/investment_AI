"""Sixth I-07 probe: is there an authoritative source for sector membership?

The full sweep showed ``reqComSumInfo.sector`` returns **38 distinct strings** for a
market with **20 industry-group indices**, and that they do not match the index
names:

    Food Beverage & Tobacco       34    (index name: "Food, Beverage & Tobacco")
    FOOD BEVERAGE & TOBACCO       10       - same sector, shouted
    Food, Beverage & Tobacco       2       - same sector, correct
    Real Estate Management & Development 18 (index: "Real Estate Management&Development")
    Diversified Financial          4    (index: "Diversified Financials")
    Capital Goods.                 1       - trailing period
    Materials (1510)               1       - GICS code appended
    45103010 - Application Software 1      - GICS code, sub-industry level
    - Property & Casualty Insurance 1      - leading dash, sub-industry level
    Banks Finance & Insurance      2       - the pre-2019 CSE sector name
    Trading / Services / Industrials / Power and Energy  1-2 each - also legacy

So a filter built on the raw string gives 38 chips, several of which are one sector
spelled three ways, and a "Food, Beverage & Tobacco" chip that finds 2 of 46
companies. A mapping table in code would fix it, but a mapping table is *my*
judgement about which group a company belongs to -- and for the legacy strings
("Industrials" is a GICS *sector* containing three industry groups) there is no
defensible single answer.

Before writing that table, check whether cse.lk publishes membership itself. If
``allSectors`` or a per-index endpoint lists constituents, the answer comes from
the exchange and no judgement is needed.

Read-only.

    python -m scratch.probe_sector_membership
"""

import asyncio
import json

import httpx

from app.services.scraper import CSE_ALL_SECTORS_URL, CSE_HEADERS

BASE = "https://www.cse.lk/api"

# Endpoint names visible in cse.lk's own market/index pages, plus plausible
# variants. A 404 is as informative as a 200 here.
CANDIDATES = [
    ("allSectors", {}),
    ("gicsSectors", {}),
    ("marketSummery", {}),
    ("companiesBySector", {"sectorId": "CG"}),
    ("companiesBySector", {"symbol": "CG"}),
    ("sectorWiseSummery", {}),
    ("indexList", {}),
    ("indexComposition", {"indexCode": "CG"}),
    ("aspiData", {}),
]


def shape(obj, depth=0, limit=3):
    """A compact description of a payload's structure, not its content."""
    pad = "  " * (depth + 1)
    if isinstance(obj, dict):
        out = []
        for k, v in list(obj.items())[:12]:
            out.append(f"{pad}{k}: {shape(v, depth + 1)}")
        return "{\n" + "\n".join(out) + "\n" + "  " * depth + "}"
    if isinstance(obj, list):
        if not obj:
            return "[] (empty)"
        return f"[{len(obj)} items] first = {shape(obj[0], depth + 1)}"
    text = str(obj)
    return text[:60] + ("..." if len(text) > 60 else "")


async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print("=" * 74)
        print("allSectors, in full -- does it name its members?")
        print("=" * 74)
        r = await client.post(CSE_ALL_SECTORS_URL, headers=CSE_HEADERS, timeout=25)
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            body = r.json()
            print(f"  top-level: {type(body).__name__}, "
                  f"{len(body) if hasattr(body, '__len__') else '?'} entries")
            first = body[0] if isinstance(body, list) and body else body
            print("  first entry, keys and values:")
            print(json.dumps(first, indent=4)[:1600])

        print()
        print("=" * 74)
        print("Other candidate endpoints")
        print("=" * 74)
        for name, payload in CANDIDATES:
            try:
                r = await client.post(f"{BASE}/{name}", data=payload,
                                      headers=CSE_HEADERS, timeout=25)
            except Exception as exc:                              # noqa: BLE001
                print(f"  {name:22} {str(payload)[:24]:26} ERROR {exc}")
                continue
            label = f"  {name:22} {str(payload)[:24]:26} HTTP {r.status_code}"
            if r.status_code != 200 or not r.content:
                print(label + ("  (empty body)" if not r.content else ""))
                continue
            try:
                body = r.json()
            except ValueError:
                print(label + "  non-JSON")
                continue
            print(label)
            print("    " + shape(body).replace("\n", "\n    ")[:900])


asyncio.run(main())
