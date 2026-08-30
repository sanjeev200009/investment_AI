"""Fifth I-07 probe: can cse.lk's own fields identify a contaminated 52-week high?

``probe_week52_sanity`` established that ``p12HiPrice`` is unusable for 26 of 287
symbols: MERC reports a 12-month range of 22.0-10,999.0 while trading at 22.7,
CPRT 29.8-4,700.0 at 30.8. Those are nominal prices from before a forward split --
correct as printed at the time, meaningless beside a post-split price. Rendered on
a "52W HIGH" tile they say the stock is down 99.8% on the year.

Suppressing them needs a rule, and the rule has to come from the data rather than
from a threshold I picked. Three candidate discriminators, all derived from fields
cse.lk already serves:

1.  **``p12HiPrice == allHiPrice``.** If a symbol's 12-month high equals its
    all-time high, and its price is a tiny fraction of both, the 12-month window is
    reaching back past a split. JKH shows the fields *can* differ (23.9 vs 430.25),
    so equality is informative rather than universal.
2.  **``ytdHiPrice``.** A year-to-date high covers a shorter window than 12 months,
    so if the split predates January it would be clean where p12 is not. If YTD is
    equally inflated, the contamination is recent and this does not help.
3.  **``p12HiPrice`` vs the 12-month high of the *previous close* series** -- not
    available; daily_close holds one day.

This probe measures 1 and 2 against the 26 known-bad symbols and against a control
group of symbols whose range is plausible, so a rule can be judged on both its hit
rate and its false-positive rate. A rule that suppresses MERC but also suppresses
JKH is not a rule worth having.

Read-only. Re-fetches from cse.lk because ytdHiPrice is not a stored column.

    python -m scratch.probe_week52_discriminator
"""

import asyncio

import httpx
from sqlalchemy import text

from app.database import SessionLocal
from app.services.company_info import (CSE_COMPANY_SUMMARY_URL, _fetch_one,
                                       _first)

# The wide-range symbols from probe_week52_sanity, worst first.
SUSPECT = ["MERC.N0000", "YORK.N0000", "CPRT.N0000", "APLA.N0000", "NAMU.N0000",
           "SIGV.N0000", "COLO.N0000", "UML.N0000", "KCAB.N0000", "INME.N0000",
           "CDB.X0000", "CDB.N0000", "ACME.N0000", "PARA.N0000", "CWM.N0000",
           "WAPO.N0000", "BFL.N0000", "CHL.N0000", "HPWR.N0000", "CIC.N0000",
           "DOCK.N0000", "OFEQ.N0000", "SFCL.N0000", "GREG.N0000"]

# Controls: liquid symbols whose published range is credible. A discriminator must
# leave every one of these alone.
CONTROL = ["JKH.N0000", "HNB.N0000", "SAMP.N0000", "COMB.N0000", "DIST.N0000",
           "LOLC.N0000", "HAYL.N0000", "RICH.N0000", "EXPO.N0000", "MELS.N0000",
           "TJL.N0000", "AEL.N0000", "CCS.N0000", "LIOC.N0000", "HAYC.N0000"]


async def probe(symbols, label, prices):
    print()
    print("=" * 92)
    print(label)
    print("=" * 92)
    print(f"  {'symbol':12} {'price':>9} {'p12Low':>9} {'p12High':>10} "
          f"{'allHigh':>10} {'ytdHigh':>9}  p12==all  hi/price")
    hits = 0
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for symbol in symbols:
            body = await _fetch_one(client, CSE_COMPANY_SUMMARY_URL, symbol)
            info = _first((body or {}).get("reqSymbolInfo")) or {}
            p12_low = info.get("p12LowPrice")
            p12_high = info.get("p12HiPrice")
            all_high = info.get("allHiPrice")
            ytd_high = info.get("ytdHiPrice")
            price = prices.get(symbol)

            same = (p12_high is not None and p12_high == all_high)
            ratio = (p12_high / price) if (p12_high and price) else None
            hits += bool(same)
            print(f"  {symbol:12} {price!s:>9} {p12_low!s:>9} {p12_high!s:>10} "
                  f"{all_high!s:>10} {ytd_high!s:>9}  "
                  f"{'YES' if same else '.':>8}  "
                  f"{('%.1fx' % ratio) if ratio else '?':>8}")
    print(f"  -> p12HiPrice == allHiPrice for {hits}/{len(symbols)}")
    return hits


async def main():
    db = SessionLocal()
    try:
        prices = {s: p for s, p in db.execute(text(
            "SELECT symbol, price FROM market_data_latest")).all()}
    finally:
        db.close()

    bad = await probe(SUSPECT, "SUSPECT: ranges spanning 5x or more", prices)
    good = await probe(CONTROL, "CONTROL: credible ranges", prices)

    print()
    print("=" * 92)
    print("Verdict on 'p12HiPrice == allHiPrice' as a suppression rule")
    print("=" * 92)
    print(f"  catches {bad}/{len(SUSPECT)} suspects, "
          f"false-positives on {good}/{len(CONTROL)} controls")


asyncio.run(main())
