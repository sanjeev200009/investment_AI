# InvestAI — Project Progress

This document tracks the current progress of the InvestAI project based on the Implementation Roadmap.

## What is Built (Completed)

**Backend Core & Infrastructure**
- [x] FastAPI backend scaffolded with all routers
- [x] SQLAlchemy models: User, Portfolio, ChatSession, MarketData, NewsSentiment, etc.
- [x] Alembic migrations (initial schema + OTP table)
- [x] Supabase Auth integration (register, OTP verify, login, forgot password)
- [x] Brevo email service (OTP emails, welcome email, reset email)
- [x] CSE web scraper (`scraper.py`)
- [x] Celery worker base (`celery_worker.py`)
- [x] Portfolio CRUD endpoints
- [x] React Native mobile app scaffolded

**Backend Services (Recently Completed)**
- [x] Implement AI agent service (`app/services/agent/`)
- [x] Implement full chat router with SSE streaming
- [x] Implement sentiment service
- [x] Implement FCM service
- [x] Wire scrape tasks to DB
- [x] Investment rules checker task
- [x] pgvector migration

## What Needs to Be Built (Remaining)

### Backend — High Priority
- [ ] Fix `dependencies.py` JWT verification (must verify Supabase-signed JWTs, not self-signed)
- [ ] Wire `/stocks` endpoints to real DB queries
- [ ] Implement `/notifications` CRUD fully
- [ ] Add watchlist router (`GET /watchlist`, `POST /watchlist`, `DELETE /watchlist/{symbol}`)
- [ ] Add risk profiling endpoint (`POST /users/risk-profile`)
- [ ] Add device token endpoint (`POST /users/device-token`)
- [ ] Payhere payment integration (`POST /payments/initiate`, `POST /payments/notify`)
- [ ] Add `.env` keys: `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `PAYHERE_MERCHANT_ID`, `PAYHERE_MERCHANT_SECRET`

### Frontend — React Native Screens
- [ ] Splash / Onboarding screens
- [ ] Register screen → OTP verification screen
- [ ] Login screen
- [ ] Risk profiling quiz screen (10 questions)
- [ ] Dashboard screen (real-time market data, watchlist)
- [ ] AI chat screen (SSE streaming, tool result indicators)
- [ ] News feed screen (AI summaries + sentiment badges)
- [ ] Portfolio screen (holdings, P&L, charts)
- [ ] Watchlist management screen
- [ ] Investment rules screen (set/edit/delete rules)
- [ ] Notifications screen
- [ ] Settings screen (language toggle: English / Sinhala / Tamil)
- [ ] Learning module screen
- [ ] Premium subscription screen (Payhere)

### Infrastructure
- [ ] Run `alembic upgrade head` to apply pgvector migration
- [ ] Enable pgvector extension in Supabase dashboard
- [ ] Configure Celery Beat schedule
- [ ] Set up Redis (local or Railway)
- [ ] Configure Firebase project and get FCM server key
- [ ] Set up Payhere merchant account
- [ ] Deploy to Railway / Render

---
*Generated based on current `project_documentation.md` roadmap tracking.*
