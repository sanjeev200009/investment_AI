# InvestAI — hand-over

Written 2026-08-28. Branch `claude/competent-solomon-ed082e`, **nothing committed** —
all of the work described here is in the working tree.

This document says three things: what state the system is in, how to run and
re-verify it, and what is left. It does not restate the remediation plan; that
lives at `C:\Users\user\.claude\plans\velvety-jingling-garden.md` and the
issue-by-issue record lives in
[REMEDIATION_LOG.md](investai-backend/docs/REMEDIATION_LOG.md).

---

## 1. Where the project stands

Seven of the plan's 23 issues are closed: **I-01 … I-07**. Sixteen remain, all
scoped and prioritised in the plan.

| | Issue | State |
|---|---|---|
| I-01 | Celery pipeline repair | CLOSED |
| I-02 | Auth cutover to verified Supabase identity | CLOSED |
| I-03 | Auth hardening (OTP bypass, reset tokens) | CLOSED |
| I-04 | Market data integrity | CLOSED |
| I-05 | Real index values | CLOSED |
| I-06 | Real price history | CLOSED |
| I-07 | Real fundamentals, real sectors, no fabricated UI | CLOSED |
| I-08 … I-23 | see §5 | open |

**What that adds up to.** Every number the app shows on its market, stock,
dashboard and portfolio surfaces is now either measured from the Colombo Stock
Exchange or absent. Nothing is computed from the price and labelled as a
fundamental; nothing is a hardcoded array; nothing is `Math.random()` presented as
AI output. Where a value does not exist the screen says so rather than
substituting one — that was a deliberate and repeated choice, and it is the part
of this work most worth defending in a viva.

The counts, measured live on 2026-08-28 after the close:

- **293** listed symbols, each with a quote in `market_data_latest`
- **293** company profiles in `company_info` — no quoted symbol lacks one
- **22** index readings (ASPI, S&P SL20, 20 industry groups)
- **39** distinct raw sector strings from cse.lk normalising to **20** industry groups
- **519** stored daily closes, accumulating one point per symbol per trading day
- **0** users — see §4, this is the one thing blocking an end-to-end demo

### What was removed, and this matters more than what was added

Twelve fabrications were serving as data before this work. The full list with
mechanisms is in the I-07 entry of the remediation log; the short version:

- Four "fundamentals" on the stock screen computed as modulus arithmetic on the
  live price — a P/E of `(price % 30 + 5)`, a market cap of `price × 1,000,000`,
  and 52-week bounds fixed at exactly ±40%/−30% of today, on every stock.
- An "AI Analysis" paragraph with a hardcoded RSI and support level, identical for
  every symbol in the market.
- An "AI Insight" card recommending **NVDA and TSM** — NASDAQ tickers, in a
  Colombo-exchange app.
- An "AI Picks" filter implemented as `sort(() => 0.5 - Math.random())`.
- A permanently green "Market Open" badge, visible at 3am on a Sunday.
- Sector filter chips built from hardcoded ticker-prefix arrays.
- A whole substitute dashboard installed on API failure: a Rs. 145,000 portfolio
  against a Rs. 200,000 target, three invented insights including one announcing
  WindForce up 12% "following the new policy announcements".

### Six real bugs found while removing them

None was in the plan. All were live and user-visible.

1. `null >= 0` is `true` in JavaScript, so every symbol with no previous close
   rendered as a green **`+null%`** with an upward arrow, on three screens.
2. `colors.success` was referenced for every gain and never defined. An undefined
   colour in React Native is silently ignored, so gains rendered near-black while
   losses were red.
3. `0 || 145000` is `145000`, so the goal tile's "error fallback" fired on the
   **success** path for every user holding nothing — the bar filled to 72.5% of a
   Rs. 200,000 goal while the line above it correctly read "Rs. 0 / Rs. 100,000".
4. `price.toFixed()` on a null price threw and blanked the row.
5. `key={i}` in lists that re-sort on filter change, so React reused the wrong
   row's state.
6. A 200-row page on a screen titled "All Top Movers", against a 293-symbol
   market.

### One production bug the verification suite found in itself

`/stocks/indices` identified the two market-wide indices as *the rows with no
turnover*, because cse.lk reports turnover per industry group only. It does — but
**a group in which nothing traded gets null, not zero**. Household & Personal
Products traded nothing one session, met the test, and was served at the top of
the list above S&P SL20 as though it were a market-wide index. Now ordered on an
explicit rank over two named codes.

This is worth mentioning in the viva as evidence the verification layer earns its
keep: the check that caught it was written for I-05 and the bug was introduced by
reasoning that looked sound.

---

## 2. How to run it

### Backend

```bash
cd investai-backend && python -m uvicorn app.main:app --reload --port 8000
```

Docs at `http://localhost:8000/api/v1/docs`. `docs_url=None` in `main.py` with a
manually-served CDN Swagger is **deliberate**, not a mistake — I-22 asks for that
to be written down in the README, which has not been done yet.

All 39 routes are under `/api/v1`. A request without that prefix 404s, which has
caught me out more than once.

### Migrations

```bash
cd investai-backend && python -m alembic upgrade head
```

Head is `b8c9d0e1f2a3`. Schema comes **solely** from Alembic — there is no
`create_all` anywhere in the backend, deliberately, so the migration chain is the
only description of the schema.

### Mobile

```bash
cd investai-mobile && npx expo start
```

**Run `npm install` first.** Clerk and `@supabase/supabase-js` are gone from the
source but still in `package-lock.json`; the install is what drops them. This
worktree has no `node_modules` at all.

### Celery

```bash
cd investai-backend && python -m celery -A celery_worker.celery_app worker --loglevel=info --pool=solo
```

```bash
cd investai-backend && python -m celery -A celery_worker.celery_app beat --loglevel=info
```

`--pool=solo` because the default prefork pool does not work on Windows.

**Redis is not running locally**, so neither of the above will connect. That is
tolerable for a demo of the app itself: no API request path touches Redis, only
Celery does. It is not tolerable for demonstrating the scheduled pipeline — for
that, start Redis first.

Beat crontabs are evaluated in **Asia/Colombo**, and the CSE trades 09:30–14:30
local. `refresh-company-info` runs at 15:40, `snapshot-portfolio-values` at 15:10,
both daily rather than weekdays, so a run that fails on Friday self-heals before
Monday's open.

---

## 3. How to re-verify it

This is the part to run before a viva, and the part to point at when asked how you
know it works.

```bash
cd investai-backend && python -m pytest
```

**289 tests, offline, deterministic, read-only** — `pytest.ini` enforces that, and
`scratch/` is excluded from collection. No test touches Postgres or the network,
so this is the one command that is safe to run anywhere, any time.

Five live verification scripts, each covering one closed issue:

```bash
cd investai-backend && python -m scripts.verify_i04
```

```bash
cd investai-backend && python -m scripts.verify_i05
```

```bash
cd investai-backend && python -m scripts.verify_i06
```

```bash
cd investai-backend && python -m scripts.verify_i07
```

```bash
cd investai-backend && python -m scripts.verify_llm_providers
```

**Current results, all passing:** pytest 289; i04 51/51; i05 88/88; i06 88/88;
i07 114/114; LLM providers 27/27. `python -c "import app.main"` succeeds and
reports 39 routes.

Three things to know before running them:

- **`verify_i05`, `verify_i06` and `verify_i07` write.** They commit a real scrape,
  because storing the live session is the thing being verified. Every stage that
  fabricates data rolls back, and each ends by confirming no `ZZ_*` throwaway row
  survived.
- **Two of `verify_i05`'s idempotency checks relax while the market is open**
  (09:30–14:30 Asia/Colombo), because an intraday re-scrape legitimately advances
  index readings. The script prints which mode it is in. Run it after the close for
  the strict form.
- On Windows, prefix with `PYTHONIOENCODING=utf-8` — the console is cp1252 and the
  scripts print box-drawing characters.

Auth verification, from I-03:

```bash
cd investai-backend && python -m scripts.verify_i03_phase1
```

```bash
cd investai-backend && python -m scripts.verify_i03_phase2
```

Phase 2 kills and restarts the API process and then redeems a reset token minted
by the dead process — that is the point of it, so expect it to take a while.

There is **no mobile test runner**. `investai-mobile/package.json` defines only
`start`/`android`/`ios`/`web`. The available evidence for the mobile work is a
`babel-preset-expo` parse check plus reading, and it is stated that way rather
than dressed up. If you want a runner, that belongs in I-18.

---

## 4. What I need from you

Ordered by how much it blocks.

### Blocking a demo right now

1. **Register an account from the app and confirm you can log in.** The `users`
   table is **empty**. Every user-scoped feature — portfolio, watchlist,
   notifications, chat history, the risk profile — is untestable end to end until
   one real account exists. Everything server-side is verified against throwaway
   users that are rolled back; what has not been exercised is the app's own
   registration screen against the live Supabase project.
2. **Confirm Brevo delivers the OTP.** I-03 made the account genuinely unusable
   until the OTP is verified, which is correct and also means a mail failure now
   blocks registration completely rather than being cosmetic.
3. **`npm install` in `investai-mobile`.**
4. **`EXPO_PUBLIC_API_BASE_URL`** — its value, and whether the backend is
   local + ngrok or deployed. I-14 needs to know because some tunnels buffer SSE
   and would defeat streaming.

### Security — please do this regardless

5. **Rotate the OpenRouter and NVIDIA API keys.** Both were pasted into our
   conversation and should be treated as disclosed. The provider chain is verified
   working (27/27) against the current keys, so rotation is a config change, not a
   code change.
6. **`CLERK_SECRET_KEY` is still in `.env`** and can be deleted. Clerk is gone
   from the source entirely.

### Decisions only you can make

7. **Your viva or submission date.** This governs two issues. `daily_close`
   accumulates one point per symbol per trading day and there is no CSE history
   endpoint to back-fill from, so the length of your price charts is a function of
   elapsed calendar time. Same for the 52-week high, which stays absent until the
   series is a year long. If the date is close, both need a different framing in
   the write-up rather than more code.
8. **Payhere.** It appears in §9 and §15 of your documentation and nothing
   implements it. My recommendation: remove it from those sections and state it as
   future work. Building a payment integration for a dissertation demo is
   disproportionate, and leaving it documented-but-absent is the kind of gap an
   examiner finds.
9. **Sinhala and Tamil translations (I-15).** Who produces them. This is the real
   cost of that issue, not the plumbing. Machine-translated financial terminology
   is a genuine credibility risk for a dissertation about Sri Lankan investors —
   an examiner who reads either language will notice. Also: which screens must be
   translated, since full coverage is a lot of strings and the auth flow plus the
   five main tabs is a defensible scope.
10. **The evaluation question set with expert-rated answers (I-17).** I can build
    the harness; I cannot supply ground truth for Sri Lankan market advice. Also
    tell me which of your §13's nine metrics your supervisor treats as mandatory —
    instrumenting all nine is more work than instrumenting the four that carry your
    argument.
11. **Which of the five rule condition types to expose in the UI (I-10)** —
    `price_above`, `price_below`, `change_pct_up`, `change_pct_down`,
    `volume_spike`, or all five. The evaluator is already written and good; it is
    waiting on a way for a user to create a rule.
12. **The recommendation weighting (I-13)**, or approval for me to propose one. For
    the dissertation the defensible route is a simple transparent linear score with
    stated weights, not a tuned black box.
13. **Whether a university or CSE official data feed, or a historical CSV, exists.**
    If one does it changes I-05, I-06 and I-07 substantially — most of all the
    52-week high.
14. **Supabase plan limits** — row and storage caps, and how long you want history
    retained. `market_data` is append-only and grows by ~293 rows per scrape.

### Needed for specific later issues

15. **A Firebase service-account JSON** for I-12, at
    `investai-backend/firebase-key.json`, gitignored. Do not paste its contents to
    me. I-12 also needs one physical device and a dev/EAS build — push does not
    work in Expo Go on Android for FCM v1.
16. **Confirmation that the three news sources are the ones you want** (ft.lk,
    dailymirror.lk, economynext.com) for I-08, and whether their terms allow
    article-page fetching at that volume. Worth a sentence in your ethics chapter
    either way; I will check `robots.txt` as part of the work.
17. **Learning module content (I-19)**, or approval for me to draft it — plus which
    OECD/INFE framework version you cite, so the mapping is against the right one.

---

## 5. What is left

Straight from the plan, with the dependencies that actually matter.

### P1 — features the documentation claims and the code does not have

- **I-08 · News pipeline.** `GET /stocks/news/{symbol}` returns empty for every
  real ticker: every article is attributed `'GENERAL'`, `summarise_article()` is
  defined and called from nowhere, `published_at` is always null, and the scraper
  ingests every `<h3>` on three index pages including nav and sidebar items. The
  agent has a news tool that can never find news. **Now unblocked** — symbol
  attribution needs company names, which I-07's `company_info` supplies.
- **I-09 · Watchlist end-to-end.** The table exists with its unique constraint;
  there is no ORM model and no router, so every user sees the same top-10 by
  volume. The user-scoping pattern in `routers/portfolio.py` is already correct and
  is what to copy.
- **I-10 · Investment rules CRUD + screen.** `tasks/rules_tasks.py` is 284 lines of
  genuinely good evaluator — five condition types, a 1-hour dedup window, generated
  explanations — with no way for a user to create a rule, so it logs "no rules
  found" and exits. **The cheapest way to make the agentic claim demonstrable.**
- **I-11 · Notifications wiring.** `NotificationsScreen.js` is a hardcoded
  `DUMMY_ALERTS` array about **TSLA, AAPL, MSFT and NVDA in USD**. The real
  endpoint works and is never called. Small, high-visibility; best done right after
  I-10 so there are real rule-triggered notifications to show.
- **I-12 · Push notifications.** Broken at three layers at once, and there are
  **three incompatible device-token conventions** in the codebase. `fcm.py` posts
  to the legacy FCM endpoint Google decommissioned in June 2024;
  `firebase-admin` is already installed and unused.
- **I-13 · Real ranked recommendations.** The `Math.random()` "AI Picks" chip is
  already deleted (I-07). What remains is building the real thing: a ranking
  endpoint returning a score **and its contributing factors**, which is what turns
  it from a black box into evidence for your no-black-box commitment. Depends on
  I-06, I-07, I-08 — two of the three are now done.

### P2 — research integrity and documented requirements

- **I-14 · SSE streaming in chat.** The backend streaming endpoint and the ReAct
  loop are complete and correct, including tool-call delta accumulation.
  `ChatScreen.js` calls the non-streaming endpoint and `react-native-sse` is not
  installed, so the user stares at a blank indicator for 15–30s against a
  documented 3–5s NFR. **Cheapest large perceived-quality win in the plan**, and it
  makes the ReAct loop visible on screen.
- **I-15 · FR-6 multilingual.** Zero matches for `i18n|sinhala|tamil` in the mobile
  source. Also needs font coverage — the bundled fonts almost certainly do not
  render Sinhala or Tamil glyphs, so Noto Sans Sinhala / Noto Sans Tamil via
  `expo-font`.
- **I-16 · Price prediction.** Table, model and agent tool all exist; nothing ever
  writes to the table, so the tool always errors. Either a simple explainable
  baseline over I-06's `daily_close`, or remove the tool and drop the table. Your
  call, and it depends on what your proposal commits to.
- **I-17 · Evaluation instrumentation.** §13 sets nine quantitative targets and
  there is **no instrumentation to produce a single one of them.** This is a
  dissertation problem more than an engineering one — without it Chapter 5 has no
  data.
- **I-18 · Test suite.** Substantially advanced past what the plan assumed: it said
  "not one test", and there are now **289**, plus five live verification scripts.
  What is still missing is the agent tools against a seeded DB, and a mobile
  runner.
- **I-19 · Learning module content.** A static array with Google-CDN stock photos,
  not CSE-specific, one entry on complex derivatives — not beginner material and
  not aligned to the OECD guidelines FR-5 cites. Currently your weakest evidence
  for the financial-literacy objective.

### P3 — hygiene, resilience, documentation

- **I-20 · Agent robustness.** The fallback chain the plan asks for **has been
  built** — `app/services/llm.py`, NVIDIA primary and OpenRouter fallback, verified
  27/27 including deliberate 401/403/404/timeout failover and the correct
  *non*-failover on a 400 or a local `TypeError`. Two defects in
  `app/services/agent/core.py` remain, both confirmed still present today and both
  silent:
  - `core.py:31` — after `max_loops = 5` the loop exits with whatever
    `final_response` holds, which is `""` if the fifth iteration was a tool call.
    The user gets an empty message.
  - `core.py:67` — `if not tool_active: final_response += delta.content`. Once a
    tool call starts, prose the model emits alongside it is dropped for the rest of
    that chunk stream and never reaches the client or the database.
- **I-21 · Dead code and dependencies.** `app/services/ai_agent.py` is **140 lines
  imported nowhere** — the only two references to it anywhere are docstrings in
  `app/models/stock.py` and `app/services/ai_providers.py` describing it as dead.
  `transformers==4.41.1` is a ~2GB install for nothing. Model names are inconsistent
  across three files while you report `ai_model_used` per message and compare
  performance — they need one `config.py` constant. `scratch/` should move out of
  the repo; it contains `nuke_supabase_and_local.py`.
- **I-22 · API hygiene.** `main.py:26-27` — `allow_origins=["*"]` with
  `allow_credentials=True` is a combination browsers reject; harmless for React
  Native, breaks the documented web target. `POST /stocks/scrape` runs a synchronous
  full market and news scrape inside the request, so any logged-in user can hold a
  worker for a minute, repeatedly — it should enqueue and return 202.
- **I-23 · Documentation.** Both `.env.example` files are incomplete, so **a fresh
  clone cannot start** — worth caring about if an external examiner tries.
  `README.md` describes `backend/` as an empty folder with "no backend source files
  committed yet" and documents the wrong auth stack. `project_progress.md` lists as
  "remaining" two things that are long done.

---

## 6. Things to know before touching the code

Collected because each of these cost me time.

- **All routes are under `/api/v1`.** No exceptions.
- **`app/models/stock.py` and `app/models/portfolio.py` use TAB indentation.**
  Everything else uses spaces. Match the file you are in.
- **`pytest.ini` mandates the suite stay offline, deterministic and read-only.**
  Do not add a Postgres-backed test to `tests/`. One-off probes go in `scratch/`,
  which is excluded from collection — that is why it exists.
- **Supabase JWTs are asymmetric ES256, verified via JWKS.** There is no
  `SUPABASE_JWT_SECRET` and none is needed. Do not add one.
- **`exchange_today()` and `EXCHANGE_TZ` live in `app/services/portfolio_history.py`.**
  Anything dated must use them, not UTC and not the machine clock. There is no
  market-is-open helper in `app/` — the application never needs to know; only
  `verify_i05` does, and it has a local one.
- **cse.lk keeps serving the previous session while the market is shut.** A scrape
  on Thursday returns Tuesday's data verbatim. Never date a row from your own
  clock.
- **cse.lk sends null, not zero, for an industry group with no trades.** This
  caused the `/stocks/indices` bug above. Do not infer meaning from a null
  turnover.
- **`ON CONFLICT DO UPDATE` cannot affect the same row twice in one statement — but
  only when the row is actually modified.** If a `WHERE` guard filters the update
  out, Postgres never registers the collision.
- **Windows:** `PYTHONIOENCODING=utf-8` for the scripts, `--pool=solo` for Celery.

---

## 7. If you continue

The next issue in plan order is **I-08 (news pipeline)**, and it is now unblocked
by I-07's company names. It is also the highest-leverage one left: it feeds I-13's
recommendations and it is the only thing that makes the agent's news tool
functional.

If a demo is imminent rather than a deep-dive, **I-11 then I-14** buy the most
visible improvement for the least work — one deletes the most obviously fake
screen in the app, the other makes the ReAct loop stream on screen.

Either way, the first real step is §4.1: register an account, so that user-scoped
work can be verified against a user.
