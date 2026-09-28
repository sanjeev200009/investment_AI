# InvestAI — Project Progress

Tracked against the remediation plan in `investai-backend/docs/REMEDIATION_LOG.md`, which is the authoritative issue-by-issue record with re-runnable evidence. This file is the one-paragraph-per-issue view; the log is the proof.

## Closed

- **I-01 · Celery pipeline repair** — worker starts, beat window matches the CSE session.
- **I-02 · Auth cutover to verified Supabase identity** — JWKS-verified ES256 (HS256 legacy supported), Clerk removed everywhere.
- **I-03 · Auth hardening** — OTP-before-usable-account, hashed single-use reset tokens in Postgres, attempt caps, `secrets`-based OTPs.
- **I-04 · Market data integrity** — `market_data_latest` upsert table, one timestamp per scrape, all read paths de-N+1'd.
- **I-05 · Real index values** — all 22 CSE indices scraped from `allSectors`; hardcoded ASPI gone; dashboard reads the stored row.
- **I-06 · Real price history** — `daily_close` per symbol-day keyed off the exchange's own timestamps; `portfolio_snapshots` daily valuation; real charts.
- **I-07 · Real fundamentals, real sectors, no fabricated UI** — `company_info` for all quoted symbols, 20 normalised industry groups, twelve fabrications removed.
- **I-08 · News pipeline** — `app/services/news.py`: measured selectors, article-page bodies, publish-date parsing, company-name symbol attribution via `company_info`, one row per (article, symbol), LLM summarisation actually called, politeness/robots considerations documented.
- **I-09 · Watchlist end-to-end** — `Watchlist` model + `GET/POST/DELETE /watchlist` + dashboard `watchlist_preview` from the user's own list + `WatchlistScreen` rewritten (was top-10-by-volume for everyone).
- **I-10 · Investment rules CRUD + screen** — `GET/POST/PATCH/DELETE /rules` validating against the evaluator's own condition table + `RulesScreen`; the 15-minute evaluator finally has rules to evaluate.
- **I-11 · Notifications wired** — `NotificationsScreen` reads `GET /notifications` with mark-read/mark-all/delete; `PATCH .../read`, `POST /read-all`, `DELETE /{id}` added; DUMMY_ALERTS deleted; `notification_service` no longer references the non-existent `user.fcm_token`.
- **I-12 · Push notifications** — `fcm.py` rewritten onto `firebase-admin` HTTP v1 (legacy endpoint was decommissioned by Google in 2024); `UserProfile.device_token` mapped; `POST /me/device-token`; app registers its token after sign-in. *Needs a Firebase service-account JSON at `investai-backend/firebase-key.json` (gitignored) and a dev build on a physical device to demo.*
- **I-13 · Real ranked recommendations** — `GET /recommendations`: a transparent linear score with stated weights (daily change 15% / 4-week momentum 30% / liquidity 25% / news sentiment 30%), per-factor contributions in every response, holdings excluded; home screen shows the reasoning.
- **I-14 · SSE streaming in chat** — `ChatScreen` consumes `POST /chat/stream` (XHR-based SSE, no new dependency) and renders tokens as they arrive plus per-tool ReAct activity lines.
- **I-15 · Multilingual plumbing** — en/si/ta strings for auth + tabs, live-switch language selector in Profile, preference persisted to `user_profiles.language` via `POST /me/language`, and the agent now steers its output language from that column. *Sinhala/Tamil copy needs a native-reader review before submission.*
- **I-16 · Price predictions** — `app/services/predictor.py` writes `price_predictions` (least-squares trend over recent closes, honestly labelled); Celery beat entry at 16:05 Colombo; the agent's prediction tool works and states what the model is.
- **I-17 · Evaluation instrumentation** — request-latency middleware (per-request `duration_ms` log line + `x-response-time-ms` header), `scripts/evaluate_agent.py` (fixed question set, live run, latency percentiles), `scripts/engagement_stats.py`. *Expert-rated reference answers are a supervisor deliverable.*
- **I-19 · Learning content** — CSE-specific, beginner-sequenced lessons mapped to OECD/INFE 2020 dimensions; derivatives article removed; no third-party CDN images. *Content still wants a subject-matter review.*
- **I-20 · Agent robustness** — pre-tool prose no longer dropped (buffered and shown), loop exhaustion answers with an explanation instead of a blank message.
- **I-21 · Dead code and dependencies** — `transformers`/`anthropic`/`google-generativeai`/`groq`/`tenacity`/`structlog` removed (one OpenAI-compatible client serves both providers); model names consolidated in `config.py` (done during the llm.py work); `scratch/` renamed `scratch_dev_only/` and removed from version control.
- **I-22 · API hygiene** — CORS wildcard+credentials fixed (bearer-token app needs no credential mode); `POST /stocks/scrape` now enqueues via Celery and returns 202 instead of running a minute-long scrape inside the request.
- **I-23 · Documentation** — this file, `README.md` and both `.env.example` files rewritten to match reality.

## Open (needs humans, not code)

- **Register a real account end-to-end** and confirm Brevo OTP delivery — every user-scoped feature is verified server-side but still needs one live-user pass.
- **Rotate the OpenRouter and NVIDIA API keys** (they were pasted into a conversation; treated as disclosed).
- **Firebase service-account JSON** at `investai-backend/firebase-key.json` for push.
- **Sinhala/Tamil translation review** by a reader of each language.
- **§13 ground truth** — expert-rated reference answers for the evaluation harness.
- **Supabase plan limits / retention policy** for the append-only `market_data` history.
