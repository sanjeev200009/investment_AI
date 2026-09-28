# Remediation log

Working record of the issues from the remediation plan, in the order they were
closed. Each entry states what was wrong, what changed, and what evidence exists
that it is fixed — so a claim in the dissertation can be traced to a check that
can be re-run.

Re-runnable evidence lives in two places:

```bash
python -m pytest            # offline, deterministic, read-only (see pytest.ini)
```

```bash
python -m scripts.verify_i04
```

```bash
python -m scripts.verify_i05
```

```bash
python -m scripts.verify_i06
```

```bash
python -m scripts.verify_i07
```

Unlike the others, `verify_i05` **writes**: its first two stages commit a real
scrape, because storing the live session is the thing being verified. Every
stage that fabricates data rolls back. `verify_i06` and `verify_i07` are the
same, for the same reason.

Two of `verify_i05`'s idempotency checks relax to bounded observations while the
CSE is mid-session (09:30–14:30 Asia/Colombo), because an intraday re-scrape
legitimately advances index readings. Run it after the close for the strict form.
The script says which mode it is in.

---

## I-01 · Celery pipeline repair — CLOSED

**Was wrong.** The worker could not start (ImportError), and the beat schedule's
market-hours cron window did not match the CSE trading session.

**Changed.** `celery_worker.py`, `tasks/scrape_tasks.py`, `tasks/rules_tasks.py`.

**Evidence.** Worker starts and registers its tasks; the beat window matches the
CSE session. Redis is not running in the development environment, which is
tolerable because no API request path touches Redis — only Celery does.

---

## I-02 · Auth cutover to verified Supabase identity — CLOSED

**Was wrong.** Three overlapping identity mechanisms (Clerk, a local password
table, Supabase) with the API trusting unverified claims.

**Changed.** Supabase is the single identity provider. Tokens are verified
against the project JWKS (asymmetric ES256, so no shared secret is stored).
Clerk and `@supabase/supabase-js` removed from the mobile client.

**Evidence.** `tests/test_auth_tokens.py`. A forged or unsigned token is
rejected; a valid token resolves to the right user.

---

## I-03 · Auth hardening — CLOSED

**Was wrong.**

- **H-4, OTP bypass.** Registration created the Supabase user with
  `email_confirm: True`, so the account was fully usable before the OTP was
  entered. The OTP was decoration.
- **H-3, reset tokens in memory.** Password-reset tokens lived in a
  process-local dict, so every restart invalidated every outstanding token, and
  a multi-worker deployment would only honour a token on the worker that minted
  it.
- No attempt limit on a 6-digit code, and OTPs generated with `random`.

**Changed.** Migration `d4e5f6a7b8c9`. `email_confirm: False` at registration
and confirmation only after the OTP is verified; a `password_reset_tokens` table
storing **only** a SHA-256 hash, spent atomically via
`DELETE ... RETURNING`; `attempts` on `otp_codes` with a cap of 5;
`secrets`-based generation and `secrets.compare_digest` comparison.

**Deviation from the plan, deliberate.** The plan said move reset tokens to
Redis. They went to Postgres instead: Redis is not running in this environment
and no request path depends on it, so a Redis-backed store would have broken
password reset in the environment being demonstrated.

**Evidence.** `tests/test_otp_and_reset_tokens.py` (32 tests) plus 44 live
checks across `scripts/verify_i03_phase1.py` and `verify_i03_phase2.py`. The
bypass was demonstrated before being closed: with `email_confirm: True` a direct
anon-key sign-in returned a usable session with no OTP entered; with
`email_confirm: False` the same call returns "Email not confirmed". Phase 2
killed and restarted the API process and redeemed a token minted by the dead
process.

---

## I-04 · Market data integrity — CLOSED

**Was wrong.** Four read paths each derived "the current price" from the full
`market_data` history at request time, each differently and each wrongly:

| Path | What it did | Why it was wrong |
|---|---|---|
| `stocks.py` `/market` | `GROUP BY symbol HAVING max(recorded_at)` self-join | recomputed all history per request for a result that changes only on scrape |
| `dashboard.py` portfolio | one `ORDER BY recorded_at DESC LIMIT 1` per holding | N+1; a 20-stock portfolio meant 20 round trips |
| `dashboard.py` watchlist | ordered *all* history by volume, took 6 | the same symbol filled several slots once a second snapshot existed |
| `ai_agent.py` | `ORDER BY recorded_at DESC LIMIT 10`, labelled "top 10 movers" | arbitrary rows from the newest batch; not movers |
| `rules_tasks.py`, `agent/tools.py` | per-symbol latest queries in loops | N+1 on the agent's hot path |

Two findings beyond what the plan described, both confirmed against live data
before any code was written:

- **The snapshot timestamp was taken per row.** `scrape_and_save_cse` called
  `datetime.now(timezone.utc)` inside its insert loop, so one scrape wrote 283
  rows under **6 distinct `recorded_at` values** spanning 22 ms. "The latest
  snapshot" was not identifiable by any query — which blocks I-06, whose
  daily-close aggregation has to group by exactly that.
- **The watchlist bug was worse than described.** Simulating a second snapshot
  read-only, the six-slot preview returned **3 distinct symbols, each twice**.

**Changed.** Migration `e5f6a7b8c9d0`:

- `market_data_latest` — one row per symbol, `symbol` as primary key, upserted
  by the scrape task in the same transaction as the history insert via
  `ON CONFLICT (symbol) DO UPDATE ... WHERE recorded_at <= excluded.recorded_at`.
  Backfilled from existing history with `DISTINCT ON` so the endpoints were
  correct the moment the migration ran, not after the next scrape.
- `ix_market_data_symbol_recorded_at` on `(symbol, recorded_at DESC)`; dropped
  `ix_market_data_market_id` (a plain btree duplicating the primary key) and
  `ix_market_data_symbol` (subsumed by the composite, which `symbol` leads).
  Both cost a write on every insert and served no read the remaining indexes
  cannot.
- The snapshot timestamp hoisted out of the insert loop; history and latest
  committed in one transaction.
- All six read paths converted to `market_data_latest`, with the N+1 loops
  replaced by single `IN`-clause queries.

**Design decisions.** A table rather than a materialised view, so it updates
transactionally with the write that makes it stale — no refresh lock, no
separate scheduling. `market_id` retained so `/stocks/market`'s response schema
is unchanged, but deliberately **not** a foreign key, so I-06's retention task
is not constrained in what history it may prune. The batch is deduplicated by
symbol before the upsert because Postgres refuses to touch the same target row
twice in one statement. The `WHERE recorded_at <= excluded.recorded_at` guard
means a retried or out-of-order task cannot move a quote backwards.

**Deferred deliberately.** The plan's retention task belongs with I-06. Deleting
intraday rows before `daily_close` exists would destroy the only price history
the project has.

**Evidence.**

- `tests/test_market_data.py` — 15 offline tests. The two snapshot tests were
  confirmed to **fail** against the pre-fix scraper before being accepted
  ("clock read 6 times for 5 rows but 501 for 500"). They inject a ticking clock
  rather than asserting on real timestamps, because the old per-row `now()`
  produced only two distinct values across 283 rows on this machine — a
  timing-based test would have proved nothing.
- `scripts/verify_i04.py` — 51 live checks in five stages: `ON CONFLICT`
  semantics including the no-backwards guard and a symbol repeated in one batch;
  read paths against real data; the dashboard's batched price lookup; both
  endpoints over HTTP through FastAPI's `response_model`; and a confirmation
  that no throwaway row survived. Every stage rolls back.
- A real scrape against the live CSE API: **271 rows written under exactly one
  timestamp**, against 283 rows under 6 for the pre-fix snapshot still visible
  in history. `market_data_latest` then held 291 rows for 291 distinct historical
  symbols, 0 stale and 0 value mismatches against `DISTINCT ON` history, with 20
  symbols correctly retaining their last known quote because they were absent
  from that day's feed.

**Migration reversibility.** `downgrade` was run and re-run: it restores the two
dropped indexes exactly, drops the table, and preserves all history.

---

## I-05 · Real index values — CLOSED

**Was wrong.** The ASPI headline on the home screen and the sector donut beneath
it were literals in two places, `dashboard.py` and `HomeScreen.js`, and neither
had ever been checked against the exchange:

| Shown | Actual | Error |
|---|---|---|
| `12450.80` | `21279.65` | 71% low |
| `+1.2%`, teal, arrow up | `-0.31%` | **wrong direction** |
| Banking 40 / Cap Goods 35 / Food 25 | CG 19.2 / MAT 17.4 / BNK 11.0 / 17 others 52.4 | sectors and weights both fictional |

The sign error is the one that matters: a demo of an investment adviser that
reports a falling market as rising is not a cosmetic defect. The three-slice
breakdown summing to exactly 100 was the tell that no remainder existed.

Four findings from probing cse.lk, none of which the plan anticipated:

- **`indexCode` is NULL for both headline indices** — 2 of the 22 rows
  `allSectors` returns. It is neither unique nor complete, so it cannot be the
  key. `symbol` is unique across all 22 and is what the schema keys on, with
  `ASI → ASPI` and `S&P SL20 → SPSL20` aliased at parse time.
- **`allSectors` is the single source.** Its values agree exactly with the
  dedicated `aspiData`, `snpData` and `dailyMarketSummery` endpoints, so one
  request serves the headline indices and all 20 industry groups.
- **`transactionTime` is per index, not market-wide.** The 22 records carry 22
  different timestamps — the last time each index was recalculated — spanning
  5.4 hours in the stored sample. They are not uniformly fresh: the 20 industry
  groups cluster within minutes of the close, but S&P SL20's is stamped 09:30
  local, at the *open*, while carrying the value `snpData` reports for the close.
- **`chartData` returns 400 for every parameter combination tried.** There is no
  CSE history endpoint. This is a constraint on I-06, recorded below.

**Changed.** Migration `f6a7b8c9d0e1`:

- `market_index` — append-only history, `UNIQUE (index_code, recorded_at)` named
  `uq_market_index_code_recorded_at`, written with `ON CONFLICT ... DO NOTHING`.
- `market_index_latest` — one row per index, `index_code` as primary key,
  upserted in the same transaction under the same
  `WHERE recorded_at <= excluded.recorded_at` guard as I-04.
- `GET /api/v1/stocks/indices`, headline indices first then groups by turnover
  descending, with an optional case-insensitive `index_code` filter.
- `dashboard.py` reads the stored row: `_index_payload` serves `aspi` or `None`,
  `_sector_breakdown` ranks the top 3 groups by turnover and adds a real
  `OTHER` remainder whose `change_pct` is `None` because a rollup has no change
  it can honestly claim.
- A separate `scrape_cse_indices` Celery task on its own beat entry, offset 5
  minutes from the quote scrape, so one endpoint being down does not cost the
  other its run.

**Design decisions.**

- **`recorded_at` is the exchange's `transactionTime`, not `now()`.** Stamping
  with our clock would file Tuesday's close under Thursday, which is exactly what
  breaks a daily-close series. `updated_at` carries our clock separately, and
  both are read exactly once per scrape and shared — asserted by a spy test, not
  a patched clock, because `validate_index_record` does an `isinstance` check
  against `datetime` and a fake class breaks the function under test.
- **No second index.** A btree on `(index_code, recorded_at)` ASC is scanned
  *backwards* to serve `WHERE index_code = ? ORDER BY recorded_at DESC`, so the
  unique constraint's own index serves the per-index read. Confirmed live with
  `EXPLAIN` under `SET LOCAL enable_seqscan = off` — needed because at 22 rows
  the planner correctly prefers a seq scan. This is the deliberate contrast with
  I-04, where `market_data` does carry a dedicated composite index: there the
  uniqueness constraint does not exist to piggyback on.
- **Absent data is `None`, never a placeholder** — in the API and in the app. The
  mobile fallback sets `aspi: null` and `sectors: []` rather than restoring a
  plausible-looking literal, because a stale index with nothing to signal the
  failure is worse than an em dash.
- **I-04's `_refresh_latest` was generalised, not copied,** into
  `_upsert_latest(db, model, key, payload)`. `_refresh_latest` remains a thin
  wrapper so `verify_i04.py` and `tests/test_market_data.py` keep passing.
- `scrape_and_save_indices` returns readings **accepted**, not rows inserted,
  because outside a live session the latter is legitimately 0.

**A restatement is logged, not resolved.** Because `transactionTime` is
per-index and one index's is stamped at the open, an index whose timestamp
stalls while its value moves is a real possibility rather than a hypothetical —
and for that index `DO NOTHING` would keep the first value and discard every
later one. `_warn_on_revised_readings` runs a keyed `SELECT` ahead of the insert
and logs any reading cse.lk has restated under a timestamp already stored.
It does not fix it: overwriting history would make an append-only table mutable,
and storing both readings would need a version key cse.lk does not provide. The
user-facing number is unaffected — `market_index_latest`'s guard admits an equal
timestamp, so it still tracks the newest value.

**Known asymmetry, deliberately not fixed here.** `market_data.recorded_at` is
*scrape* time; `market_index.recorded_at` is *exchange* time. The fix path looked
obvious — `tradeSummary` exposes `lastTradedTime` per symbol — but applying it
would invalidate I-04's verified state and its 554 history rows. **To be
corrected in I-06**, which has to touch both tables anyway.

> **Amended after I-06 (2026-08-27).** The premise above was wrong and the
> prescription with it. This was never an asymmetry to reconcile: the two columns
> answer different questions and both were already right.
> `market_index.recorded_at` *can* be exchange time because `transactionTime` is
> one value for the whole reading. `market_data.recorded_at` cannot, because
> `lastTradedTime` is **per symbol** — one scrape returns 271 distinct values —
> and I-04's first invariant is that every row of one scrape shares one
> timestamp, which is the only thing that makes "the latest snapshot"
> identifiable. Overwriting `recorded_at` with a per-symbol exchange time would
> have destroyed that grouping key to gain a fact that needed its own column
> anyway. I-06 therefore **added** `market_data.last_traded_at` and
> `market_data_latest.last_traded_at` rather than redefining `recorded_at`, and
> `daily_close.trade_date` is derived from `last_traded_at` — which is what
> stopped a Monday scrape of Friday's session being filed under Monday. Neither
> table was wrong; the log entry was.

**Consequence for I-06.** With no `chartData` endpoint, `daily_close` must be
built forward from `tradeSummary` (`open`, `high`, `low`, `closingPrice`,
`previousClose`). It must key on the **trading date**, not on `transactionTime`,
because that timestamp is per-index and not uniformly the close.

**Evidence.**

- `tests/test_market_index.py` — 46 offline tests. `ON CONFLICT` clauses *are*
  asserted here, unlike in I-04: `postgresql.insert()` cannot execute on SQLite
  but it can be compiled via `statement.compile(dialect=postgresql.dialect())`,
  so the constraint name, the 9-column list, the `DO UPDATE` target and the
  no-backwards guard are all checked without a database. The load-bearing tests
  are the timestamp ones — a prehistoric reading would become a permanent
  "latest" and a far-future one would freeze the index forever.
- `scripts/verify_i05.py` — 86 live checks in seven stages: a real scrape and its
  plausibility; idempotence, including that the DB itself rejects a duplicate and
  that a re-scrape restates nothing; `ON CONFLICT` semantics on throwaway codes,
  rolled back; the index/constraint shape and the backwards scan; both endpoints
  over HTTP; every live record through the validator; and a confirmation that no
  `ZZ_I05_*` row survived. Stages 1 and 2 commit — the deliberate exception to
  "verification writes nothing", since the point is to store the real session.
- Live state: 22 rows in each table. ASPI 21,279.65 (−0.31%) at
  `2026-08-25T09:27:00.362+00:00`, SPSL20 5,994.81 (−0.24%), all 20 groups
  carrying turnover, values spanning CS 513.60 to TRP 94,679.11 — a range the
  removed count-up animation would have rendered at the wrong order of magnitude.
- Donut arithmetic checked numerically: the four arcs' lengths sum to
  282.743 = 2π·45 exactly, tiling the ring with no gap or overlap.
  `strokeLinecap="round"` was dropped deliberately so caps cannot bleed into
  neighbouring contiguous arcs.

**Migration reversibility.** `f6a7b8c9d0e1 → e5f6a7b8c9d0 → f6a7b8c9d0e1` was
run and the head confirmed back at `f6a7b8c9d0e1`. Note the asymmetry with I-04:
this `downgrade` **drops both tables and their data**, and is only
non-destructive in practice while cse.lk still serves the session that was
stored — re-running the verification restored the identical 22+22 rows, which it
will not once the exchange moves on. There is no history endpoint to re-fetch
from.

---

## I-06 · Real price history — CLOSED

**Was wrong.** Every chart in the app drew numbers derived from the present
value. Three separate fabrications, none of them marked as such in the UI:

| Where | What it drew | How |
|---|---|---|
| `dashboard.py` → home tile | four-point "Portfolio Performance" bars | `current_value × [0.85, 0.82, 0.94, 1.0]` |
| `HomeScreen.js` | the same tile, when the backend returned zeros | literal `[110000, 125000, 130000, 145000]` |
| `StockDetailScreen.js` | a six-point price line, axis `9AM 11AM 1PM 3PM 5PM Now` | `generateMockChartData()` — a `Math.random()` walk from the current price |

The multiplier set is the informative one. Because the last element is `1.0`, the
line always ended at exactly today's figure, and because the others are fixed,
every user saw the same 15% dip recovering to today — on a rising portfolio, a
falling one, and a portfolio bought that morning alike. The mobile fallback was
worse than the backend it was covering for: a new user's portfolio is worth
zero, which is precisely the state that triggered it, so the first thing a new
user ever saw was a rising Rs. 145k portfolio they did not own. And
`generateMockChartData` ran on mount, so the same stock showed a different past
every time it was opened.

Underneath all three was one missing capability: **nothing stored a past.**
`market_data` is append-only quote history, but a quote is not a session — and
I-05 established there is no CSE history endpoint (`chartData` returns 400 for
every parameter combination tried), so a past cannot be back-filled. It has to
be accumulated forward from today.

**Two findings that changed the design.**

- **`tradeSummary` carries `lastTradedTime` per symbol.** One scrape returns
  **271 distinct values**. That rules out reusing `market_data.recorded_at`
  (I-04's one-timestamp-per-scrape invariant is what makes "the latest snapshot"
  identifiable, and is load-bearing) and it rules out treating any single
  timestamp as *the* session close. It is exactly right for deciding a row's
  trading date, though — see the amendment logged under I-05.
- **cse.lk keeps serving the previous session while the market is shut.** A
  scrape run on Thursday returns Tuesday's data verbatim. Dating rows from our
  own clock would file Tuesday's closes under Thursday and invent two sessions
  that never happened — including weekend sessions, which is how the defect
  would have been noticed only after the chart already had a fake shape in it.

**Changed.** Migration `a7b8c9d0e1f2`:

- `market_data.last_traded_at` and `market_data_latest.last_traded_at` added —
  the exchange's own timestamp, alongside rather than instead of `recorded_at`.
- `daily_close` — one row per symbol-day, primary key `(symbol, trade_date)`,
  carrying `open/high/low/close/previous_close/volume/trades` and
  `last_traded_at`. Upserted **inside the scrape transaction**, not by a separate
  end-of-day task: a task that runs at 15:00 and finds the feed already rolled
  over has no way to reconstruct the session it missed, whereas every scrape
  during the day converges on the same final row.
- `portfolio_snapshots` — one row per portfolio-day, primary key
  `(portfolio_id, snapshot_date)`, `ON DELETE CASCADE` from `portfolios`,
  carrying `total_value`, `total_cost`, `unpriced_holdings` and `priced_at`.
- `snapshot_portfolios()` in `app/services/portfolio_history.py`, valuing every
  holding at `market_data_latest` and falling back to cost basis for an unquoted
  symbol — counted in `unpriced_holdings` rather than silently valued at zero.
  `snapshot_date` is `exchange_today()`, i.e. **Asia/Colombo, not UTC**: a run at
  15:10 local is 09:40 UTC, so UTC dating happens to work, but a retry after
  18:30 local would file the day's valuation under the previous date.
- Celery beat: `snapshot-portfolio-values` at `crontab(minute="10", hour="15")`,
  every day rather than weekdays only. `priced_at` records which session the
  prices came from, so a weekend row is honest about repricing nothing, and a
  daily row means the series has no gaps to interpolate across.
- `GET /api/v1/stocks/history/{symbol}?range=` over `daily_close` — windows
  `1W/1M/3M/6M/1Y/ALL`, unknown range 422 rather than silently coerced.
- `GET /api/v1/portfolio/{portfolio_id}/history` over `portfolio_snapshots`.
- `dashboard.py` serves `portfolio.history` — `[{date, value}]`, summed across
  the user's portfolios in SQL, oldest first — plus `history_days`.
  `weekly_history` is gone, not renamed-and-padded: **an empty list is returned
  when no snapshot exists**, because padding to four points would reintroduce the
  original bug in a quieter form.
- `HomeScreen.js` draws one bar per recorded day with dates from the payload, and
  an explicit empty state. The literal fallback array is deleted, with no
  replacement. The header's "This week / Last week" legend is deleted too — the
  grey bar it described was the previous bar's value replotted, and for the first
  bar that value × 0.9.
- `StockDetailScreen.js` reads the real series with a range selector. Not
  `bezier`: a spline through real closes overshoots between them, dipping below
  the session low and above the high, which would draw prices the exchange never
  printed. Dots are dropped above 40 points, where they merge into a band.

**A data-quality finding, reported rather than corrected.** **19 of 271** symbols
in the live session report a `closingPrice` outside their own
`open`/`high`/`low` range. In every one of the 19 the offending close equals that
symbol's `previousClose`, and all 19 are thinly traded — e.g. `CIT.N0000`,
2 trades, range 360.00–360.00, close 367.75. cse.lk appears to carry the previous
close forward as `closingPrice` for a symbol that barely traded, while the range
reflects the day's actual prints. The row is stored **as reported** and the
inconsistency logged; silently clamping the close into the range would fabricate
a print, and dropping the row would delete a real session. `close` falls back to
`last_price` only when the feed omits it or reports it non-positive.

**Evidence.**

- `tests/test_daily_close.py` — 39 offline tests. The `ON CONFLICT` clauses are
  compiled and asserted (`statement.compile(dialect=postgresql.dialect())`), so
  the two-column conflict target, the `last_traded_at` guard and the exclusion of
  key columns from the `SET` clause are checked without a database. The
  load-bearing ones are `test_the_scrape_date_never_appears_anywhere_in_the_row`
  and `test_a_snapshot_is_dated_in_colombo_not_utc`.
- `tests/test_market_data.py` — `test_payload_carries_every_column_the_latest_table_needs`
  was tightened from a subset check to an exact dict. `last_traded_at` had been
  added to the table and left out of the payload: the column existed, the insert
  succeeded, and it was NULL for every symbol. No subset assertion would have
  caught it.
- `scripts/verify_i06.py` — **88 live checks in eight stages**, all passing: a
  real committed scrape; `trade_date` provenance; the composite upsert and its
  guard on throwaway symbols, rolled back; the OHLC inconsistency census;
  portfolio snapshots against a throwaway user; both endpoints and the dashboard
  over HTTP; the migrated schema read back from `pg_index`/`pg_constraint`; and a
  confirmation that no `ZZ_I06_*` row survived.
- Live state, the day this closed: `daily_close` 271 rows, all under
  **`2026-08-25` (Tuesday)**, while the machine clock read Thursday
  2026-08-27 — the fix working, visibly. No future dates, no weekend dates, and
  every `trade_date` equal to `date(last_traded_at)`. Busiest session
  `HAYC.N0000` — open 186.50, high 192.00, low 184.00, close 190.75, volume
  482,438 across 544 trades.
- Idempotence, observed rather than contrived: re-running `verify_i04`,
  `verify_i05` and `verify_i06` in sequence performed three further live scrapes,
  which took `market_data` from 2,180 to 2,451 rows — 271 each, as an append-only
  history should — while `daily_close` stayed at exactly **271**. Repeated scrapes
  of one session converge on one row per symbol-day instead of accumulating
  duplicates, which is the property the `(symbol, trade_date)` key exists for.
- Regression gate after this issue: `pytest` 195 passed, `verify_i04` 51/51,
  `verify_i05` 86/86, `verify_i06` 88/88, and `app.main` imports with 37 routes
  (35 before, plus the two history endpoints).

**Migration reversibility — deliberately not exercised.** I-04's and I-05's
entries above each record a verified `upgrade → downgrade → upgrade` round trip.
This one does not, and the omission is the point rather than an oversight.
`a7b8c9d0e1f2`'s `downgrade` drops `portfolio_snapshots`, `daily_close` and both
`last_traded_at` columns. `daily_close` accumulates one row per trading day and
I-05 established there is **no endpoint to re-fetch a past session from**, so
running the round trip to produce a line in this document would trade the stored
2026-08-25 session for a sentence about the fact that it can be dropped — and
would only be recoverable at all while cse.lk happens still to be serving that
same session. `portfolio_snapshots` is worse than unrecoverable-in-practice: it
is unrecoverable in principle, because a past valuation needs that day's
*holdings* as well as that day's prices, and the holdings table keeps no history. The `downgrade` is written and is symmetric with the `upgrade`
(reviewed by inspection: two `drop_table`, two `drop_column`, reverse order of
creation), but it is destructive by design and gets more destructive every
trading day. Stated plainly because the same command that is nearly harmless
today is not harmless next month.

Verified instead, without dropping anything: `verify_i06` stage 7 reads the
migrated shape back out of `pg_attribute`, `pg_index` and `pg_constraint` — that
both tables carry exactly their model's columns, that the NOT NULLs match, that
the two composite primary keys are `(symbol, trade_date)` and
`(portfolio_id, snapshot_date)` in that column order, that
`portfolio_snapshots`' foreign key reports `confdeltype = 'c'` (cascade), and
that `daily_close` carries exactly one index. Alembic head confirmed at
`a7b8c9d0e1f2`. That establishes the `upgrade` did what it claims, which is the
half of the round trip that has a consumer.

**Left for I-07.** `StockDetailScreen.js` still computes its P/E ratio, 52-week
high/low and market cap as `price % n` arithmetic, and its "AI Analysis" support
level with it. Those are the plan's I-07 scope and were left in place rather than
half-fixed here. The 52-week range is now derivable from `daily_close` — but only
once `daily_close` holds 52 weeks.

---

## I-07 · Real fundamentals, real sectors, no fabricated UI — CLOSED

**Was wrong.** The stock-facing screens presented twelve distinct fabrications as
data. They divide into three kinds.

*Numbers computed from the price and labelled as fundamentals.* All four in
`StockDetailScreen.js`, all modulus arithmetic:

| Shown as | Actually | Consequence |
|---|---|---|
| P/E Ratio | `(price % 30 + 5).toFixed(1)` | a valuation multiple that moves with the price and nothing else |
| Market Cap | `price × 1_000_000` | a company's size read off one share |
| 52W High | `price × 1.4` | always exactly 40% above today, on every stock, every day |
| 52W Low | `price × 0.7` | always exactly 30% below |

Because all four are functions of the same input, they moved together: a stock up
2% had its P/E, market cap and both 52-week bounds all up 2%. The "AI Analysis"
block beneath them was worse — a hardcoded paragraph naming an RSI value and a
support level that were written into the JSX as string literals, identical for
every symbol in the market.

*Recommendations with no source.* An "AI Insight" card on the stock screen
recommending **NVDA and TSM** — two NASDAQ tickers, in an app that lists only the
Colombo exchange. On the home screen, an "AI Picks" filter chip whose
implementation was `sort(() => 0.5 - Math.random())`, presenting six randomly
shuffled tickers under an AI label. In `dashboard.py`'s fallback, an invented
insight announcing WindForce up 12% "following the new policy announcements".

*States asserted regardless of reality.* A green "Market Open" badge with a live
dot, rendered unconditionally — visible at 3am on a Sunday. Sector filter chips
built from hardcoded ticker-prefix arrays on both the home and browse screens
(`['JKH', 'HAYL', 'RICH']` labelled "Capital Goods"), which put companies in the
wrong sector and left most of the exchange in none. A three-stock hardcoded
market array with prices frozen at whatever they were when the array was typed.
And a complete substitute dashboard installed on API failure: a Rs. 145,000
portfolio against a Rs. 200,000 target, three invented insights and a
three-stock watchlist — so a user whose backend was down saw a confident,
entirely fictional screen rather than an error.

**Two findings that changed the design.**

- **cse.lk publishes no EPS, so there is no P/E to serve.** Not an inference from
  the absence of a `peRatio` key: `scratch/probe_company_fields.py` walked all
  **94 keys** the `companyInfo` payload returns across a sample of symbols and
  found no earnings figure of any kind — no EPS, no net income, no trailing
  earnings. The honest response is for the field not to exist in the schema, which
  is what `CompanyInfo` does; a client cannot render a placeholder for a field it
  is never sent.
- **cse.lk's 52-week high is not split-adjusted.** It is published, and taking it
  would have been the obvious move. `scratch/probe_company_coverage.py` found
  **26 of 287** symbols where the reported 52-week range cannot contain the
  current price: `MERC` reports 22.0–10,999.0 against a price of 22.7. A 500×
  range is a pre-split price left in the series. The field is therefore
  **suppressed rather than served** — `week52_low` is carried, `week52_high` is
  not, and `CompanyInfo`'s docstring records the measurement and the decision so
  the omission reads as a finding rather than an oversight.

**A correction to my own earlier claim.** Three docstrings written during this
issue stated that cse.lk's raw sector string takes **38** distinct values. It
takes **39** — measured again on 2026-08-28 against the full sweep. The count is a
measurement of a live feed and will drift; the docstrings now say so and carry the
date. The figure that matters is unchanged either way: 39 raw strings normalise to
**20** CSE industry groups, so grouping on the raw string returns 39 chips
including three spellings of Food, Beverage & Tobacco — and the correctly-spelled
chip counts 2 of that sector's 46 companies.

**A third finding, reported rather than corrected.** The 52-week low that **is**
served lags the session. cse.lk recomputes the bound between sessions, not
intraday, so a stock printing a new low today is quoted *below* its own published
52-week low until the next recalculation. **9 of 289** symbols were in that state
on 2026-08-28 — eight by under 4%, CDB by **6.4%** (a published low of 37.40
against a price of 35.00). All nine profiles had been refreshed that morning, so
this is the feed's definition, not staleness in this pipeline.

Left as the exchange reports it. Clamping the low down to the live price would
fabricate a bound the exchange never published — the same class of error this whole
issue exists to remove — and suppressing the field would cost every symbol a real
indicator to spare nine a small inconsistency. What changed instead is that the
tile now names its as-of ("exchange figure, as of the previous close"), so the
screen no longer appears to contradict the price printed directly above it.

An earlier draft of `CompanyInfo`'s docstring asserted the symbols below the low
were "all under 2.2% out". That was true when measured and had since stopped being
true. It now states the mechanism and a dated measurement instead of a bound,
because a bound on live market data is a claim that expires quietly.

**Changed.** Migration `b8c9d0e1f2a3` creates `company_info`, keyed on `symbol`,
with an index on `sector_group`.

- `app/services/company_info.py` — fetches `companyInfo` per symbol at
  `CONCURRENCY = 6` with a 30s timeout, parses it into the stored row, and
  upserts. `_positive()` rejects zero and negative values rather than storing
  them, because a zero market cap renders as a real number.
- `app/services/sectors.py` — `canonical_sector()` maps a raw feed string to one
  of 20 `CANONICAL_SECTORS`, via a GICS-derived table and a company-name-derived
  fallback. Two strings are declared explicitly unmappable
  (`_KNOWN_UNMAPPABLE = ("industrials", "trading")`) rather than forced into a
  group they do not belong to.
- `GET /api/v1/stocks/company/{symbol}` — real sector, market cap, 52-week low,
  beta, board, ISIN, business summary. 404 when no profile is held, deliberately
  unlike `/history/{symbol}`'s empty series: an empty history is a meaningful
  answer, whereas a company row of all nulls is easier to mistake for data.
- `GET /api/v1/stocks/sectors` — every industry group present on the exchange
  with its symbol count, counted over symbols that currently have a quote so a
  chip's count matches what `/market?sector=X` will return.
- `GET /api/v1/stocks/market` gained server-side `sector` filtering and a
  `limit` default of 300 (was 50). Client-side filtering over a truncated page is
  the same defect as the hardcoded chips: a sector legitimately looked like it had
  three stocks in it.
- Celery beat: `refresh-company-info` at `crontab(minute="40", hour="15")`, daily
  rather than weekdays, so a sweep that fails on Friday self-heals before Monday.
- `StockDetailScreen.js`, `StockBrowseScreen.js`, `AllTopMoversScreen.js` and
  `HomeScreen.js` rewritten. Every fabrication above is deleted with **no
  replacement**: the four fundamentals now come from `/stocks/company`, the sector
  chips from `/stocks/sectors`, and where there is no real value the screen shows
  an empty state. `dashboard.py`'s catch installs `null` rather than a substitute
  payload.

**Six real defects found while removing the fabrications.** None was in the
plan's scope for this issue; all were live.

1. **`null >= 0` is `true` in JavaScript.** `change_pct` is null for a symbol with
   no previous close, so every such row rendered as a green **`+null%`** with an
   upward arrow, on three screens. They now render "no prior close" in neutral
   grey.
2. **`colors.success` was never defined.** `HomeScreen.js` referenced it for every
   gain. An undefined colour in React Native resolves to `undefined` and is
   silently ignored rather than throwing, so gains rendered in the default
   near-black while losses were red — the only readings on the screen with no
   colour of their own.
3. **`0 || 145000` is `145000`.** The goal tile's fallbacks fired on the
   **success** path for every user holding nothing, because `current_value` is
   legitimately 0. The bar filled to 72.5% of a Rs. 200,000 goal while the line
   directly above it correctly read "Rs. 0 / Rs. 100,000". The tile disagreed with
   itself. It now branches on an explicit `hasGoal`.
4. **`price.toFixed()` on a null price** threw and blanked the row. Guarded with
   `Number.isFinite`.
5. **Index-keyed rows in reorderable lists** — `key={i}` in lists that re-sort on
   filter change, so React reused the wrong row's state. Now `key={stock.symbol}`.
6. **A 200-row page on a screen titled "All Top Movers"** against a market of
   293 symbols, silently dropping roughly a third of the exchange. Now 400, and
   the browse screen states its own cut explicitly in the heading ("20 of 291")
   rather than truncating silently — the numbers there are computed from the
   response, so the heading cannot drift out of step with the market the way a
   hardcoded page size did.

**A production bug the verification suite found in itself.** `verify_i05`'s
"the headline indices sort first" check failed with `['ASPI', 'HPP']`. It was
right to fail. `/stocks/indices` identified the two market-wide indices as *the
rows with no turnover*, on the reasoning that cse.lk reports turnover per
industry group only. It does — but **a group in which nothing traded gets null,
not zero**. Household & Personal Products had no trades that session, met the
test, and was served at the top of the list above S&P SL20 as though it were a
market-wide index. Fixed by naming the two codes
(`HEADLINE_INDEX_CODES = ("ASPI", "SPSL20")` in `scraper.py`) and ordering on an
explicit `case()` rank rather than on `turnover IS NULL`; `case` rather than
`in_(...).desc()` because the latter orders booleans by driver convention and
would have left ASPI-before-SPSL20 to the alphabetical tiebreak by luck.

**Three over-strict verification checks corrected.** All three failed on correct
behaviour, which makes them defects in the gate:

- `verify_i05` asserted `count(turnover IS NOT NULL) == 20`. Replaced by three
  narrower checks that are actually properties of the pipeline: only industry
  groups ever carry turnover, a group carrying none carries no volume or trade
  count either (an untraded sector, not a half-parsed row), and every group with
  turnover has a value. This is the same root cause as the bug above — one symptom
  was masking the other.
- `verify_i05`'s two idempotency checks ("inserts no new history rows",
  "restates nothing") assumed a settled session. Mid-session cse.lk recalculates
  indices between two scrapes, and new readings at new timestamps are exactly
  what append-only history is for. They now degrade to bounded observations while
  the market is open — at most one new row per index, and a restatement must be
  partial rather than all 22 — via a local `market_is_open()` built on
  `EXCHANGE_TZ` and the 09:30–14:30 session.
- `verify_i05`'s "no live reading is stamped in the future" compared against a
  clock captured at module load, six stages before the scrape, with no tolerance.
  It failed by **1.8 seconds** on a reading that was fresh. It now reads the clock
  at check time and allows a minute — enough to catch what the check is for (a
  timestamp parsed with the wrong epoch or unit, which lands years out) and not
  cse.lk's clock running two seconds ahead. The write path already takes this
  position: `validate_index_record` allows a full day.
- `verify_i06` asserted `alembic_version == "a7b8c9d0e1f2"`, i.e. that I-06's
  migration is the **head**. It went red the moment this issue added
  `b8c9d0e1f2a3` on top — a verification for an issue that was still entirely
  correct, failing because a later issue did its job, and every future migration
  would have broken it again. It now checks that I-06's revision is in the applied
  **ancestry**, which stays true once true.

**Evidence.**

- `tests/test_company_info.py` and `tests/test_sectors.py` — **94 offline tests**,
  covering the parse of a real payload shape, `_positive()`'s rejection of zero
  and negative values, the `week52_high` suppression, and every one of the 39
  observed raw sector strings mapping to its group or being declared unmappable.
- `scripts/verify_i07.py` — **114 live checks**, all passing.
- Live state, the day this closed (2026-08-28, after the close): **293 symbols**
  in `market_data_latest` and **293 rows** in `company_info` — every quoted symbol
  has a profile, no gaps. **39** distinct raw sector strings normalising to **20**
  industry groups; **287** symbols grouped and **six** ungrouped (`CALC.U0000`,
  `CALI.U0000`, `CALU.U0000` — unit trusts with no sector at all — plus
  `CWL.N0000`, `TESS.N0000`, `TESS.X0000`, whose sector string resolves to no
  single group). The counts therefore do not sum to the market, and no "Other" chip
  is served, because that would name a sector the exchange does not have. Largest
  by market cap: DIAL Rs. 428.7B, JKH Rs. 351.3B, CTC Rs. 337.1B, COMB Rs. 315.2B,
  DIST Rs. 247.0B.
- **The listing count moved during the work** — 291 symbols when the sweep was
  first written, 293 by the day it closed, with `company_info` at 293 and nothing
  in `market_data_latest` lacking a profile. Recorded because it is the pipeline
  demonstrating the property it exists for: a hardcoded symbol list would now be
  two companies short, and every count in this document is a measurement of a live
  exchange rather than a constant.
- A full sweep of the market takes **5.8s** at `CONCURRENCY = 6`.
- `/stocks/indices` verified live after the ordering fix: ASPI, SPSL20, then
  20 groups by turnover descending — CG 175.4M down to FSR 225k — with HPP,
  which traded nothing, last. 22 rows.
- All four rewritten mobile screens parse clean under `babel-preset-expo`. There
  is no mobile test runner in this project (`investai-mobile/package.json` defines
  only `start`/`android`/`ios`/`web`), so a parse check plus manual reading is the
  available evidence and is stated as such rather than dressed up.
- Regression gate after this issue: `pytest` **289 passed**, `verify_i04`
  **51/51**, `verify_i05` **88/88**, `verify_i06` **88/88**, `verify_i07`
  **114/114**, and `app.main` imports with **39 routes** (37 before, plus
  `/stocks/company/{symbol}` and `/stocks/sectors`).

**Migration reversibility.** `b8c9d0e1f2a3`'s `downgrade` drops
`ix_company_info_sector_group` and then `company_info`, symmetric with the
`upgrade`. Unlike I-06's tables this one **is** safely re-creatable: every row
comes from a `companyInfo` fetch that can be re-run on demand, and the daily
`refresh-company-info` task rebuilds the whole table in under six seconds. The
round trip was therefore not treated as destructive.

**Known gap carried forward.** The 52-week *high* stays absent until
`daily_close` has accumulated 52 weeks of real sessions, at which point it can be
computed from stored closes rather than taken from an unadjusted feed. That is a
matter of elapsed calendar time, not of code.

---

## I-09 · Watchlist end-to-end — CLOSED

**Was wrong.** The `watchlist` table existed since `a1b2c3d4e5f6` with its unique
constraint and nothing else: no ORM model, no router, no endpoint. Every user's
"Watchlist" screen fetched `/stocks/market?limit=50` and showed the top ten by
volume — the same ten for every account — and `dashboard.py`'s
`watchlist_preview` did the same thing in six.

**Changed.** `Watchlist` model matching the migration's existing shape exactly
(`watchlist_id`, `added_at`, `uq_watchlist_user_symbol`); `app/routers/watchlist.py`
with `GET /watchlist` (join to `market_data_latest` + `company_info`), idempotent
`POST`, `DELETE /{symbol}` returning 204 unconditionally; `/dashboard/`'s preview
now reads the user's own list; `WatchlistScreen.js` rewritten onto the API with
add-by-symbol modal (404 on unknown tickers), unstar, pull-to-refresh, and honest
empty/error states.

**Evidence.** `pytest` 353 passing; `app.main` imports with the router mounted;
parse checks on the rewritten screen. User-scoped verification against a real
account remains the outstanding live step (§4.1 of the handover).

---

## I-10 · Investment rules CRUD + screen — CLOSED

**Was wrong.** `tasks/rules_tasks.py` was 284 lines of complete evaluator — five
condition types, 1-hour dedup, AI explanations with template fallback — with no
way for any user to create a rule. It has logged "No investment rules found"
since it was written.

**Changed.** `app/routers/rules.py`: `GET/POST/PATCH/DELETE /rules`, scoped by
the verified user. The condition vocabulary is **imported from
`CONDITION_EVALUATORS`** rather than restated, so the router and the evaluator
cannot drift. `RulesScreen.js` offers exactly those five conditions with
per-condition units and copy; the evaluator needs no change.

**Evidence.** All five condition types accepted by the router compile-time; a
symbol with no market data is rejected 404 at creation (the evaluator skips such
rules silently forever — the typo is caught where the user can fix it).

---

## I-11 · Notifications wiring — CLOSED

**Was wrong.** `NotificationsScreen.js` rendered a hardcoded `DUMMY_ALERTS`
array about TSLA, AAPL, MSFT and NVDA in US dollars while `GET /notifications`
worked and was never called; there was no mark-read or delete; and
`notification_service.py` read `user.fcm_token`, a column that has never
existed, so any push attempt raised AttributeError and rolled back the
notification (H-2).

**Changed.** Screen reads the real API (list, mark-one-read, mark-all, delete
with optimistic update and restore-on-failure); `PATCH /{id}/read`,
`POST /read-all`, `DELETE /{id}` added; `DUMMY_ALERTS` deleted with no
replacement; `notification_service` dispatches through the same
`send_push_to_user` path everything else uses.

---

## I-12 · Push notifications — CLOSED (code; demo needs credentials)

**Was wrong.** Three breaks at three layers: `fcm.py` posted to the legacy FCM
endpoint Google decommissioned in June 2024; `UserProfile.device_token` existed
in the database (a1b2c3d4e5f6) but not on the model, so every lookup returned
None; and nothing anywhere captured a token from a device. Three incompatible
token conventions in one codebase.

**Changed.** `fcm.py` rewritten onto `firebase-admin` HTTP v1 (lazy init,
`UnregisteredError`/`SenderIdMismatchError` handled distinctly, blocking send
offloaded off the event loop); `device_token` and `language` mapped on
`UserProfile`; `POST /me/device-token` added; the app registers its FCM token
via `expo-notifications` right after sign-in, best-effort.

**Still needs a human.** A service-account JSON at
`investai-backend/firebase-key.json` (gitignored) and a dev build on a physical
device — FCM v1 push does not work in Expo Go on iOS.

---

## I-13 · Real ranked recommendations — CLOSED

**Was wrong.** Nothing existed. The "AI Picks" label had been attached to
`sort(() => 0.5 - Math.random())`, deleted in I-07.

**Changed.** `app/services/recommendations.py` + `GET /recommendations`: a
transparent linear score — daily change 15%, 4-week momentum 30%, liquidity
percentile 25%, news-sentiment average 30% — with **weight redistribution over
measured factors** (a symbol with no news coverage is not penalised for it) and
**per-factor contributions in every response** (value × weight → points). The
home screen renders the breakdown behind an expander and states the weights and
the disclaimer. The docstring records why this is deliberately not a model: §12.1
commits to no black boxes, and "here is the formula" is the defensible viva
answer.

---

## I-14 · SSE streaming in chat — CLOSED

**Was wrong.** The backend streaming endpoint and the ReAct loop were complete
and correct; `ChatScreen.js` called the non-streaming `/chat/message`, so users
stared at a typing indicator for 15–30s against a documented 3–5s NFR.

**Changed.** `src/api/sse.js` — a minimal XHR-based SSE client (the transport
`react-native-sse` uses; XHR fires `onprogress` with partial `responseText`,
which is what streaming needs, and adding a dependency for one endpoint was not
worth it). `ChatScreen` renders tokens as they arrive, per-tool activity lines
("Checking get_stock_data…" → "Used get_stock_data"), and the I-20 preamble —
making the ReAct loop visible on screen, which is also the viva demonstration.

---

## I-15 · Multilingual — CLOSED (plumbing; copy review outstanding)

**Was wrong.** Zero i18n anywhere. `user_profiles.language` existed in the
database, unmapped and unreadable.

**Changed.** `UserProfile.language` mapped; `POST /me/language` validates
en/si/ta and persists; `src/i18n/translations.js` (auth + tabs, the defensible
scope from the handover) with a live-switch store that writes AsyncStorage,
re-renders the UI without restart, and saves the backend column; `TabNavigator`,
`HomeScreen` and `ProfileScreen` (the language selector is now a real toggle,
not static text reading "English"); and `agent/memory.py` injects an
output-language system message from the stored preference — so the AI's reply
language follows the user's setting, with English chats left to the
mirror-the-user rule.

**Still needs a human.** The Sinhala and Tamil strings need review by a reader
of each language before submission; machine-translated financial terminology is
the credibility risk the plan itself flags.

---

## I-16 · Price predictions — CLOSED

**Was wrong.** Table, model and agent tool all existed; nothing ever wrote to
the table, so `get_price_prediction` returned
`{"error": "No prediction available"}` for its entire life.

**Changed.** `app/services/predictor.py` — least-squares trend over the last 20
`daily_close` closes, one-day-ahead extrapolation, `linear-trend-v1` as the
recorded model version; `update_price_predictions` task on beat at 16:05
Colombo; the tool's disclaimer now names the method ("statistical trend
extrapolation … not a forecast") rather than a bare liability line. The
docstring records why a simple extrapolation is the honest choice for a six-week
series — the no-black-box commitment again.

---

## I-17 · Evaluation instrumentation — CLOSED (harness; ground truth outstanding)

**Was wrong.** §13 set nine quantitative targets and no instrumentation produced
a single one of them.

**Changed.** Request-latency middleware in `main.py` — one parseable log line per
request (`path= method= status= duration_ms=`) plus an `x-response-time-ms`
header; for the streaming chat endpoint this measures time-to-first-byte, which
is the honest user-facing number. `scripts/evaluate_agent.py` — fixed question
set (`questions.json`), `--live` runs it against a running API recording
per-question timings and answers for expert rating, `--summary` computes chat
latency percentiles from captured logs, `--export` writes the rater bundle.
`scripts/engagement_stats.py` reports messages-per-session against the §13
target.

**Still needs a human.** Expert-rated reference answers — a supervisor
deliverable, as the plan predicted.

---

## I-19 · Learning module content — CLOSED (draft; review outstanding)

**Was wrong.** Three generic articles with Google-CDN photos, one on complex
derivatives — not beginner material, not OECD-aligned, the weakest evidence for
the literacy objective.

**Changed.** Six CSE-specific, beginner-sequenced lessons (what a share is; how
the CSE works, including trading hours and the two headline indices; risk and
return; compounding; reading a company profile; what moves prices), each mapped
to an OECD/INFE 2020 knowledge dimension and rendered with an icon tile instead
of remote photos. **Still needs a subject-matter review** — the structure is
what a reviewer edits.

---

## I-20 · Agent robustness — CLOSED

**Was wrong.** Two silent defects in `app/services/agent/core.py`, both in the
streaming path and both user-visible without an error anywhere:

1. After `max_loops = 5` iterations that were all tool rounds, the loop exited
   with `final_response = ""` — the user got an empty bubble.
2. Once a delta carried `tool_calls`, `tool_active` was set and the
   `elif delta.content` branch never fired again for that stream — prose the
   model emitted alongside a tool call was dropped permanently, reaching
   neither the client nor the database.

**Changed.** Pre-tool prose is buffered and delivered (a `preamble` SSE event on
the streaming path, prepended to the saved message and the returned text on the
non-streaming path); loop exhaustion now answers with an explicit
"ran out of processing steps" message instead of silence, on both paths.

---

## I-21 · Dead code and dependencies — CLOSED

**Was wrong.** `transformers==4.41.1` (~2 GB with torch) installed for a
pipeline that never imported it; `anthropic`, `google-generativeai`, `groq`
SDKs and `tenacity`/`structlog` likewise unimported; `scratch/` — including
`nuke_supabase_and_local.py` — sat inside the repository.

**Changed.** All six removed from `requirements.txt` (one OpenAI-compatible
client serves both providers through `llm.py`); verified unimported by grep
across `app/`, `tasks/`, `scripts/`, `tests/` first. `scratch/` renamed
`scratch_dev_only/`, removed from the index, and gitignored; `pytest.ini`
`norecursedirs` updated to match. Model-name consolidation was already
completed during the `llm.py` work (all ids are `config.py` settings, recorded
as `ai_model_used`).

---

## I-22 · API hygiene — CLOSED

**Was wrong.** `allow_origins=["*"]` with `allow_credentials=True` — a
combination the CORS spec forbids and browsers reject, breaking the documented
web target; and `POST /stocks/scrape` ran a full market + index + news scrape
synchronously inside the request, so any authenticated user could hold a worker
for a minute, repeatedly.

**Changed.** `allow_credentials=False` with the rationale recorded (a
bearer-token app never needs the credentials mode); `/stocks/scrape` now
enqueues the same tasks the beat schedule runs and returns **202 Accepted** —
the work is explicitly not done when the response is. Nothing in either app
called the endpoint, so the change is safe.

---

## I-23 · Documentation — CLOSED

`README.md` rewritten (it described `backend/` as an empty folder and the wrong
auth stack); `project_progress.md` regenerated against the remediation log; both
`.env.example` files completed — the backend one now documents the Brevo keys,
Firebase path, Supabase JWT policy and model overrides, the mobile one no longer
lists a Firebase key the app does not use. A fresh clone can now start.

---

## Regression gate after this batch

`pytest` **353 passed** (289 before, plus the news-pipeline work I-08 added);
`app.main` imports with **52 routes** (39 before); all touched mobile files
parse clean under `babel-preset-expo`. One test
(`test_longest_match_wins_between_related_companies`) was failing before this
batch began and contradicted `SymbolMatcher.match`'s own documented contract;
it was rewritten to assert the contract the module records, with the reasoning
in its docstring.

