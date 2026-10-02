# InvestAI Test Strategy

**Owner:** S. Sanjeev and P. Sajeevan · **Version:** 1.0, 2 Oct 2026 · **Context:** `.agents/qa-project-context.md`

## 1. Scope and objectives
- **In scope:**
  - FastAPI backend: all routers, the agent and its tools, recommendations, scrapers and sentiment;
  - AI answer quality and safety;
  - the Expo mobile app (static analysis, i18n, accessibility);
  - production health (read-only).
- **Out of scope:** third-party internals (Supabase, NVIDIA NIM, OpenRouter, FCM, cse.lk), which are tested only at their contract boundary; load testing on production (Always Free VM); iOS.
- **Objectives:**
  1. No Critical or High open defects in auth, data isolation or AI safety at release.
  2. Backend line coverage from 62% to 75% or more; every router covered.
  3. AI evaluation: 100% safety pass, at least 90% factual accuracy on live data, 0 invented numbers.
  4. Median AI answer reported honestly against the 3–5 s target.

## 2. Test levels and types
| Level | What | Tool |
|---|---|---|
| Unit | scoring, risk, plan, sentiment, parsing, tool helpers | pytest |
| Integration / API | every route through TestClient + in-memory SQLite + dependency overrides | pytest, FastAPI TestClient |
| Contract | response models; third-party payload parsing (cse.lk, RSS) on recorded fixtures | pytest |
| Security | JWT/OTP/rate limits, IDOR, input handling, secrets, dependency audit | pytest, pip-audit, npm audit |
| AI system | golden set of 30 questions: factual, concept, safety, explainability, multilingual, memory | read-only harness on the real agent |
| Performance | in-process benchmarks; production latency sampling (light, read-only) | pytest timing, httpx |
| Mobile | i18n completeness, accessibility, robustness review, expo-doctor | Node script, static review |
| Exploratory / persona | five beginner personas, manual-research comparison, back-test | agents, browser, scripts |

## 3. Test pyramid
Mostly unit and API tests (fast, offline, deterministic). AI evaluation is a separate, slower, non-deterministic layer, run on demand, never in the PR gate. No device E2E yet (no device farm); mobile is covered by static checks and the existing API tests behind it.

## 4. Risk matrix (likelihood × impact)
| Risk | L | I | Response |
|---|---|---|---|
| AI gives buy/sell advice or invents numbers | M | Critical | Safety golden set, prompt rules, tool-only numbers |
| Auth bypass / IDOR on portfolio, watchlist, rules, chat | L | Critical | Security and API isolation tests |
| Wrong live data (names, time, prices) | M | High | Factual golden set vs DB ground truth |
| Slow or failed answers (free-tier LLM) | H | High | Latency sampling, fallback-chain review |
| Alerts and push never exercised (0% coverage) | H | Medium | API tests for rules, notifications, device |
| Missing Sinhala/Tamil strings, accessibility gaps | M | Medium | i18n script, a11y review |

## 5. Environments
- **Local tests:** SQLite in memory. The local `.env` points at the production DB, so no live writes.
- **AI evaluation:** real agent, read-only harness.
- **Production:** read-only GETs, at most 10 per endpoint.

## 6. Tool rationale
pytest is already used by 420 tests. TestClient + dependency overrides is already the house pattern. pip-audit and npm audit are free and standard. No new frameworks.

## 7. Entry and exit criteria
- **Entry:** branch builds and the existing suite passes, except the known brotli environment test.
- **Exit:**
  - all new QA tests pass;
  - real defects are recorded as strict `xfail` tests with severity;
  - no open Critical; every High has an owner and a fix or a documented limitation.

## 8. Quality gates
- **Pull request:** `pytest` (unit + API + security) green. Coverage must not drop.
- **Release:**
  - all PR gates pass;
  - AI golden set: safety 100%, accuracy ≥ 90%;
  - production health check green;
  - mobile `.env` points at the production API;
  - release-readiness checklist signed.

## 9. Metrics
| KPI | Now | Target |
|---|---|---|
| Backend line coverage | 62% | ≥ 75% |
| Routers with tests | 8/13 | 13/13 |
| AI safety pass rate | from the eval | 100% |
| AI factual accuracy | from the eval | ≥ 90% |
| Median AI answer | ~11 s | 3–5 s (stretch) |
| Open Critical/High defects | from this QA pass | 0 Critical, High documented |
