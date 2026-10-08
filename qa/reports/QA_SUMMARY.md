# InvestAI: Full QA Report and Release Readiness

**Date:** 2 October 2026 · **Build:** branch `fix/app-polish` (uncommitted) · **Method:** QA skills `petrkindlmann/qa-skills` (context → strategy → plan → execution → release readiness)

**Documents:**
- context: `.agents/qa-project-context.md`
- strategy: `qa/strategy.md`
- plan: `qa/plan.md`
- detailed reports: `qa/reports/*.md`

## 1. What was tested

| Area | How | Result |
|---|---|---|
| Existing regression suite | pytest | 420 passed, 1 environment-only failure |
| API and contract (55 routes) | 183 new tests, TestClient + SQLite | 174 pass, **9 bugs recorded** |
| Security | 204 new tests + config review + dependency audit | 196 pass, **8 findings recorded** |
| Performance and production health | 9 benchmarks + light read-only production probes | production healthy; **AI slow** |
| AI system | 30-question golden set on the real agent (32 calls) | 73% strict / 85% partial-credit accuracy; **safety 100%** |
| Mobile | static review, i18n script, expo-doctor, tsc, eslint | 27 findings: 1 Critical (release config), 2 High |
| Earlier in this session | 5 personas, manual-research comparison, 1-year back-test | separate reports in Downloads |

**Test suite now:** 800 backend tests. 799 pass; 17 are strict `xfail`, each one a known bug; 1 is an environment-only failure. **Line coverage went from 62% to 79%.**

## 2. Key results

- **Security core is solid.**
  - All 43 protected routes reject missing, expired, tampered, `alg:none` and wrong-audience tokens.
  - One-time login codes lock after 5 tries.
  - Reset tokens are single-use.
  - **No cross-user data access** on portfolio, holdings, watchlist, rules, chats or notifications.
  - Raw SQL is parameterised. No secrets are committed.
- **AI safety: 30/30 answers safe.** No buy/sell/hold, no profit promise, no trade, no prompt leak, no other user's data.
- **AI factual accuracy:**
  - every price, index, market cap and top mover matched the database;
  - 2 mislabelled numbers in 30 answers (a factor value shown as a % change; UTC time shown as Sri Lanka time).
- **Production:**
  - `/health` passed 10/10 (p50 287 ms);
  - TLS valid;
  - API docs hidden;
  - every protected route returns 401 without a token.
- **Non-AI speed:** recommendations ~114 ms, lessons ~5 ms, the plan ~11 ms. A dead LLM does not slow Home.
- **i18n:** 658/658/658 keys in EN/SI/TA, none missing.

## 3. Open defects by severity

### Critical (blocks release)
| # | Defect | Area | Fix |
|---|---|---|---|
| C1 | Mobile `EXPO_PUBLIC_API_BASE_URL` is still the localhost dev value; a release build would crash on launch | Mobile config | Restore the production HTTPS URL (backup in scratchpad) before any release build |

### High
| # | Defect | Area | Fix |
|---|---|---|---|
| H1 | **The Tamil/Sinhala script filter garbles answers.** It strips characters inside words ("ிகiai"). *Caused by the persona fix in this session.* | AI | Drop or regenerate whole mixed-script words; re-ask once if too much text is in the wrong script |
| H2 | AI median latency 14–15 s (p90 31–36 s, max 62 s) vs the 3–5 s target. Answers with 5 tool calls came back empty | AI / performance | Fetch data before the LLM for simple price and index questions; cap at 3 rounds; 8 s first-byte timeout, 25 s total budget, skip failing providers |
| H3 | `python-jose 3.3.0` CVE-2024-33663/33664 | Dependencies | Upgrade to ≥ 3.4.0 or move to PyJWT |
| H4 | Mobile `axios 1.13.5` advisories (auth bypass, SSRF) | Dependencies | `axios@^1.15.1` |
| H5 | Login tokens in plain AsyncStorage with `allowBackup=true` | Mobile security | Use `expo-secure-store` (already installed) and disable backup |

### Medium
| # | Defect | Fix |
|---|---|---|
| M1 | Login rate limit bypassed by sending a fake `Authorization` header | Key unauthenticated routes on client IP |
| M2 | `quantity: Infinity` saves a holding, then every portfolio load returns 500 | `allow_inf_nan=False` on `HoldingCreate` |
| M3 | `NaN` threshold accepted on alert rules | Same setting on `RuleCreate`/`RuleUpdate` |
| M4 | "Hayleys" resolves to Hayleys Leisure, not Hayleys PLC | Rank exact or starts-with name matches first in `resolve_symbols` |
| M5 | No overall chat deadline (~60 s wait when all providers are down) | Total time budget |
| M6 | One network error during a token refresh signs the user out; the refresh has no timeout | Retry on network/5xx; add a timeout |
| M7 | Disclaimer text contrast 3.9–4.3:1 (< 4.5); chat answers not announced to screen readers | Darker token; `accessibilityLiveRegion` |
| M8 | Raw axios error text ("Network Error") shown untranslated | Map errors to i18n keys |
| M9 | Unused Android permissions (microphone, overlay, storage) | Remove the unused `expo-av` and `expo-image-picker` |
| M10 | One Celery process with no task time limits; slow AI summaries can delay the 15-min market scrape | Time limits or a separate queue |

### Low
Accounts can be enumerated through the register and login messages. `limit=-1` is accepted on chat messages. Portfolio names have no length limits. Four endpoints have no response model. No HSTS or security headers. `X-Forwarded-For` is trusted when Caddy is bypassed. Internal tool names appear in one answer. Tamil/Sinhala answers lack the disclaimer. Concept answers don't always link a lesson. The Sinhala answer had terminology slips. eslint is broken by prettier 3. `expo` is a patch version behind. versionCode is 1.

### To verify manually
- Supabase row-level security on public tables (the anon key ships in the app).
- Never run `scripts/verify_i03_cleanup.py`: it deletes from `users`, and the local `.env` points at production.
- Device checks: TalkBack/VoiceOver, 200% font size, push delivery, offline behaviour.

## 4. Release readiness: **NO-GO** for a production APK until:
1. C1 is fixed (API URL).
2. H1 is fixed (Tamil/Sinhala garbling) or the filter is reverted.
3. H3–H5 are fixed (dependencies and token storage).
4. M2 and M3 are fixed (data-corrupting validation), both one-line changes.

**The backend fixes can be deployed now:** their tests pass, and the security and isolation core is sound. H2 (latency) is a known, documented limitation for the viva, not a blocker.

## 5. For the thesis
- **RO2:** AI factual accuracy (prices and indices match the DB) and safety at 100% over 30 adversarial and normal questions. Add the 1-year back-test.
- **RO4:**
  - Reliability: 800 automated tests, 79% coverage, production health.
  - Accuracy: matched the exchange.
  - Speed: honest median of 14–15 s vs the 3–5 s target.
  - The manual-research comparison.
- **Limitations:** the AI evaluation is one run per case with one scorer, accurate to roughly ±15 points; no device or real-user testing in this pass.

---

## 6. Blocker fixes (2 Oct 2026, same branch, not yet committed or deployed)

| # | Blocker | Fix | Verified |
|---|---|---|---|
| C1 | Mobile API URL was a dev value; the old backup pointed at a LAN IP, not production | `eas.json` preview/production `env` and `.env` set to `https://138-2-105-105.sslip.io/api/v1` | `expo export` bundle contains the production URL and no localhost; live `/health` 200, `/api/v1/portfolio/` 401 without a token |
| H1 | Tamil/Sinhala filter garbled words | Drops **whole** mixed-script words; the stream cleaner holds back a split word until it is complete; also covers CJK punctuation | New unit tests, including a word split across chunks |
| H3 | `python-jose 3.3.0` CVEs | `python-jose[cryptography]==3.5.0` in `requirements.txt` | Full suite green |
| H4 | `axios 1.13.5` advisories | `axios ^1.20.0` | `npm audit`: no axios advisory |
| H5 | Tokens in plain, backed-up AsyncStorage | New `src/store/tokenStore.js` (expo-secure-store, one-time migration, web fallback); `allowBackup: false` | Android bundle builds; every token read/write goes through `tokenStore` |
| M2/M3 | Infinity/NaN saved and broke the portfolio and rules | `allow_inf_nan=False` on holdings and rules, plus a 422 handler that no longer echoes non-JSON input (it was turning the 422 into a 500) | The former `xfail` tests now pass |
| extra | `limit=-1` on chat messages; portfolio name length | `ge=1`; `min_length=1, max_length=120` | Tests pass |
| extra | Unused microphone, overlay and storage permissions | Removed unused `expo-av` and `expo-image-picker`; `blockedPermissions` | `expo config` shows them blocked |

**Suite after the fixes:** 806 passed; 11 strict `xfail` remain (lower-severity issues such as the rate-limit key and account enumeration); 1 environment-only failure.

**Still open:**
- H2: AI latency, a documented limitation.
- M1: rate-limit key.
- M4: "Hayleys" resolves to the wrong company.
- M5–M8 and M10.
- The npm advisories are in Expo build tooling (CLI, bundler), not the shipped app runtime; they need an Expo SDK upgrade.

**Release readiness:** the blockers are fixed. **GO to build a preview APK *after* the backend is deployed** (so the app talks to a server that has the fixes), then do a device smoke test: login, Home, chat in EN/SI/TA, add a holding, set an alert.
