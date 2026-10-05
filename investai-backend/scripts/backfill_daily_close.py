"""Backfill daily_close from cse.lk's own price history (about one year per stock).

The scraper only records days it was running for, so any downtime leaves a hole in
the series that charts, the 52-week high, momentum and the price predictor read.
cse.lk's ``companyChartDataByStock`` (period=5) returns ~240 trading days of
high/low/close/volume per stock, which is what this fills from.

    python scripts/backfill_daily_close.py            # dry run: counts only
    python scripts/backfill_daily_close.py --apply    # insert

Safe to re-run:

*   **Insert only, ``ON CONFLICT DO NOTHING``.** A day the scraper already stored
    is never touched; the scraper's own row (with open, trades, turnover and the
    exchange's real last-trade time) always wins.
*   **Split-adjusted, like the rest of the table.** cse.lk's chart history is not
    restated for sub-divisions (MERC went 8,046 -> 39.4 overnight). CSE price bands
    stop an ordinary session moving anywhere near 40%, so a one-day ratio outside
    0.6x..1.6x is treated as a corporate action and every earlier day is scaled by
    it (volume inversely). Each adjustment is printed so it can be checked.
*   ``last_traded_at`` is the session close, 14:30 Colombo — the chart feed gives a
    date, not a trade time. ``open``, ``trades`` and ``turnover`` stay NULL: the
    feed does not carry them, and inventing them is worse than leaving them empty.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.stock import DailyClose  # noqa: E402

API = 'https://www.cse.lk/api/'
HEADERS = {'Origin': 'https://www.cse.lk', 'Referer': 'https://www.cse.lk/',
           'User-Agent': 'Mozilla/5.0 (InvestAI history backfill)',
           'Content-Type': 'application/x-www-form-urlencoded'}
COLOMBO = dt.timezone(dt.timedelta(hours=5, minutes=30))
SPLIT_LOW, SPLIT_HIGH = 0.6, 1.6


def post(endpoint: str, data: dict) -> dict:
    req = urllib.request.Request(API + endpoint, data=urllib.parse.urlencode(data).encode(),
                                 headers=HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def rows_for(symbol: str, points: list[dict]) -> tuple[list[dict], list[tuple]]:
    """chart points -> daily_close rows, oldest first, split-adjusted to today's scale."""
    by_day = {}
    for p in points:
        if p.get('p') is None or p.get('t') is None:
            continue
        # cse.lk stamps each point with Colombo midnight, in UTC milliseconds.
        day = dt.datetime.fromtimestamp(p['t'] / 1000, COLOMBO).date()
        by_day[day] = p
    days = sorted(by_day)
    factor, adjustments, out = 1.0, [], []
    for i in range(len(days) - 1, -1, -1):
        d, p = days[i], by_day[days[i]]
        scale = lambda v: None if v is None else round(v * factor, 4)  # noqa: E731
        out.append({
            'symbol': symbol, 'trade_date': d,
            'open': None, 'high': scale(p.get('h')), 'low': scale(p.get('l')), 'close': scale(p['p']),
            'volume': None if p.get('q') is None else p['q'] / factor,
            'turnover': None, 'trades': None,
            'last_traded_at': dt.datetime.combine(d, dt.time(14, 30), COLOMBO),
        })
        if i:
            prev = by_day[days[i - 1]]['p']
            ratio = p['p'] / prev if prev else 1.0
            if not SPLIT_LOW <= ratio <= SPLIT_HIGH:
                factor *= ratio
                adjustments.append((symbol, d, round(ratio, 4)))
    out.reverse()
    for prev_row, row in zip(out, out[1:]):
        row['previous_close'] = prev_row['close']
    if out:
        out[0]['previous_close'] = None
    return out, adjustments


def main(apply: bool) -> None:
    stocks = post('tradeSummary', {})['reqTradeSummery']
    print(f'{len(stocks)} listed stocks; fetching history (dry run)' if not apply else f'{len(stocks)} listed stocks; fetching history')
    db = SessionLocal()
    existing = {(s, d) for s, d in db.query(DailyClose.symbol, DailyClose.trade_date)}
    total_new, all_adj = 0, []
    try:
        for n, s in enumerate(stocks, 1):
            for attempt in range(3):
                try:
                    points = post('companyChartDataByStock', {'stockId': s['id'], 'period': 5}).get('chartData') or []
                    break
                except Exception as exc:  # noqa: BLE001
                    print('retry', s['symbol'], exc)
                    time.sleep(2)
            else:
                print('SKIPPED', s['symbol'])
                continue
            rows, adj = rows_for(s['symbol'], points)
            all_adj += adj
            new = [r for r in rows if (r['symbol'], r['trade_date']) not in existing]
            total_new += len(new)
            if apply and new:
                db.execute(pg_insert(DailyClose).values(new)
                           .on_conflict_do_nothing(index_elements=['symbol', 'trade_date']))
                db.commit()
            if n % 25 == 0:
                print(f'  {n}/{len(stocks)} stocks, {total_new} new rows so far')
            time.sleep(0.3)  # be polite to cse.lk
    finally:
        db.close()
    print(f'{"Inserted" if apply else "Would insert"} {total_new} daily_close rows')
    print(f'Split adjustments ({len(all_adj)}):')
    for a in all_adj:
        print('  ', *a)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--apply', action='store_true', help='write rows (default: dry run)')
    main(ap.parse_args().apply)
