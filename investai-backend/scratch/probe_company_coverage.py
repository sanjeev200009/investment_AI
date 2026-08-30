"""Third I-07 probe: coverage and cost across the real symbol list.

The first two probes established *what* cse.lk serves. This one answers whether a
``company_info`` table is worth building, which turns on three numbers the earlier
probes could not give:

1.  **Fill rate per field, over a real sample.** JKH has a market cap and a
    12-month range; CALC.U0000 has neither. A tile is only worth building if the
    field behind it is populated for most of the market, and "most" has to be
    measured rather than assumed from two symbols.
2.  **Whether EPS or a P/E ratio is served anywhere.** The plan assumes a
    ``pe_ratio`` column. Neither probe found one, but they only expanded four
    nested objects out of thirteen. This walks every key at every depth and greps
    for it, so the conclusion is "not served" rather than "not found yet".
3.  **Seconds per symbol.** A refresh is two POSTs per symbol and there are ~271
    symbols. At 0.4s that is a 4-minute Celery task; at 3s it is 27 minutes and
    needs concurrency and a longer interval.

Read-only, and read-only against the database too -- it reads the symbol list from
``market_data_latest`` and writes nothing.

    python -m scratch.probe_company_coverage
"""

import asyncio
import sys
import time

import httpx
from sqlalchemy import text

from app.database import SessionLocal
from app.services.scraper import CSE_HEADERS

BASE = "https://www.cse.lk/api"

# How many symbols to sample. Pass 0 for the whole market: at the 0.15s per symbol
# the first run measured, all 291 costs ~45s, so there is no reason to extrapolate
# a fill rate from a sample. The 60-symbol default exists only so the first run is
# quick; the number quoted in the log comes from the full sweep.
#
# Sampling matters more than it looks. The first run took every 4th symbol ordered
# by volume and reported 100% fill on marketCap -- but CALC.U0000, which an earlier
# probe had already shown with marketCap NULL, was not in that sample. A 100% that
# excludes the known counter-example is not a 100%.
SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 60

# The fields I-07 would build a tile or a filter on.
WANTED = [
    ("companyInfoSummery", "reqSymbolInfo", "marketCap"),
    ("companyInfoSummery", "reqSymbolInfo", "quantityIssued"),
    ("companyInfoSummery", "reqSymbolInfo", "p12HiPrice"),
    ("companyInfoSummery", "reqSymbolInfo", "p12LowPrice"),
    ("companyInfoSummery", "reqSymbolInfo", "allHiPrice"),
    ("companyInfoSummery", "reqSymbolInfo", "allLowPrice"),
    ("companyInfoSummery", "reqSymbolInfo", "name"),
    ("companyInfoSummery", "reqSymbolInfo", "isin"),
    ("companyInfoSummery", "reqSymbolInfo", "parValue"),
    ("companyInfoSummery", "reqSymbolInfo", "ytdHiPrice"),
    ("companyInfoSummery", "reqSymbolBetaInfo", "triASIBetaValue"),
    ("companyInfoSummery", "reqSymbolBetaInfo", "betaValueSPSL"),
    ("companyProfile", "reqComSumInfo", "sector"),
    ("companyProfile", "reqComSumInfo", "boardType"),
    ("companyProfile", "reqComSumInfo", "established"),
    ("companyProfile", "reqComSumInfo", "web"),
    ("companyProfile", "infoCompanyBusinessSummary", "body"),
]

# Anything matching these, at any depth, would be an earnings figure.
EARNINGS_HINTS = ("eps", "earning", "peratio", "pe_", "priceearning", "dividend",
                  "yield", "navps", "bookvalue", "profit", "revenue", "netasset")


def _first(obj):
    """companyProfile wraps single records in a one-element list."""
    if isinstance(obj, list):
        return obj[0] if obj else None
    return obj


def _walk_keys(obj, depth=0, out=None):
    """Every key name anywhere in the payload, for the EPS search."""
    if out is None:
        out = set()
    if depth > 6:
        return out
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.add(key)
            _walk_keys(value, depth + 1, out)
    elif isinstance(obj, list):
        for item in obj[:2]:
            _walk_keys(item, depth + 1, out)
    return out


async def _fetch(client, endpoint, symbol):
    try:
        r = await client.post(f"{BASE}/{endpoint}", data={"symbol": symbol},
                              headers=CSE_HEADERS, timeout=25)
        return r.json() if r.status_code == 200 else None
    except Exception:                                         # noqa: BLE001
        return None


async def main():
    db = SessionLocal()
    try:
        # Spread across the liquidity range: every Nth symbol ordered by volume,
        # so the sample includes the untraded tail instead of 60 blue chips.
        rows = db.execute(text(
            "SELECT symbol FROM market_data_latest ORDER BY volume DESC NULLS LAST"
        )).all()
    finally:
        db.close()

    all_symbols = [r[0] for r in rows]
    if SAMPLE <= 0:
        sample, step = all_symbols, 1
    else:
        step = max(1, len(all_symbols) // SAMPLE)
        sample = all_symbols[::step][:SAMPLE]
    print(f"{len(all_symbols)} symbols in market_data_latest; "
          f"sampling every {step}th -> {len(sample)}")

    # Which symbols lack each field, not just how many. A fill rate says a tile is
    # mostly safe; the names say what it looks like when it is not, and whether the
    # gaps share a cause worth handling deliberately.
    missing: dict[tuple, list[str]] = {w: [] for w in WANTED}

    filled = {w: 0 for w in WANTED}
    every_key: set[str] = set()
    elapsed = 0.0
    failures: list[str] = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i, symbol in enumerate(sample, start=1):
            started = time.monotonic()
            summary, profile = await asyncio.gather(
                _fetch(client, "companyInfoSummery", symbol),
                _fetch(client, "companyProfile", symbol))
            elapsed += time.monotonic() - started

            if summary is None or profile is None:
                failures.append(symbol)
                continue

            every_key |= _walk_keys(summary) | _walk_keys(profile)

            bodies = {"companyInfoSummery": summary, "companyProfile": profile}
            for want in WANTED:
                endpoint, container, field = want
                record = _first((bodies[endpoint] or {}).get(container))
                if isinstance(record, dict) and record.get(field) not in (None, "", " "):
                    filled[want] += 1
                else:
                    missing[want].append(symbol)

            if i % 15 == 0:
                print(f"  ...{i}/{len(sample)}")

    ok = len(sample) - len(failures)
    print()
    print("=" * 72)
    print(f"Fill rate over {ok} symbols that answered "
          f"({len(failures)} failed: {', '.join(failures) or 'none'})")
    print("=" * 72)
    for want in WANTED:
        endpoint, container, field = want
        pct = (filled[want] / ok * 100) if ok else 0
        bar = "#" * round(pct / 5)
        print(f"  {container}.{field:22} {filled[want]:3}/{ok:<3} {pct:5.1f}%  {bar}")

    gaps = {w: syms for w, syms in missing.items() if syms}
    if gaps:
        print()
        print("=" * 72)
        print("Which symbols are missing what")
        print("=" * 72)
        for want, syms in gaps.items():
            shown = ", ".join(syms[:14]) + (f" +{len(syms) - 14} more" if len(syms) > 14 else "")
            print(f"  {want[1]}.{want[2]}  ({len(syms)})")
            print(f"      {shown}")

    print()
    print("=" * 72)
    print("Earnings-like keys anywhere in either payload")
    print("=" * 72)
    hits = sorted(k for k in every_key
                  if any(h in k.lower().replace("_", "") for h in EARNINGS_HINTS))
    print(f"  {', '.join(hits) if hits else 'NONE -- no EPS, P/E, dividend or NAV served'}")
    print(f"  ({len(every_key)} distinct keys walked across both endpoints)")

    print()
    print("=" * 72)
    print("Refresh cost")
    print("=" * 72)
    per = elapsed / max(1, ok)
    print(f"  {per:.2f}s per symbol (2 POSTs, issued concurrently)")
    print(f"  {len(all_symbols)} symbols -> {per * len(all_symbols) / 60:.1f} min serially")
    print(f"  at 8 symbols in flight -> ~{per * len(all_symbols) / 8 / 60:.1f} min")

asyncio.run(main())
