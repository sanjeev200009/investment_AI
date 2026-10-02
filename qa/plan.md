# InvestAI Test Plan: Full QA Pass, 2 Oct 2026

**Scope:** release candidate on branch `fix/app-polish` (backend, AI agent, mobile). **Strategy:** `qa/strategy.md`.

| # | Area | Requirement / risk | Test approach | Priority | Owner | Output |
|---|---|---|---|---|---|---|
| 1 | Existing suite + coverage | No regressions; find untested code | `pytest --cov=app` | P0 | lead | coverage table (below) |
| 2 | API + contract | Every route: auth, validation, happy path, isolation, schema | TestClient + SQLite | P0 | QA agent: API | `tests/qa/test_api_contract.py`, `reports/api_contract.md` |
| 3 | Security | JWT/OTP/rate limits, IDOR, injection, config, secrets, dependencies | pytest + audits | P0 | QA agent: security | `tests/qa/test_security.py`, `reports/security.md` |
| 4 | AI system | Accuracy, safety, explainability, language, memory | 30-question golden set, real agent | P0 | QA agent: AI | `reports/ai_system.md` |
| 5 | Performance + production health | Latency, freshness, reliability, worst case | benchmarks + light production GETs | P1 | QA agent: performance | `tests/qa/test_performance.py`, `reports/performance.md` |
| 6 | Mobile | i18n, accessibility, robustness, release config | static review + scripts | P1 | QA agent: mobile | `scripts/check_i18n.js`, `reports/mobile.md` |
| 7 | Exploratory (done earlier) | Beginner journeys, manual-research comparison, back-test | personas, browser, scripts | P1 | lead | persona, RO4 and back-test reports |
| 8 | Release readiness | Go/no-go | checklist from findings | P0 | lead | `reports/QA_SUMMARY.md` |

**Out of this pass:** device E2E (no device or farm), load testing (Always Free VM), real-user SUS/TAM study.

**Exit:** see the strategy, §7.

## Baseline coverage (item 1)
**62% total** (3,781 statements, 1,454 missed); 420 passed, 1 known environment failure.

**0% coverage:** `routers/rules.py`, `routers/watchlist.py`, `routers/notifications.py`, `routers/device.py`, `routers/recommendations.py`, `services/notification_service.py`, `services/predictor.py`, `schemas/chat.py`, `main.py`.

**Under 50%:** `routers/auth.py` 38%, `services/llm.py` 32%, `services/agent/embeddings.py` 24%, `routers/stocks.py` 42%, `services/recommendations.py` 42%, `routers/dashboard.py` 45%, `routers/portfolio.py` 47%.
