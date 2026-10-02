# InvestAI backend: API and contract test report

**Date:** 2026-10-02 · **Branch:** `fix/app-polish` (worktree `project-overview-1619bb`, uncommitted)
**Suite:** `investai-backend/tests/qa/test_api_contract.py`
**Command:** `cd investai-backend && python -m pytest tests/qa/test_api_contract.py -q`
**Result:** **183 tests: 174 passed, 9 xfailed (strict), 0 failed.** Runtime is about 10 s.

## How the tests run

- The tests drive the real `app.main.app` through `fastapi.testclient.TestClient`.
- The database is in-memory SQLite (`StaticPool`) built from `Base.metadata`. JSONB is compiled to SQLite `JSON`. `get_db` is overridden, and so is `SessionLocal`, which the chat stream and `/health` use.
- `get_current_user` is overridden for the happy-path and isolation tests. It returns a seeded `users` row, and `as_user()` switches between user A and user B.
- The auth tests do **not** override `get_current_user`. They use real `verify_supabase_token` with HS256 tokens signed by a throwaway test secret. JWKS is stubbed to "no keys".
- Everything runs offline:
  - `DATABASE_URL` and `SUPABASE_URL` are pointed at `127.0.0.1:1` before the app is imported.
  - An autouse fixture blocks every non-loopback `socket.connect`.
  - Patched out: the dashboard LLM insight refresh, FCM push dispatch, Celery `.delay`, and `stream_agent`/`run_agent`.
  - No real DB, network, LLM, Supabase or production server is touched.
  - No accounts are created and the real `SECRET_KEY` is not used.
- The whole backend suite with this module included gives 603 passed and 9 xfailed. I excluded the known brotli env failure and a sibling `tests/qa/test_security.py` that was being written concurrently by another agent. Without `tests/qa`, the suite still shows its usual result: 420 passed and the 1 known brotli failure. So this module does not break the existing tests.
- One caveat: the module sets env vars at import time. In a single pytest process, any test module collected after it sees the fake `DATABASE_URL`/`SUPABASE_URL`, which errs on the safe side.

## Route inventory (55 routes, prefix `/api/v1` unless noted)

Auth = depends on `get_current_user` (Supabase JWT bearer). This is verified by walking each route's dependency tree.

| Method | Path | Auth | Request schema | Response model / status |
|---|---|---|---|---|
| POST | /auth/register | no (rate-limit 10/min) | RegisterRequest | untyped, 201 |
| POST | /auth/verify-otp | no | OTPVerifyRequest | untyped |
| POST | /auth/resend-otp | no | ForgotPasswordRequest | untyped |
| POST | /auth/login | no | LoginRequest | TokenResponse |
| POST | /auth/refresh | no | RefreshRequest | TokenResponse |
| POST | /auth/forgot-password | no | ForgotPasswordRequest | untyped |
| POST | /auth/verify-reset-otp | no | VerifyResetOTPRequest | untyped |
| POST | /auth/reset-password | no | ResetPasswordRequest | untyped |
| GET | /auth/me | yes | – | UserOut |
| POST | /auth/logout | optional bearer | – | untyped |
| GET | /stocks/market | yes | query symbol, sector, limit 1–500 | List[MarketData] |
| GET | /stocks/sectors | yes | – | List[SectorSummary] |
| GET | /stocks/company/{symbol} | yes | – | CompanyInfo |
| GET | /stocks/indices | yes | query index_code | List[MarketIndex] |
| GET | /stocks/history/{symbol} | yes | query range (1W…ALL) | PriceHistory |
| GET | /stocks/news/{symbol} | yes | query limit 1–100 | List[NewsSentiment] |
| POST | /stocks/scrape | yes (404 in prod) | query symbol | ScrapeResponse, 202 |
| GET | /stocks/sentiment/{symbol} | yes | – | SentimentSummary |
| GET | /portfolio/ | yes | – | List[PortfolioOut] |
| POST | /portfolio/ | yes | PortfolioCreate | PortfolioOut, 201 |
| GET | /portfolio/{portfolio_id}/history | yes | query range | PortfolioHistory |
| POST | /portfolio/{portfolio_id}/holdings | yes | HoldingCreate | HoldingOut, 201 |
| DELETE | /portfolio/{portfolio_id}/holdings/{holding_id} | yes | – | 204 |
| GET | /chat/sessions | yes | query active_only | List[SessionOut] |
| POST | /chat/sessions | yes | – | SessionOut, 201 |
| DELETE | /chat/sessions/{session_id} | yes | – | 204 |
| GET | /chat/sessions/{session_id}/messages | yes | query limit ≤200 | List[MessageOut] |
| POST | /chat/stream | yes (10/min) | SendMessageRequest | SSE `text/event-stream` |
| POST | /chat/message | yes (10/min) | SendMessageRequest | SendMessageResponse |
| GET | /notifications/ | yes | – | List[NotificationOut] |
| PATCH | /notifications/{notif_id}/read | yes | – | NotificationOut |
| POST | /notifications/read-all | yes | – | untyped `{marked_read}` |
| DELETE | /notifications/{notif_id} | yes | – | 204 |
| POST | /notifications/test | yes (404 in prod) | – | untyped (ORM row) |
| GET | /dashboard/ | yes | – | untyped `Dict[str, Any]` |
| PATCH | /me | yes | UpdateProfileRequest | UserOut |
| GET | /me/assessment/questions | **no** | – | list[QuestionOut] |
| POST | /me/risk-profile | yes | AssessmentRequest | RiskProfileResponse |
| GET | /me/plan | yes | – | PlanOut |
| DELETE | /me | yes (3/min) | – | 204 |
| POST | /me/device-token | yes | DeviceTokenRequest | UserOut |
| DELETE | /me/device-token | yes | – | 204 |
| POST | /me/language | yes | LanguageRequest | UserOut |
| GET | /watchlist | yes | – | list[WatchlistItem] |
| POST | /watchlist | yes | WatchlistAdd | WatchlistItem, 201 |
| DELETE | /watchlist/{symbol} | yes | – | 204 |
| GET | /rules | yes | – | list[RuleOut] |
| POST | /rules | yes | RuleCreate | RuleOut, 201 |
| PATCH | /rules/{rule_id} | yes | RuleUpdate | RuleOut |
| DELETE | /rules/{rule_id} | yes | – | 204 |
| GET | /recommendations | yes | query limit 1–50 | untyped `dict` |
| GET | /learn/lessons | yes | – | untyped |
| GET | /learn/lessons/{lesson_id} | yes | – | untyped |
| GET | /health (no prefix) | no | – | untyped, 503 if DB down |
| GET | /docs, /redoc (no prefix, dev only) | no | – | HTML |

That makes 43 protected method+path pairs and 12 public ones. A test pins the public set to an explicit allow-list, so a route that accidentally loses auth will fail CI.

## What was tested

| Area | Tests | Notes |
|---|---|---|
| Auth boundary sweep | 86 | All 43 protected routes give **401 + `WWW-Authenticate: Bearer`** with no token and also with a malformed token. 401 comes before 422 even with an invalid body. |
| JWT verification | 12 | A valid test-signed token reaches the handler. These are rejected with 401: expired, wrong secret, wrong `aud`, wrong `iss`, non-UUID `sub`, unprovisioned user, `alg:none`, RS256 with unknown `kid`, blank bearer, missing `exp`. |
| Validation: 422 not 500 | 50 | Covers wrong types, missing fields, out-of-range values and unknown enums across portfolio, holdings, watchlist, rules, chat, `/me`, notifications, stocks, recommendations and the public `/auth/*` bodies. Also: a whitespace chat message gives 400. |
| Happy paths + contracts | 20 | Risk profile then plan, portfolio CRUD and history, watchlist (idempotent add/remove), rules CRUD, recommendations, learn list/detail (and LessonView recorded), every stocks endpoint (sector filter, index order ASPI→SPSL20→groups, scrape enqueues 3 tasks), dashboard, notifications, device token handover between users, language, profile name, chat sessions/stream/message, rate limits (auth 10/min, chat 10/min to 429), prod-only 404s, `/health`. Each typed body is validated against its declared `response_model` **with no extra or missing keys**. |
| Recommendations contract | (in above) | Every item has `symbol, name, score, factors`. Score is in [-100, 100], there are ≥3 factors, price ≥ Rs 1, items are sorted by score, the user's own holdings are excluded only for that user, and `limit` is respected. |
| User-data isolation | 6 | User B cannot list, read, modify or delete user A's portfolio, holdings, watchlist, rules, chat sessions/messages (including `/chat/stream` and `/chat/message` on A's `session_id`) or notifications. All attempts return 404, or a no-op 204 where the API is idempotent by design. The DB was checked afterwards to confirm A's rows were unchanged. B's plan and dashboard show none of A's data. |
| Findings (xfail strict) | 9 | See below. |

**No isolation failures were found.** Every query in the CRUD routers is scoped by the verified `user_id`.

## Findings

### F1 (Medium): Infinity in a holding is accepted and persisted, and the user's portfolio list then returns 500 permanently

- **Test:** `test_holding_with_infinite_quantity_is_422`
- **Request:** `POST /api/v1/portfolio/{id}/holdings` with the raw JSON body `{"symbol":"JKH.N0000","quantity":Infinity,"avg_buy_price":10}`
- **Expected:** 422.
- **Actual:**
  - The POST returns **500**.
  - The row is still **committed**: 1 holding in the DB.
  - Every later `GET /api/v1/portfolio/` for that user returns **500**. I verified this with an ad-hoc probe.
- **Cause:** Pydantic v2 floats allow `inf`/`nan` by default. `Field(gt=0)` passes `inf`. Starlette's `JSONResponse` then refuses to encode it.
- **Impact:** A crafted client can put its own account into a permanent error state. The stock mobile app can't do this, because `JSON.stringify(Infinity)` gives `null`.
- **Fix:** Add `allow_inf_nan=False` to `quantity` and `avg_buy_price` (or `model_config = ConfigDict(allow_inf_nan=False)` on `HoldingCreate`). Apply the same to every float input.

### F2 (Medium): A NaN rule threshold is accepted by the schema

- **Test:** `test_rule_with_nan_threshold_is_422`
- **Request:** `POST /api/v1/rules` with `{"symbol":"JKH.N0000","condition_type":"price_above","threshold":NaN}`
- **Expected:** 422.
- **Actual (SQLite):** **503** "Could not save your rule". SQLite stores NaN as NULL, which fails the NOT NULL constraint.
- **Postgres (by inference, not run):** Postgres accepts `'NaN'::float8`, so the row would be stored and the `RuleOut` encoding would give 500. The same would then likely happen on every `GET /rules`, and a NaN comparison never triggers the alert.
- **Fix:** Add `allow_inf_nan=False` to `RuleCreate.threshold` and `RuleUpdate.threshold`.

### F3 (Low): Negative `limit` on chat history is not validated

- **Test:** `test_chat_messages_negative_limit_is_422`
- **Request:** `GET /api/v1/chat/sessions/{id}/messages?limit=-1`
- **Expected:** 422.
- **Actual:** **200**. On SQLite, `LIMIT -1` means unlimited, so the 200-message cap is bypassed. On Postgres, `LIMIT` must not be negative, so it would be a **500** (by inference).
- **Fix:** `limit: int = Query(50, ge=1, le=200)`.

### F4 (Low): Portfolio name has no length bounds

- **Tests:** `test_portfolio_name_bounds_are_validated[""]` and `[x*121]`
- **Request:** `POST /api/v1/portfolio/` with `{"name": ""}` or a 121-character name.
- **Expected:** 422.
- **Actual:** **201** for both on SQLite.
- **Postgres:** `portfolios.name` is `VARCHAR(120)`, so the long name would raise a DataError, giving **500** (by inference). The empty name gives a nameless portfolio card.
- **Fix:** `name: str = Field(min_length=1, max_length=120)`, ideally with `.strip()`.

### F5 (Low, contract): Core mobile endpoints publish no response schema

- **Tests:** `test_core_endpoints_publish_a_typed_response_schema[...]` for `/recommendations`, `/learn/lessons`, `/learn/lessons/{lesson_id}`, `/dashboard/`
- **Expected:** An OpenAPI `$ref`/`properties`/`items` schema for each.
- **Actual:** `{"type":"object"}` for recommendations and dashboard, and `{}` for both learn endpoints. `/notifications/test`, `/notifications/read-all` and most `/auth/*` bodies are untyped too.
- **Impact:** These are the screens the Home and Learn tabs depend on. Nothing checks their shape, so a renamed key (for example `factors` or `watchlist_preview`) reaches the app silently. This suite now pins the keys by hand as a stopgap.
- **Fix:** Add Pydantic models (`RecommendationsOut`, `LessonSummary`, `LessonDetail`, `DashboardOut`) and set them as `response_model`.

### Observations (not failing tests)

- `GET /me/assessment/questions` is public and returns the correct answer and explanation for each of the 5 knowledge checks. That looks intentional (it's a self-check quiz), but it means `knowledge_score` is self-reported. Keep that in mind before using it in RO3/RO4 evaluation.
- Rate limits are in-process per worker (`app/rate_limit.py` already says so), so with N workers the effective limit is N×.

## Not covered here

- The successful `/auth/register`, `/verify-otp`, `/login`, `/refresh`, `/reset-password` and `DELETE /me` paths all call Supabase. I only tested their validation and pre-Supabase branches (unknown user gives 401, unverified user gives 403, and the rate limit). They need a mocked `create_client` in a dedicated auth test.
- Postgres-only behaviour (VARCHAR overflow, negative LIMIT, NaN storage) is inferred from the schema and documented, not executed. No live DB was used, by rule.
