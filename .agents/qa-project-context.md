# QA Project Context: InvestAI

## Product
AI-powered investment-education assistant for **beginner investors on the Colombo Stock Exchange (CSE)**, built as a final-year research project. Four research objectives:
- **RO1 Build:** a personalised, trilingual (EN/SI/TA) learning assistant.
- **RO2 Evaluate:** agentic AI with live data and explainable recommendations.
- **RO3 Assess:** satisfaction and trust.
- **RO4 Measure:** accuracy, response time and reliability.

The app is **educational and must never give buy, sell or hold advice**.

## Stack
- **Backend** `investai-backend/`: Python 3.11, FastAPI, SQLAlchemy, Supabase Postgres (+pgvector, Auth), Celery + Beat + Redis, Caddy. Production runs on an Oracle Cloud Always Free VM (1 OCPU / 1 GB) with Docker compose, at `https://138-2-105-105.sslip.io`.
- **AI agent** `app/services/agent/`: tool loop of up to 5 rounds. Tools: `get_stock_data`, `get_stock_news`, `get_user_portfolio`, `get_price_prediction`, `search_financial_knowledge`, `get_market_overview`, `explain_recommendation`. LLM chain: NVIDIA NIM → OpenRouter → NVIDIA backup, free tier, 20 s timeout per provider. Answers stream over SSE (`/api/v1/chat/stream`).
- **Mobile** `investai-mobile/`: Expo SDK 54, React Native, React Navigation v7, expo-notifications (FCM), i18n in EN/SI/TA (`src/i18n/translations.js`).
- **Data:** cse.lk scraper (prices every 15 min during the session, daily closes, indices), RSS news with VADER sentiment, a linear factor recommendation model (`app/services/recommendations.py`), 9 lessons (`app/content/lessons.py`).

## Tests today
- `investai-backend/tests/`: **~420 pytest tests**. They use **in-memory SQLite plus `app.dependency_overrides`** for `get_db` and `get_current_user` (see `tests/test_plan.py`, `tests/test_chat_stream.py`). No live DB is used.
- Known environment-only failure: `test_news_pipeline.py::test_undecoded_detects_unsupported_encoding` (brotli is installed on this PC).
- Mobile: **no automated tests**. Expo web can run, with configs in `.claude/launch.json`.
- No coverage tooling and no CI test gate.

## Environments: hard rules for testers
- **The local backend's `.env` points at the PRODUCTION Supabase database.** Never run write operations (register, portfolio, watchlist, rules, chat sessions) against a running local or production server. Use TestClient + SQLite + dependency overrides instead.
- **Never create accounts, never send OTP emails, never mint JWTs with the real `SECRET_KEY` for real users.** Use a test secret inside tests.
- **Production:** only light, read-only GETs on public endpoints. No load or stress testing against production.
- **Never print secrets** from `.env` or config files. Report only that a secret exists and where.
- Do not commit, push or deploy. Do not modify application code; write tests and reports only.

## Risk areas (highest first)
1. The AI gives buy/sell advice, invents numbers, or mixes languages (safety, trust).
2. Auth and token handling, user-data isolation (portfolio, watchlist, rules, chat).
3. Live-data correctness (prices, indices, company names, Sri Lanka time).
4. Response time: median AI answer ~11 s against a 3–5 s target; free-tier provider outages.
5. Recommendation model correctness and explainability.
6. Push notifications and alert rules (never exercised end to end).
7. Mobile i18n completeness and accessibility.

## Recent work (branch `fix/app-polish`, uncommitted)
Persona-test fixes: tool argument coercion, company names in tools, Sri Lanka time, script filtering for Tamil/Sinhala, the `explain_recommendation` tool, ranking rules (≥3 factors, price ≥ Rs 1, one share class per company), a sentiment lexicon, and the agent `max_tokens` raised to 6000.
