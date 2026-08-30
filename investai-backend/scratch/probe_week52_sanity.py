"""Fourth I-07 probe: is ``week52_high`` safe to put on a tile?

The first three probes established what cse.lk serves and how completely. This one
exists because the full 291-symbol sweep surfaced something a two-symbol probe
could not: nine symbols whose current price sits *outside* their own published
52-week range, and two whose range spans more than 10x.

A 52-week range is the one field here that gets rendered next to the live price, so
a wrong one is not a null tile -- it is a tile that says the stock has fallen 94%
this year. That is the same class of defect I-07 exists to remove, so it has to be
measured before the tile ships, not after.

Two candidate explanations, distinguishable by direction and magnitude:

*   **Recalculation lag.** A stock that printed a new 52-week low *today* would sit
    just below a ``p12LowPrice`` computed before today's session -- a fraction of a
    percent out, and the range itself still plausible.
*   **Unadjusted pre-split prices.** ``allHiPrice`` is already known to be
    unadjusted (JKH: 430.25 against a 19.80 close). If ``p12HiPrice`` shares that
    flaw, the range's *high* is inflated by the split ratio and the range spans
    several multiples.

Read-only, against the database only -- no HTTP.

    python -m scratch.probe_week52_sanity
"""

from sqlalchemy import text

from app.database import SessionLocal

RATIO_BUCKETS = text("""
    SELECT count(*) FILTER (WHERE r < 2)                 AS under_2x,
           count(*) FILTER (WHERE r >= 2 AND r < 3)      AS x2_3,
           count(*) FILTER (WHERE r >= 3 AND r < 5)      AS x3_5,
           count(*) FILTER (WHERE r >= 5 AND r < 10)     AS x5_10,
           count(*) FILTER (WHERE r >= 10)               AS over_10x
    FROM (
        SELECT week52_high / week52_low AS r
        FROM company_info
        WHERE week52_low > 0 AND week52_high IS NOT NULL
    ) t
""")

WIDE_RANGES = text("""
    SELECT c.symbol, m.price, c.week52_low, c.week52_high,
           round((c.week52_high / c.week52_low)::numeric, 1) AS ratio,
           round((m.price / c.week52_low)::numeric, 2)       AS price_over_low
    FROM company_info c
    JOIN market_data_latest m ON m.symbol = c.symbol
    WHERE c.week52_low > 0 AND c.week52_high / c.week52_low >= 5
    ORDER BY c.week52_high / c.week52_low DESC
""")

DIRECTION = text("""
    SELECT count(*) FILTER (WHERE m.price > c.week52_high) AS above_high,
           count(*) FILTER (WHERE m.price < c.week52_low)  AS below_low,
           count(*)                                        AS comparable
    FROM company_info c
    JOIN market_data_latest m ON m.symbol = c.symbol
    WHERE c.week52_high IS NOT NULL AND c.week52_low IS NOT NULL
""")

# How far outside the range the outliers actually are. Recalculation lag would put
# them a fraction of a percent out; a wrong range would be orders of magnitude.
OUTLIER_MAGNITUDE = text("""
    SELECT c.symbol, m.price, c.week52_low, c.week52_high, m.volume,
           round((100.0 * abs(
               CASE WHEN m.price > c.week52_high
                    THEN m.price - c.week52_high
                    ELSE c.week52_low - m.price END
           ) / m.price)::numeric, 3) AS pct_outside
    FROM company_info c
    JOIN market_data_latest m ON m.symbol = c.symbol
    WHERE c.week52_high IS NOT NULL
      AND (m.price > c.week52_high OR m.price < c.week52_low)
    ORDER BY pct_outside DESC
""")

# A price near the bottom of a very wide range is what an unadjusted high looks
# like: the low is a real recent price, the high is a pre-split one, so the current
# price sits at a tiny fraction of the range.
DEEP_IN_RANGE = text("""
    SELECT c.symbol, m.price, c.week52_low, c.week52_high,
           round((100.0 * (m.price - c.week52_low)
                  / (c.week52_high - c.week52_low))::numeric, 1) AS pct_of_range
    FROM company_info c
    JOIN market_data_latest m ON m.symbol = c.symbol
    WHERE c.week52_high > c.week52_low
      AND (m.price - c.week52_low) / (c.week52_high - c.week52_low) < 0.02
    ORDER BY (m.price - c.week52_low) / (c.week52_high - c.week52_low)
""")


def main():
    db = SessionLocal()
    try:
        print("=" * 74)
        print("week52_high / week52_low ratio, all symbols with a range")
        print("=" * 74)
        print(" ", dict(db.execute(RATIO_BUCKETS).mappings().one()))

        print()
        print("=" * 74)
        print("Ranges spanning 5x or more")
        print("=" * 74)
        rows = db.execute(WIDE_RANGES).all()
        if not rows:
            print("  none")
        for r in rows:
            print(f"  {r[0]:12} price={r[1]:>10}  52w={r[2]}-{r[3]}  "
                  f"ratio={r[4]}x  price/low={r[5]}")

        print()
        print("=" * 74)
        print("Price outside its own range: which direction, and by how much")
        print("=" * 74)
        print(" ", dict(db.execute(DIRECTION).mappings().one()))
        print()
        for r in db.execute(OUTLIER_MAGNITUDE).all():
            print(f"  {r[0]:12} price={r[1]:>10}  52w={r[2]}-{r[3]}  "
                  f"{r[5]}% outside  vol={r[4]}")

        print()
        print("=" * 74)
        print("Price in the bottom 2% of its range (unadjusted-high signature)")
        print("=" * 74)
        rows = db.execute(DEEP_IN_RANGE).all()
        if not rows:
            print("  none")
        for r in rows:
            print(f"  {r[0]:12} price={r[1]:>10}  52w={r[2]}-{r[3]}  "
                  f"{r[4]}% of range")
    finally:
        db.close()


main()
