# InvestAI — Codebase Investigation Report

**Date:** 2026-08-26
**Scope:** `investai-backend/` (FastAPI + Celery) and `investai-mobile/` (React Native / Expo), read in full against the claims in `project_documentation.md` and `project_progress.md`.
**Method:** Direct source reading of every router, service, task, model, migration, screen, navigator and store. No code was modified.

---

## 1. Executive summary

The project is **much further along than the docs say** — `project_documentation.md` §15 claims "30% complete" and lists as "remaining" several things that are in fact built (risk-profiling endpoint, `/stocks` wired to real DB queries, full agent tool layer, SSE endpoint, Celery beat schedule). The structural work is genuinely done: a 6-tool ReAct agent with DB-backed multi-turn memory, a working CSE API scraper, pgvector RAG with keyword fallback, an investment-rules evaluator, and ~7,000 lines of polished React Native UI across 21 screens.

**But the system does not currently work end-to-end, for four specific reasons:**

| # | Break | Effect |
|---|-------|--------|
| 1 | `dependencies.py` never verifies the JWT signature | Total auth bypass; any forged token grants access to any account |
| 2 | Two parallel identity systems (Clerk in the app, Supabase in the backend) that never meet | The entire OTP/register/login/reset backend stack is dead code; user rows are duplicated |
| 3 | `tasks/scrape_tasks.py` imports two functions that don't exist | Every scheduled Celery task dies on import — the "agentic automation" never runs autonomously |
| 4 | Mobile axios instance has no auth interceptor | Risk-profile sync and session restore silently fail, so AI personalisation never activates |

Beyond those, several features that the dissertation presents as delivered are **UI-only or synthetic**: the watchlist, the notifications screen, the ASPI index, portfolio history charts, and all stock fundamentals (P/E, 52-week range, market cap) on the detail screen. These are the highest viva risk, because §12.1 of your own documentation commits to transparency and no "black box" outputs.

**Honest completion estimate:** ~70% of the backend, ~85% of the UI shell, ~40% of the end-to-end feature paths. The remaining work is mostly *wiring and de-mocking*, not new architecture — which is good news. Section 7 lists it in priority order.

---

## 2. What the system actually is (as built)

```
┌─────────────────────────── investai-mobile (Expo SDK 54, RN 0.81) ──────────┐
│  Auth:  Clerk (@clerk/clerk-expo)          ← NOT Supabase, despite the docs │
│  State: Zustand (authStore) + AsyncStorage                                  │
│  Nav:   Clerk isSignedIn → SignedInStack (Assessment gate → Tabs)           │
│  21 screens; each attaches Clerk getToken() to axios calls MANUALLY          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  Bearer <Clerk JWT>  (signature unchecked)
┌──────────────────────────────────▼──────── investai-backend (FastAPI 0.111) ┐
│  /api/v1/auth          Supabase + Brevo OTP  ← DEAD: app never calls it     │
│  /api/v1/me            risk-profile scoring        (works, but never reached)│
│  /api/v1/stocks        market / news / sentiment / manual scrape   (works)   │
│  /api/v1/portfolio     portfolio + holdings CRUD                   (works)   │
│  /api/v1/chat          /message  (used) · /stream SSE  (built, unused)       │
│  /api/v1/dashboard     LLM-generated insights + portfolio value    (works)   │
│  /api/v1/notifications list + test  (works, but the app never calls it)      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
        Agent (ReAct, OpenRouter          Celery + Redis + Beat
        google/gemini-2.5-flash)          ├ scrape_cse_data      ✗ ImportError
        6 tools · DB memory · RAG         ├ scrape_and_analyse_news ✗ ImportError
                                          └ check_investment_rules  ✓ (no data)
                     │                           │
                     └─────────────┬─────────────┘
                                   ▼
                 Supabase PostgreSQL + pgvector (5 migrations, single head ✓)
```

### Documented vs. actual architecture

| Layer | `project_documentation.md` §9 says | Code actually does |
|---|---|---|
| Mobile auth | Supabase Auth, JWT in AsyncStorage | **Clerk** (`App.js:69`, `LoginScreen.js:46`, `RegisterScreen.js:45`) |
| Backend auth | Verify Supabase-signed JWT | **Nothing verified** (`dependencies.py:28`) |
| Chat transport | EventSource / SSE streaming | Plain POST `/chat/message` (`ChatScreen.js:61`) |
| Primary LLM | Gemini Flash 1.5 / GPT-4o | `google/gemini-2.5-flash` (`agent/core.py:21`), 1.5 elsewhere |
| Push | Firebase FCM | Legacy FCM HTTP API — **retired by Google in 2024** (`fcm.py:16`) |
| Languages | Tamil / Sinhala / English | **English only**; no i18n library, zero translation files |
| Payments | Payhere premium tier | **Not present anywhere** in the codebase |

---

## 3. Critical findings

### C-1 · Complete authentication bypass
`investai-backend/app/dependencies.py:28`

```python
payload = jwt.get_unverified_claims(token)
clerk_sub = payload.get("sub", "unknown")
```

The token's signature is never checked, and there is no JWKS fetch, no `jwt.decode`, and no Clerk SDK on the backend. `CLERK_SECRET_KEY` is declared at `config.py:19` and never read.

Anyone can hand-craft a JWT with an arbitrary `sub` and read or write **any** user's portfolio, chat history and risk profile. Worse, lines 36–46 *auto-create* a user row for any unrecognised `sub`, so a forged token also silently provisions accounts. Because `get_unverified_claims` succeeds on almost any base64 blob, this is not a subtle hole.

This is the item your own roadmap still lists as open ("Fix `dependencies.py` JWT verification") — it is still open, and the switch to Clerk made it wider. **Fix this first**: it invalidates NFR-Security, §12.2 of the ethics chapter, and any claim about protecting user data.

### C-2 · Split-brain identity — the whole auth backend is dead code
The app authenticates with Clerk. The backend's `/auth/*` router (`routers/auth.py`, 268 lines) implements a complete Supabase + Brevo OTP flow: register, 6-digit OTP verify, resend, login, 3-step password reset. **The mobile app calls none of it** for sign-in — `LoginScreen`/`RegisterScreen` use Clerk's `useSignIn`/`useSignUp` hooks directly.

The two systems produce incompatible user rows:

- `routers/auth.py:85` writes `users` keyed by the **Supabase UUID** with the user's **real email**.
- `dependencies.py:32` looks users up by the synthetic address `f"{clerk_sub}@clerk.local"` and creates a second row if absent.

So a person who registers through the API and then signs in through the app is two different users to the database. Everything that hangs off `user_id` — portfolios, chat sessions, risk profile, notifications — is partitioned across the two.

Collateral: `services/otp.py`, `services/email_service.py`, `models/otp.py`, `utils/security.py`, the `otp_codes` migration, `schemas/auth.py`, and the Supabase auth trigger migration are all unreachable in the current app flow. That is a substantial amount of working code you are not getting credit for.

**Decision needed** (see §6): pick one identity provider. Keeping both is not viable.

### C-3 · Every scheduled Celery task crashes on import
`investai-backend/tasks/scrape_tasks.py:40` and `:87`

```python
from app.services.scraper import scrape_cse_data, validate_market_record   # :40
from app.services.scraper import scrape_news, validate_news_record         # :87
```

Neither `validate_market_record` nor `validate_news_record` exists — `grep "def validate" app/services/scraper.py` returns nothing. Both `scrape_cse_data` and `scrape_and_analyse_news` therefore raise `ImportError` on every Beat tick, retry three times, and die.

Consequence: **no autonomous data collection happens at all.** No market data, no news, no sentiment, no embeddings. Which in turn means:

- FR-10 (agentic workflow automation) is unmet.
- **Research Objective 2** — "evaluate the effectiveness of agentic workflows combined with real-time web scraping" — has no running system to evaluate.
- Evaluation metric "Data Freshness < 15 minutes" (§13) cannot be measured.

The synchronous escape hatch `POST /stocks/scrape` **does** work, because it calls `scrape_and_save_cse` / `scrape_and_save_news`, which do exist (`scraper.py:45`, `:111`). So your data today is whatever you scraped by hand. Note the two paths also duplicate logic — the task versions re-implement insert + dedup rather than calling the service functions.

### C-4 · Mobile axios sends no credentials
`investai-mobile/src/api/axiosConfig.js:11` — `// Auth logic removed`

The shared axios instance has a response interceptor but **no request interceptor**, so no `Authorization` header. Every screen works around this by calling `getToken()` and building headers inline — except the two calls that go through `authApi`:

- `authStore.js:46` → `authApi.getMe()` → `GET /auth/me` → **403**. `restoreSession()` always lands in its catch block (`authStore.js:56`), wipes the stored token, and leaves `user: null`. Masked because Clerk handles the actual gating — but it's why `HomeScreen.js:40` falls back to the hardcoded name `'Sanjeev'` / `'PERERA'`.
- `authStore.js:81` → `authApi.updateRiskProfile()` → `POST /me/risk-profile` → **403**, caught and logged as a warning at `authStore.js:83`.

That second one has real consequences. The risk score is never persisted, so `risk_profiles` stays empty, so `memory._risk_context()` (`agent/memory.py:51`) always returns `None`, so the risk-profile system message is never injected into the LLM context. **The AI's risk-based personalisation — feature 6.10, and a core part of Objective 1 — never activates.** The 10-question quiz UI runs, stores to AsyncStorage, and the result goes nowhere.

Also note `ResetPasswordScreen.js:96` calls `authApi.resetPassword('mock-token', password)` with a literal placeholder and the wrong arity (the function takes `email, reset_token, new_password`).

---

## 4. High-severity findings

### H-1 · Push notifications cannot work — three independent breaks
1. **Retired API.** `services/fcm.py:16` posts to `https://fcm.googleapis.com/fcm/send` with `Authorization: key=<server key>`. Google decommissioned the legacy FCM HTTP API in June 2024; this endpoint now returns 404. `firebase-admin==6.5.0` is already in `requirements.txt` and unused — that's the correct path (HTTP v1 + service-account OAuth).
2. **Token unreadable.** Migration `a1b2c3d4e5f6:45` adds `user_profiles.device_token`, but the `UserProfile` SQLAlchemy model (`models/user.py:29`) has no such column. So `fcm.py:83`'s `getattr(profile, "device_token", None)` returns `None` for every user, forever. Same for the `language` column added at `:51`.
3. **Token never captured.** There is no endpoint to register a device token, and the mobile app never requests one (`expo-notifications` and `@react-native-firebase/messaging` are installed but unused).

Net effect: FR-8's push path is non-functional at three layers.

### H-2 · `notification_service` references a non-existent column
`services/notification_service.py:30` reads `user.fcm_token`. The `User` model has no `fcm_token` field, so any call with `send_push_alert=True` raises `AttributeError` and rolls back (`:44`). Currently masked only because `routers/notifications.py:36` hardcodes `send_push_alert=False`. Note this is a *third* device-token convention, alongside `user_profiles.device_token` (migration) and `send_push_to_user` (fcm.py).

### H-3 · Password-reset tokens in a process-local dict
`utils/security.py:31` — `_reset_tokens: dict = {}`

Reset tokens live in module memory: lost on every restart or deploy, invisible to sibling workers (any multi-worker uvicorn or Railway replica breaks resets ~50% of the time), never expire, and grow unbounded. The comment acknowledges it ("use Redis in production"). Redis is already a dependency for Celery. Lower urgency only because this path is currently dead (C-2).

### H-4 · Registration creates a usable Supabase account before OTP verification
`routers/auth.py:47` calls `admin.create_user({... 'email_confirm': True ...})` with the real password *before* any OTP is checked. The OTP gate is enforced only by the local `is_email_verified` flag at `:167`. Anyone who authenticates against Supabase directly — the anon key is public by design and shipped in the client — bypasses email verification entirely. Again, dead path today, but it must not survive into whichever auth model you keep.

---

## 5. Medium-severity findings

### M-1 · Features that exist as UI only

| Feature | Documented as | Reality |
|---|---|---|
| **Watchlist** (6.7 / FR-7) | Per-user add/remove, secure storage | `watchlist` table created by migration `a1b2c3d4e5f6:57`, but **no ORM model, no router, no endpoint**. `WatchlistScreen.js:78` fetches `/stocks/market?limit=50` and shows the top 10 **by volume** — identical for every user. `dashboard.py:64` does the same for `watchlist_preview`. |
| **Notifications** (6.8 / FR-8) | Rule alerts with AI explanations | `NotificationsScreen.js:32` is a hardcoded `DUMMY_ALERTS` array — and it's about **TSLA, AAPL, MSFT, NVDA in USD**, not CSE stocks. `GET /notifications/` works and is never called. |
| **Investment rules** (6.12) | User defines rules; agent monitors | `InvestmentRule` model and a well-written evaluator (`rules_tasks.py`, 284 lines, 5 condition types, 1-hour dedup, AI explanation with fallback) both exist — but there is **no create/list/delete endpoint and no screen**. The table is always empty, so the task logs "No investment rules found" and exits. |
| **Multilingual** (6.6 / FR-6) | Tamil / Sinhala / English, hot-switchable | **Nothing.** No i18n library in `package.json`, no translation files, zero matches for `i18n|sinhala|tamil` across `investai-mobile/src`. Only the system prompt (`agent/memory.py:40`) asks the LLM to mirror the user's language. |
| **Payhere premium** (§9, §15) | LKR subscription payments | **Zero occurrences** of `payhere` or `payment` in the backend. |
| **Learning module** (6.5 / FR-5) | OECD-aligned beginner content | `LearnScreen.js:24` is a static `ARTICLES` array with Google-CDN stock photos. Content is generic and not CSE-specific; one entry is "Complex Derivatives: Hedging against market volatility" — not beginner material, and not aligned to OECD literacy guidelines. |

### M-2 · Synthetic data presented as real market data — highest viva risk
Your ethics chapter (§12.1) commits to no "black box" outputs and full transparency about how figures are produced. These violate it:

- `routers/dashboard.py:95` — **ASPI index hardcoded** to `12450.80` / `+1.2%`. The code comment admits it: `# ASPI is an index, hardcoded for now`. It is rendered on the home screen as live market data.
- `routers/dashboard.py:86` — portfolio `weekly_history` is `current_val × [0.85, 0.82, 0.94, 1.0]`. A fabricated 4-point history drawn as a performance chart.
- `StockDetailScreen.js:24` — `generateMockChartData()` builds the intraday price chart from `Math.random()`, labelled with real times ("9AM … Now").
- `StockDetailScreen.js:57-60` — **P/E ratio, 52-week high, 52-week low and market cap derived arithmetically from the price**: `peRatio = 8 + (price % 15)`, `high52 = price × (1 + (price % 30)/100)`. These are displayed as company fundamentals. FR-4 says the AI "must interpret basic financial indicators" — the indicators themselves are invented.
- `HomeScreen.js:136` — the **"AI Picks"** filter is `sort(() => 0.5 - Math.random())`.
- `HomeScreen.js:40` — display name falls back to hardcoded `'Sanjeev'` / `'PERERA'`.
- Sector filters (`HomeScreen.js:127`, `StockBrowseScreen.js:71`) are hardcoded ticker-prefix lists, because `market_data` has no sector column.

Recommendation: either compute these for real, or label them in the UI ("illustrative", "sample data"). An examiner who taps into Stock Detail and sees a P/E derived from `price % 15` will question every other number in the demo. Labelling costs you almost nothing; being caught costs a lot.

### M-3 · SSE streaming built but unused
`routers/chat.py:173` (`POST /chat/stream`) and `agent/core.py:23` (`stream_agent`) are complete and correct — including tool-call delta accumulation, `tool_start`/`tool_result`/`token`/`done` events, and `X-Accel-Buffering: no`. But `ChatScreen.js:61` calls the non-streaming `/chat/message`, and `react-native-sse` is not in `package.json`.

§14 names SSE as a *key design decision* ("mobile client sees tokens appear in real time, not a blank screen for 5 seconds"). Right now the user waits on a blank typing indicator for the full round-trip — with `timeout: 60000` (`axiosConfig.js:7`) and a 5-iteration tool loop, that can be 15–30s. This also directly harms your NFR "3–5 second" performance target and metric §13 "Response Time".

### M-4 · News pipeline: sentiment works, summarisation and symbol attribution don't
- `services/sentiment.py:50` `summarise_article()` — the LLM summariser — is **defined and called from nowhere**. Verified: it has exactly one occurrence in the codebase, its own definition. So FR-3's "AI must summarise each article into short, easy-to-understand insights" is not happening.
- What populates `summary` instead: `scraper.py:171` takes `h3.find_next('p')` — literally whatever paragraph follows the headline in the HTML. That raw fragment is what the sentiment scorer reads (`scrape_tasks.py:149`) and what the agent's `get_stock_news` tool returns to the LLM.
- `scraper.py:127` sets `published_at=None` unconditionally, so news has no date. §13's "Data Freshness" metric is unmeasurable for news.
- **Symbol attribution:** `scraper.py:105`/`:124` assigns `'GENERAL'` to every article unless a symbol was passed in. So `GET /stocks/news/{symbol}` and the agent's `get_stock_news("HNB")` return **empty for every real ticker**. The agent has a news tool that can never find news.
- `scraper.py:161` selects **all `<h3>` elements** on three index pages. Nav items, sidebars and "related stories" are ingested as articles. No CSS-selector-per-source, no article-page fetch.

The RAG path is the same story: `search_financial_knowledge` (`agent/tools.py:338`) is well built with a keyword fallback, but it searches `news_sentiment.embedding`, which is only populated by `embed_news_articles` — reachable only through the crashing task chain (C-3).

### M-5 · `market_data` grows without bound, and "latest" is recomputed per request
`scraper.py:50` inserts a **new row per symbol per scrape** with no unique constraint and no upsert. At ~300 CSE symbols every 15 minutes over a 5-hour session that's ~6,000 rows/day, ~1.5M over a year, with no retention policy. Meanwhile `stocks.py:24` derives "latest per symbol" with a `GROUP BY max(recorded_at)` subquery **on every single request**, and `dashboard.py:79` runs an `ORDER BY recorded_at DESC LIMIT 1` query **per holding** in a loop (N+1).

Directly threatens NFR-Scalability and NFR-Performance. Cheapest fixes: a `(symbol, recorded_at)` composite index now, and a `latest_market_data` materialised view or a `market_data_latest` upsert table later.

### M-6 · Dead code and duplicated agent implementations
- `app/services/ai_agent.py` (119 lines) — **imported nowhere**. Verified by grep. It's the pre-refactor agent, superseded by `app/services/agent/`.
- `app/services/ai_providers.py` — 5 provider classes; only `OpenRouterProvider` is used, by `dashboard.py:24`. The Anthropic, Google, Groq and OpenAI classes are unreachable, but `requirements.txt` still carries `anthropic`, `google-generativeai`, `groq`, `openai` **and `transformers==4.41.1`** (~2 GB of install for nothing).
- The provider fallback chain the docs imply (`PROVIDERS = [...]` at `ai_agent.py:20`) is never exercised, so NFR-Reliability's "fallback data sources if primary source is unavailable" is unimplemented for the LLM: `agent/core.py` calls OpenRouter with a 15s timeout and no fallback. If OpenRouter is down or rate-limited during your demo, chat returns a 500.
- 13 one-off scripts in `investai-backend/scratch/` including `nuke_supabase_and_local.py` and `clear_users.py`. Move out of the repo or into a documented `scripts/` folder before submission — a destructive script sitting next to source is a bad look, and `scratch/` implies the auth work was debugged by hand rather than tested.

### M-7 · Model-name drift
`agent/core.py:21` uses `google/gemini-2.5-flash`; `rules_tasks.py:215` and `sentiment.py:78` use `google/gemini-flash-1.5`; `dashboard.py` (via `ai_providers.py:132`) uses `google/gemini-2.5-flash`. The docs say "Gemini Flash 1.5 / GPT-4o". For a dissertation that reports `ai_model_used` per message and compares performance, this needs to be one constant in `config.py`, cited consistently.

### M-8 · `.env.example` files are incomplete — a fresh clone cannot start
- **Backend** `.env.example` omits: `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `CLERK_SECRET_KEY`, `BREVO_API_KEY`, `BREVO_FROM_EMAIL`, `BREVO_FROM_NAME`, `FRONTEND_URL`, `FIREBASE_CREDENTIALS_PATH`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` — all read by `config.py`. Without the first two, chat and RAG fail silently at runtime.
- **Mobile** `.env.example` has only `EXPO_PUBLIC_API_BASE_URL` and an obsolete `EXPO_PUBLIC_FIREBASE_API_KEY`. It is **missing `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY`**, which `App.js:30` requires — so a fresh clone crashes at `ClerkProvider`. Your external examiner may well try this.

### M-9 · No automated tests
`pytest` and `pytest-asyncio` are in `requirements.txt`; there is not one test. The four `test_*.py` files are ad-hoc manual scripts (`scratch/test_email_api.py`, `test_supa_auth.py`, …) that hit live services. Nothing exercises the agent tool layer, the rule evaluators, or the risk-score calculation — all of which are pure functions and trivially testable.

This is also a **dissertation problem, not just an engineering one**: §13 sets nine quantitative targets (recommendation accuracy > 80%, response time < 3–5s, notification accuracy > 95%, uptime > 99%). There is no instrumentation to produce a single one of those numbers. You need at minimum request-latency logging on `/chat/*` and a small evaluation harness over a fixed question set before you can write Chapter 5.

### M-10 · Smaller items
- **CORS** `main.py:26-27`: `allow_origins=["*"]` together with `allow_credentials=True` is an invalid combination — browsers reject credentialed wildcard requests. Harmless for React Native, breaks the documented web target (NFR-Portability).
- **Unauthenticated-cost endpoint** `stocks.py:57`: `POST /stocks/scrape` runs a *synchronous* full market + news scrape with a 60s timeout inside the request. Any logged-in user can hold a worker for a minute, repeatedly. Should enqueue a Celery task and return 202.
- **Agent turn cap silently truncates** `agent/core.py:36`: after `max_loops = 5`, the loop exits with whatever `final_response` holds — which is `""` if the 5th iteration was a tool call. The user gets an empty message with no explanation.
- **Streaming loses pre-tool prose** `agent/core.py:75`: once `tool_active` is set, `delta.content` is dropped for the rest of that chunk stream, so any text the model emits alongside a tool call never reaches the client or the DB.
- **Migration docstring drift** `a1b2c3d4e5f6:4`: says `Revises: 9c7bb6e6ce19`, actual `down_revision` is `8a75110865d7`. Cosmetic — I verified the chain is linear with a single head: `c7df033a746c → 79fcf139c76e → 9c7bb6e6ce19 → 8a75110865d7 → a1b2c3d4e5f6`. `alembic upgrade head` is safe.
- **`price_predictions` never written.** The table, model and `get_price_prediction` tool (`agent/tools.py:304`) all exist; nothing populates it. The tool always returns `{"error": "No prediction available"}`. Either build the predictor or drop the tool from `TOOL_SCHEMAS` — an agent tool that always errors wastes context and confuses the model.
- **`docs_url=None` + manual Swagger** (`main.py:21`, `:42`) is deliberate — a CDN patch so the docs render where bundled assets are blocked. Keep, and note it in the README so it doesn't read as a mistake.
- **`README.md` is badly stale.** It describes `backend/` as an empty folder with "no backend source files or run scripts committed yet", tells the reader to configure a Firebase API key, and documents Supabase/Zustand auth. All wrong. This is the first file an examiner opens.
- **`project_progress.md` is stale in the other direction** — it lists as "remaining" the risk-profiling endpoint (`user.py:24`, done) and "wire `/stocks` to real DB queries" (`stocks.py:14`, done).

---

## 6. The one decision you must make now

Everything in §7 depends on this, so resolve it before writing more code.

**Which identity provider?** You cannot ship both.

- **Keep Clerk** (what the app actually uses). Then: install a Clerk backend verifier, verify the JWT against Clerk's JWKS in `dependencies.py`, key `users` by Clerk `sub` (add a `clerk_user_id` column — stop synthesising `@clerk.local` emails), and **delete** `routers/auth.py`, `services/otp.py`, `services/email_service.py`, `models/otp.py`, `utils/security.py`. Fastest path to working; costs you the OTP/Brevo work in the dissertation, and Clerk contradicts §9's documented stack.
- **Keep Supabase** (what the docs describe, and what most of the backend implements). Then: verify the Supabase JWT with `SUPABASE_JWT_SECRET` (HS256) in `dependencies.py`, rip Clerk out of `App.js`/`AppNavigator.js`/`LoginScreen.js`/`RegisterScreen.js`, and point them at the existing `/auth/*` endpoints via `authApi` — which is already written and complete. More mobile churn, but it makes your existing OTP + Brevo + reset implementation *count*, keeps the documented architecture honest, and means one less third-party dependency to explain.

My recommendation: **Supabase.** The backend work is already done and tested-by-hand, `authApi.js` already wraps every endpoint, and it aligns the code with the dissertation you have to defend. The mobile change is roughly four screens plus the navigator gate — smaller than it looks, and `AuthNavigator`/`OTPVerifyScreen`/`ForgotPasswordScreen`/`ResetPasswordScreen` already exist for exactly this flow. You'd also drop `@clerk/clerk-expo` and get the `getToken()` boilerplate out of all nine screens by restoring the axios request interceptor.

---

## 7. Prioritised remaining work

### P0 — Blocks a safe, working demo
1. **Verify JWTs** in `dependencies.py` (C-1). Whichever provider §6 picks. Reject on failure; stop auto-creating users from unverified claims.
2. **Unify identity** (C-2). Execute the §6 decision and delete the losing path.
3. **Fix the Celery import crash** (C-3). Either add `validate_market_record` / `validate_news_record` to `scraper.py` or have the tasks call the existing `scrape_and_save_cse` / `scrape_and_save_news`. Then confirm Beat actually fires — `celery -A celery_worker worker` + `beat`, and watch for row counts.
4. **Restore the axios request interceptor** (C-4) so risk-profile sync and `/auth/me` work — and drop the per-screen `getToken()` duplication.

### P1 — Needed for the documented feature set
5. **Watchlist**: `Watchlist` ORM model + `GET/POST/DELETE /watchlist` + wire `WatchlistScreen` and `dashboard.watchlist_preview` to it. The table already exists.
6. **Investment rules CRUD**: `GET/POST/PUT/DELETE /rules` + a screen. `rules_tasks.py` is already written and waiting for data — this is the cheapest way to make "agentic automation" demonstrable.
7. **Wire `NotificationsScreen` to `GET /notifications/`**; delete `DUMMY_ALERTS`. Add `PATCH /notifications/{id}/read`.
8. **Fix FCM**: switch to `firebase-admin` HTTP v1, add `device_token` + `language` to the `UserProfile` model, add `POST /me/device-token`, register the token from the app, and fix `notification_service.py:30`'s phantom `user.fcm_token`.
9. **Label or fix all synthetic data** (M-2). Cheapest credible route: scrape ASPI / S&P SL 20 from the CSE `marketStatus`/index endpoints for the index tiles; snapshot real daily closes into a small table for the charts; and for the Stock Detail fundamentals either scrape them or replace the tiles with data you do have (volume, change, sentiment). Anything you can't source, label "sample".

### P2 — Research-objective and dissertation integrity
10. **Symbol attribution for news** (M-4). Without it, the agent's news tool and all per-stock sentiment return nothing. Match CSE ticker symbols and company names against headline + body at ingest.
11. **Call `summarise_article()`** in the sentiment task, so FR-3's AI summarisation actually runs.
12. **Multilingual support** (FR-6). `i18n-js` or `react-i18next` + Sinhala/Tamil strings for at least the primary screens, plus a language toggle that also sets the LLM output language. The `user_profiles.language` column is already migrated.
13. **Switch chat to SSE** (M-3). Add `react-native-sse`, point `ChatScreen` at `/chat/stream`, and render the `tool_start` / `tool_result` events — which also *demonstrates* the ReAct loop visually. Strong viva material, and it's the difference between a 20-second blank wait and a live-looking agent.
14. **Instrumentation for §13** (M-9): per-request latency logging on `/chat/*`, a fixed question set with expert-rated answers for the accuracy figure, and a rule-alert audit log for notification accuracy. Without this Chapter 5 has no data.
15. **Tests** for the pure logic that carries your claims: risk-score calculation (`user.py:33-83`), the five rule evaluators (`rules_tasks.py:31`), sentiment labelling thresholds, and each agent tool against a seeded DB.

### P3 — Cleanup and scope calls
16. Delete `app/services/ai_agent.py`; either implement the multi-provider fallback in `agent/core.py` (good for NFR-Reliability, and defensible in the viva) or delete the unused providers and drop `anthropic`/`google-generativeai`/`groq`/`transformers` from `requirements.txt`.
17. Complete both `.env.example` files (M-8), especially `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` or its Supabase replacement.
18. Rewrite `README.md` to match reality; regenerate `project_progress.md`.
19. Add the composite index on `market_data(symbol, recorded_at DESC)`; fix the N+1 in `dashboard.py:79`; make `POST /stocks/scrape` enqueue rather than block.
20. Move `scratch/` out of the repo (especially `nuke_supabase_and_local.py`).
21. Consolidate the model name into `config.py` (M-7); drop the `get_price_prediction` tool unless you build the predictor.
22. **Payhere / premium tier** — currently zero lines. If it stays out of scope, say so explicitly in the dissertation and remove it from §9 and §15 rather than leaving it as an unmet promise. The `role` column already supports `premium`, so a stub is cheap if you want to keep the claim.
23. Replace `LearnScreen`'s generic articles with CSE-specific, OECD-aligned beginner content (M-1). Right now it's the weakest evidence for Objective 1's "financial literacy" claim.

---

## 8. What is genuinely good

Worth saying, because the finding list above is long and the underlying engineering is not bad:

- **`agent/tools.py`** (459 lines) — six well-specified tools with clear LLM-facing descriptions, real P&L computation, a pgvector→keyword graceful fallback, per-tool exception isolation, and a disclaimer baked into the prediction tool. This is the strongest file in the project and the best evidence for Objective 2.
- **`agent/memory.py`** — a clean rolling-window context builder with DB persistence and risk-profile injection. The `SYSTEM_PROMPT` is genuinely well written for the beginner-investor use case and encodes your ethics chapter (no guarantees, always disclaim, refuse trade execution, mirror the user's language).
- **`agent/core.py`** — correct OpenAI-style streaming tool-call delta accumulation across chunks. This is fiddly and easy to get wrong.
- **`rules_tasks.py`** — table-driven condition evaluators, a 1-hour dedup window matching the spec, AI explanation with a template fallback, and separate retry policies per task. Ready to work the moment it has rules to evaluate.
- **CSE scraper** — uses the real `cse.lk/api/tradeSummary` JSON endpoint with correct `Origin`/`Referer` headers rather than brittle HTML parsing, and checks market status to distinguish "closed" from "broken".
- **Mobile UI** — 21 screens, a consistent token-based theme (`theme/tokens.js`), custom fonts, reusable components, and real animation work (`PanResponder` swipe stack for AI insights, `Animated` chart reveals). Presents very well in a demo.
- **Alembic chain** — linear, single head, `IF NOT EXISTS` guards, working `downgrade()`. `upgrade head` is safe to run.
- **Graceful degradation throughout the app** — every screen has a fallback so the UI never breaks on a failed request. Good defensive practice; just make sure the fallbacks are *labelled* (M-2), because right now they're indistinguishable from live data.

---

## 9. Suggested viva framing

You will be asked "is this working?" Three honest, defensible positions:

1. **Lead with the agent.** The ReAct loop, tool layer and DB-backed memory are real, novel for the CSE context, and directly answer Objective 2. Demo chat with visible tool indicators (P2 #13) and it speaks for itself.
2. **Be upfront about the auth migration.** "We prototyped with Supabase Auth, trialled Clerk for faster social sign-in, and consolidated on X" is a normal engineering narrative. Being *caught* with two half-wired systems and an unverified JWT is not. Fix C-1/C-2 and the story becomes a strength.
3. **Never present synthetic data as live.** Label it, or compute it. One examiner tap into Stock Detail is all it takes, and the credibility loss extends to every real number in the system.

---

*Report produced by direct source inspection on 2026-08-26. No files were modified. Every claim above cites `file:line` — spot-check any of them.*
