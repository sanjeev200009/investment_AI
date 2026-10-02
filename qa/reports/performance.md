# InvestAI: performance, reliability and production health

QA pass dated 2026-10-02, run at 14:37 Asia/Colombo (Friday, just after the 14:30 CSE close).
Every number below was measured unless it is labelled **estimate** or **derived**.

**Scope and safety.** Production received only light, read-only GETs: 10 sequential requests to each of 2 public endpoints, 1 request to each of 3 docs URLs and 1 request to each of 15 protected endpoints. Requests were spaced at least 1.1 s apart. No load, concurrency, writes, accounts or tokens were used. The local benchmarks run in-process against in-memory SQLite with the LLM mocked. No application code was changed.

Artifacts:
- `investai-backend/tests/qa/test_performance.py`: 9 benchmark tests. All 9 passed in 6.0 s. Run them with `cd investai-backend && python -m pytest tests/qa/test_performance.py -q`, and add `-s` to print the timings.
- Probe and analysis scripts are kept in the session scratchpad: `perf/probe.py`, `perf/ai_stats.py` and `perf/rss.py`.

---

## 1. Production synthetic check (`https://138-2-105-105.sslip.io`)

### TLS

| Check | Result |
|---|---|
| Certificate chain validates (Python default trust store, SNI) | Valid |
| Issuer | Let's Encrypt `YE2` |
| Validity | 2026-09-29 to 2026-12-28, 86 days left (Caddy renews automatically) |
| Protocol negotiated | TLSv1.3 |
| HTTP/3 advertised | `alt-svc: h3=":443"` |
| HSTS header | **Absent** |

### Public GET endpoints

Client latency is measured from this laptop and includes the network round trip. Server time comes from the app's own `x-response-time-ms` header.

| Endpoint | n | Status | Client p50 | Client p95 | Client max | Server-side median (max) |
|---|---|---|---|---|---|---|
| `GET /health` | 10 | 10/10 × 200 | 287 ms | 373 ms | 414 ms | 232 ms (240) |
| `GET /api/v1/me/assessment/questions` | 10 | 10/10 × 200 | 54 ms | 383 ms | 577 ms (first request) | 1 ms (78, first request) |
| `GET /docs` | 1 | 404 | 57 ms | | | 4 ms |
| `GET /openapi.json` | 1 | 404 | 51 ms | | | 0 ms |
| `GET /redoc` | 1 | 404 | 51 ms | | | 0 ms |

- `/health` returned `{"status":"ok","version":"v1","database":"ok"}`. Its server time stays near 230 ms on every call, while a handler that never touches the database answers in about 1 ms. The whole of that 230 ms is therefore the database. The figure is consistent with two round trips to Supabase (the `pool_pre_ping` probe plus `SELECT 1`) at about 115 ms each. This is **derived**, not measured directly.
- The docs, ReDoc and the OpenAPI schema are correctly hidden in production.
- **Freshness.** The public endpoints carry no data timestamps. Market data freshness (`recorded_at`, `as_of`) is only exposed behind authentication, so it could not be checked without a token, and the rules forbid creating one. The server clock is fine: the `Date` header was 0.1 to 0.9 s behind local UTC.

### Protected endpoints without a token (1 request each)

All **15/15 returned `401`** with `{"detail":"Missing bearer token"}` and `WWW-Authenticate: Bearer`. Responses took 50 to 95 ms, plus one outlier at 216 ms (`/stocks/market`).

The endpoints checked were: `/auth/me`, `/stocks/market`, `/stocks/indices`, `/stocks/sectors`, `/stocks/history/JKH.N0000`, `/stocks/news/JKH.N0000`, `/dashboard/`, `/recommendations`, `/learn/lessons`, `/portfolio/`, `/watchlist`, `/rules`, `/chat/sessions`, `/me/plan` and `/notifications/`.

---

## 2. Local in-process benchmarks

**Setup.** TestClient with in-memory SQLite (StaticPool), with `get_db` and `get_current_user` overridden. The seed has 300 quoted symbols with company info, 12,000 `daily_close` rows (300 symbols × 40 days), 2,000 scored news rows, 22 indices, and one user with 20 holdings, 20 watchlist items and 90 portfolio snapshots.

Each figure is the median of 5 runs after 1 warm-up, from 3 consecutive suite runs on this laptop. Budgets are roughly 10× the measured time, so they catch regressions such as an N+1 query or a quadratic loop rather than noise.

| Benchmark | Measured median (3 runs) | Budget |
|---|---|---|
| `build_recommendations` Low | 32.7 / 37.5 / 34.8 ms | 1500 ms |
| `build_recommendations` Medium | 36.4 / 35.0 / 34.6 ms | 1500 ms |
| `build_recommendations` High | 105.9 / 107.7 / 106.2 ms (38.6 when run alone) | 1500 ms |
| `build_recommendations` default (no profile) | 114.9 / 106.4 / 104.7 ms (37.3–37.5 when run alone) | 1500 ms |
| `GET /api/v1/recommendations?limit=10` (fresh session per request) | 113.5 / 113.7 / 114.5 ms | 1500 ms |
| `resolve_symbols` (6 terms: tickers, names, unknown) | 0.8 ms | 500 ms |
| `POST /me/risk-profile` + `GET /me/plan` | 11.4 / 10.7 / 11.5 ms | 500 ms |
| `GET /learn/lessons` | 3.6 / 3.6 / 3.5 ms | 200 ms |
| `GET /learn/lessons/{id}` (writes a LessonView) | 4.8 / 4.4 / 4.6 ms | 300 ms |
| `GET /dashboard/` with the LLM mocked to hang for 2 s | 7.4 / 7.3 / 7.9 ms | 800 ms |

How to read these:
- The recommendation weights do not change the amount of work. The roughly 3× gap between the High/default rows and the Low/Medium rows is a test-order effect: run alone, High and default take 37–39 ms. The **realistic per-request cost** is the endpoint row, because each request gets a fresh session and has to load 300 quotes, 300 company profiles and 12,000 closes: about **110 ms on SQLite**. On Supabase the same three queries also pay network round trips and transfer for 12,000 rows. That cost is not measured; it would need an authenticated production probe.
- The dashboard test confirms by measurement that a hung LLM never blocks Home. Insights are generated on a background thread, and the response falls back to headline cards.

---

## 3. AI answer latency (existing measurements, no new LLM load)

**Source.** The persona state files (`scratchpad/personas/state/*.json`, `log[].seconds`) and `scratchpad/personas/ro4_app.json`.

**What was measured.** `harness.py` times `core.run_agent()`, which is the **non-streaming** path. It ran on the laptop against the real LLM chain and the production database. The figure is the **total time to a complete answer**, not the time to the first streamed token.

### Overall

| Set | n | Median | p90 | Max | Min | Mean | > 5 s | > 30 s |
|---|---|---|---|---|---|---|---|---|
| **All** | **45** | **15.1 s** | **30.9 s** | **48.6 s** | 3.9 s | 16.8 s | **42/45 (93%)** | **5/45 (11%)** |
| Personas (5 users) | 37 | 15.9 s | 31.6 s | 48.6 s | 3.9 s | 17.7 s | 34/37 | 4/37 |
| RO4 tasks T1–T8 | 8 | 10.7 s | 20.8 s | 31.5 s | 5.2 s | 12.6 s | 8/8 | 1/8 |

### By number of tool calls

| Tool calls | n | Median | p90 | Max | > 5 s | > 30 s |
|---|---|---|---|---|---|---|
| 0 | 9 | 9.0 s | 14.7 s | 15.9 s | 7/9 | 0/9 |
| 1 | 25 | 11.0 s | 27.9 s | 47.8 s | 24/25 | 2/25 |
| 2 | 6 | 19.1 s | 30.6 s | 34.0 s | 6/6 | 1/6 |
| 3 | 1 | 16.2 s | | | 1/1 | 0/1 |
| 4 | 1 | 37.4 s | | | 1/1 | 1/1 |
| 5 | 3 | 30.0 s | 44.9 s | 48.6 s | 3/3 | 1/3 |

### By tool and by persona

An answer counts under every tool it used.

| Tool used | n answers | Median | Max |
|---|---|---|---|
| `get_market_overview` | 10 | 13.9 s | 21.0 s |
| `get_stock_data` | 15 | 15.1 s | 48.6 s |
| `search_financial_knowledge` (embedding + pgvector) | 14 | **25.1 s** | 48.6 s |
| `get_stock_news` | 4 | **32.8 s** | 37.4 s |
| `get_price_prediction` | 1 | 6.9 s | 6.9 s |

| Persona (language) | n | Median | Max |
|---|---|---|---|
| Dilani (Sinhala) | 7 | **27.8 s** | 47.8 s |
| Fathima (Tamil) | 7 | 17.7 s | 48.6 s |
| Nimal (EN beginner) | 8 | 17.1 s | 28.0 s |
| Ruwan (EN) | 8 | 12.2 s | 34.0 s |
| Kasun (EN, terse) | 7 | 9.0 s | 27.3 s |

Other observations:
- **Answer length barely explains latency.** The Pearson correlation between answer characters and seconds is 0.13 (median answer 1,042 characters). The time goes into model rounds and tool round trips, not into generating text.
- **Every run that made 5 tool calls ended with no answer.** All 3 such runs (22.8 s, 30.0 s, 48.6 s) returned the `EMPTY_ANSWER` fallback, "I couldn't put together an answer this time". In each one `search_financial_knowledge` was called 3–5 times. The user waited the longest and got nothing.

### Timeout and fallback chain

Taken from `app/services/llm.py` and `app/config.py`. Secrets were not read or printed; the code only checks that the provider keys exist.

1. **Provider chain, in order:**
   - `nvidia` (`nemotron-3-super-120b-a12b`)
   - `openrouter` (`qwen/qwen3.8-27b:free`)
   - `nvidia-backup` (`openai/gpt-oss-20b`)

   A provider without a key is dropped from the chain. The SDK's own retries are off (`max_retries=0`).
2. **What triggers failover:** a timeout, a connection error, or HTTP 401/402/403/404/408/409/410/413/429/5xx/529. HTTP 400 and local errors raise immediately and do not fail over.
3. **`LLM_TIMEOUT_SECONDS = 20.0`** is passed to the OpenAI client as a single float. httpx applies it **per phase** (connect, write, pool, and each read), **not as a total**:
   - A provider that never sends headers costs about 20 s before the next one is tried.
   - Once streaming starts there is no total cap. A stream that sends one chunk every 19 s never times out.
4. **Agent loop:** up to `MAX_LOOPS = 5` LLM calls. The last call is offered no tools. `AGENT_MAX_TOKENS = 6000`. Failover is decided again for every call.
5. **Tools:**
   - Embeddings use their own `httpx` client with a 30 s timeout. The query embedding is one call; the first lesson search also embeds all 9 lessons as a batch, which is cached per process.
   - The pgvector search falls back to `ILIKE` keyword search.
6. **Chat endpoint:** `chat.py` has no overall deadline. `LLMUnavailable` becomes an SSE `error` event only after every provider has failed.

**Worst-case latency (derived from the code above, not measured):**
- **All providers hung:** 3 × 20 s = **about 60 s** before the user sees the error event, on the first round.
- **Primary and secondary hung, backup answers, every round:** 5 rounds × 40 s of failover = **200 s**, plus the backup's own generation time on each round, plus up to 30–60 s per embedding call. Generation itself has no ceiling.
- **Measured maximum to date:** 48.6 s.

---

## 4. Reliability review

### Celery Beat schedule (`celery_worker.py`, timezone Asia/Colombo)

| Job | Schedule | Retries (countdown) |
|---|---|---|
| `scrape_cse_data` | every 15 min, 09:00–14:45, Mon–Fri | 3 (60 s) |
| `scrape_cse_indices` | :05/:20/:35/:50, 09–14 h, Mon–Fri | 3 (60 s) |
| `scrape_and_analyse_news`, which chains to `analyse_sentiment_batch` and then `embed_news_articles` | every 30 min, 24/7 | 3 (120 s); then 2 (60 s); then 2 (90 s) |
| `check_investment_rules`, which fans out to `send_push_for_rule` | every 15 min, 09–14 h, Mon–Fri | 3 (120 s); then 3 (30 s) |
| `snapshot_portfolio_values` | daily 15:10 | 3 (300 s) |
| `snapshot_recommendations` | 15:15, Mon–Fri | 3 (300 s) |
| `refresh_company_info` | daily 15:40 | 2 (600 s) |
| `update_price_predictions` | daily 16:00 | 2 (300 s) |

Settings that apply to every job:
- `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`.
- **No `time_limit` or `soft_time_limit` on any task.**
- Redis runs with no persistence, so queued tasks are lost on a restart. The compose comment says this is accepted.

### Single points of failure on the 1 OCPU / 1 GB VM (`docker-compose.micro.yml`)

| Component | Copies | Effect if it fails |
|---|---|---|
| `api` (uvicorn `--workers 1`) | 1 | Full outage. Docker restarts it, and its healthcheck runs `/health` every 30 s. |
| `worker` (`--concurrency=1`) | 1 process | All background work stops. The worker has no healthcheck: if it hangs, nothing restarts it and nothing alerts. |
| `beat` | 1 | Scrapes, rules, snapshots and predictions stop silently. Beat has no healthcheck. |
| `redis` | 1 | `.delay()` fails and Beat cannot enqueue anything. Redis does have a healthcheck. |
| `caddy` | 1 | Full outage, including TLS. |
| Supabase (free tier) | external | `/health` returns 503, and every authenticated endpoint fails. |

**Memory headroom.** Measured on this laptop, one Python process takes **115 MB** of working set just after importing `app.main`, up from a 13 MB baseline, and **116 MB** with the Celery tasks also imported. The micro stack runs at least 4 such interpreters:
- `api`
- the `worker` parent
- its prefork child
- `beat`

Together that is about **460 MB before any request or task does work** (**derived**: 4 × 115 MB). On top of that come Redis, Caddy and the OS. Redis and Caddy usage was not measured: no access to the VM. A 1 GB VM is left with little room. The 2 GB swap mentioned in `docker-compose.micro.yml` keeps the containers alive, but swapping causes multi-second latency spikes. Confirm on the VM with `docker stats --no-stream`.

The documentation disagrees with the context file: `deploy/README.md` describes an **Ampere A1.Flex with 2 OCPU / 12 GB**, while the QA context and `docker-compose.micro.yml` describe 1 OCPU / 1 GB. Confirm which one is in production.

### When cse.lk is down

The code path:
1. `scrape_cse_data` and `scrape_cse_indices` raise and retry 3 times, 60 s apart, then give up with a logged exception. The next Beat tick tries again.
2. The app keeps serving the last stored `market_data_latest` and `market_index_latest` rows.
3. The agent tools return `recorded_at` and `as_of` in Colombo time, so the AI can say how old the data is.

Nothing signals the outage:
- `/health` stays `ok`.
- The scrape failure is not surfaced to users or to any alert.
- `refresh_company_info` (2 retries, 600 s apart) leaves yesterday's fundamentals in place.

### When every LLM provider is down

| Feature | Behaviour |
|---|---|
| Chat (`/chat/stream`) | About 60 s of failover, then an SSE `error` event ("could not answer right now"). No answer and no fast fail. |
| Dashboard insights | Unaffected. A background thread runs the LLM, and the response falls back to headline cards. Measured at 7.4 ms with a hung LLM. |
| News summaries | `summarise_article` returns `None`, and the lede is kept. VADER sentiment still runs. Each article costs up to about 60 s of failover, processed **one at a time inside the single Celery worker**. |
| Embeddings / RAG | The NVIDIA embeddings call uses the same key and has no other provider. `search_financial_knowledge` falls back to keyword search. Lesson search falls back to keyword ranking. |

---

## 5. Findings

| ID | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| P-01 | **High** | AI answers miss the 3–5 s target by 3–6× | Median 15.1 s, p90 30.9 s, max 48.6 s; 42 of 45 answers over 5 s | See section 6 |
| P-02 | **High** | Long tool loops end with **no answer** | All 3 of the 5-tool-call runs returned `EMPTY_ANSWER` after 22.8–48.6 s | Cap `MAX_LOOPS` at 3. Stop repeat calls to `search_financial_knowledge` (deduplicate by tool name and arguments; allow at most 1 knowledge search per turn). Force a final answer from the facts gathered so far. |
| P-03 | **High** | Chat has no end-to-end deadline. The 20 s timeout applies per phase, not in total. | Code: `llm.py` and `chat.py`. Worst case about 60 s to an error event with all providers down, and no cap on streaming. | Wrap each `acreate` call in `asyncio.timeout(...)` and the whole turn in an overall budget of about 25 s. Lower the time-to-first-byte timeout to 8 s with `httpx.Timeout(connect=3, read=8, ...)`. Add a circuit breaker that skips a provider for 5 minutes after it fails. |
| P-04 | Medium | Sync SQLAlchemy calls run on the event loop inside the async chat generator and tools. With `--workers 1`, every DB round trip during a chat blocks every other request. | Code: `core.py` and `tools.py` (`self.db.query` inside `async def`); `micro.yml` sets `--workers 1`. The DB round trip is about 115 ms (derived from `/health`). | Run the tool DB calls with `run_in_threadpool` or `asyncio.to_thread`. Alternatively run 2 uvicorn workers if memory allows (see P-06). |
| P-05 | Medium | A single Celery process with no task time limits. LLM summarisation of each news batch, one article at a time, shares that process with the 15-minute market scrape. When providers hang, the scrape is delayed. | `--concurrency=1`; no `time_limit` set anywhere; failover can cost about 60 s per article | Set `soft_time_limit`/`time_limit` on every task, e.g. 120/180 s for scrapes. Route LLM work (`analyse_sentiment_batch`, `embed_news_articles`) to a separate low-priority queue, or skip summarisation when the circuit breaker is open. |
| P-06 | Medium | Tight memory on 1 GB | About 115 MB per interpreter (measured), about 460 MB for 4 interpreters (derived) | Use `--pool=solo` or `threads` for the worker, which drops the prefork child. Add `mem_limit` per service. Measure with `docker stats` and record it in this report. |
| P-07 | Medium | Monitoring cannot see stale data, a dead worker or a dead Beat | `/health` checks only the DB. `worker` and `beat` have no healthcheck. A scrape that fails after its retries only writes a log line. | Add a public, read-only `/health/data` endpoint that returns the newest `market_data_latest.recorded_at` and `market_index_latest.recorded_at` with their age in minutes. A synthetic probe then asserts age < 30 min during the session. Add a heartbeat key per Beat job and a healthcheck on `worker` and `beat` (`celery inspect ping`). |
| P-08 | Low | Every DB-backed request costs about 230 ms of database time on the server | `/health` server time 229–240 ms, against 1 ms for a handler that does not touch the DB | Check that the Supabase region matches the VM region. Replace `pool_pre_ping` with `pool_recycle=300`, which removes one round trip per checkout, or use the Supabase pooler in the same region. |
| P-09 | Low | `search_financial_knowledge` and `get_stock_news` answers are the slowest | Medians of 25.1 s and 32.8 s, against 13.9 s for market overview | Cut the embedding timeout from 30 s to 5 s with the keyword fallback. Cache query embeddings (LRU). Precompute the lesson vectors at startup. |
| P-10 | Low | No `Strict-Transport-Security` header | Probe headers | Add `header Strict-Transport-Security "max-age=31536000"` to the Caddyfile. |
| P-11 | Info | The deploy README and the QA context disagree on VM size | README says 2 OCPU / 12 GB; the context and `micro.yml` say 1 OCPU / 1 GB | Confirm and correct the documentation. |
| OK | Pass | TLS is valid (TLSv1.3, 86 days left). Docs and OpenAPI are hidden. All 15 protected GETs return 401. Dashboard is unaffected by LLM outages. Local hot paths stay at or below about 115 ms even at 300 symbols × 40 days. | Sections 1–2 | |

---

## 6. How to reach the 3–5 s target

Recommendations are in order of expected impact, with the supporting measurement for each.

1. **Measure the right thing first.** For a streamed answer, the 3–5 s target should be judged on *time to first token*. Production already logs `chat_timing first_token_ms=… total_ms=…` from `chat.py`. Pull a week of those lines and report the median and p90. The 15.1 s median above is *total* time on the non-streaming path.
2. **Skip the tool-selection round for simple data questions.** Answers with no tool calls took a median of 9.0 s, against 11.0 s with one tool and 19.1 s with two. Every tool round adds a full LLM call.
   - Detect the intent before calling the model. `resolve_symbols` measured 0.8 ms, and price, index, top-gainer and compare questions are recognisable.
   - Prefetch the data, then make **one** LLM call with the facts already in the prompt.
   - RO4 tasks T1–T4 and T6 fit this path.
3. **Answer instantly from a template where possible.** A price or index lookup can show a server-rendered fact card in under 1 s (local DB paths are under 120 ms), while the LLM explanation streams in underneath it. The user then perceives an answer within the target.
4. **Bound the loop and the timeouts** (P-02, P-03): `MAX_LOOPS` of 3, at most 1 knowledge search per turn, an 8 s first-byte timeout, an overall budget of about 25 s, and a circuit breaker. Together these remove the 30–60 s tail and the empty answers.
5. **Cut the cost of reasoning.** Reasoning stays on for the agent role, and `AGENT_MAX_TOKENS` is 6000. The Sinhala persona's median was 27.8 s, against 9.0–17.1 s for the English personas. Turn reasoning off on the final no-tools round, and test a smaller token budget per language with the evaluation set.
6. **Speed up RAG** (P-09): a 5 s embedding timeout, cached query embeddings, and the 9 lessons served from memory when the query matches lesson keywords.
7. **Unblock the event loop** (P-04), so one slow chat does not add latency to everyone else's requests on the single worker.
8. **Monitor continuously.** Schedule the probe in `perf/probe.py` (read-only, 1 request per endpoint per 5 min) and add the `/health/data` freshness assertion (P-07). Alert after 2 consecutive failures.
