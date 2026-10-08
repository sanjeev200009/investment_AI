# InvestAI mobile: QA report (static analysis)

- **Scope:** `investai-mobile/` (Expo SDK 54, RN 0.81, React Navigation 7), branch `fix/app-polish` with uncommitted changes, 2026-10-02.
- **Method:** No device or emulator was attached, so this pass is static review plus scripted checks. Nothing was run against a backend. App source, `package.json` and `.env` were not modified, and no secret values were printed.
- **Tools run:**

| Check | Result |
|---|---|
| `node qa/scripts/check_i18n.js` (new) | exit 0, 0 missing keys |
| `npx expo-doctor` | 17/18 checks passed; `expo` 54.0.35 vs expected ~54.0.37 (patch) |
| `npx tsc --noEmit` | exit 0. This only checks syntax and module resolution, because `checkJs` is off and the source is all `.js` |
| `npx eslint App.js src` (project config) | **crashes**: `prettier.resolveConfig.sync is not a function`, because eslint-plugin-prettier is incompatible with prettier 3 |
| `npx eslint ... --rule "prettier/prettier: off"` | 399 problems: 10 errors (all `react-hooks/exhaustive-deps`), 389 warnings (178 inline styles, 176 `curly`, 13 `no-console`, 7 unused vars, 3 nested components) |
| WCAG contrast calculation for the colours in `src/theme/tokens.js` | see the Accessibility section |
| Regex scan of touchables (scratch script, not committed) | 49 touchables found; details below |

---

## Release blockers

1. **API base URL is a localhost dev value.** `investai-mobile/.env` sets `EXPO_PUBLIC_API_BASE_URL` to `http://localhost…`. This is intentional for dev and was left untouched. Before any release or preview build:
   - Set an HTTPS production URL (for example `https://138-2-105-105.sslip.io/api/v1`) in the **EAS `preview`/`production` environment**.
   - `.env` is git-ignored and there is no `.easignore`, so EAS will not upload `.env`.
   - If the EAS variable is missing, `src/api/axiosConfig.js:12-13` throws at import time and the release app **crashes on launch**. If it is set to http, Android blocks cleartext (`axiosConfig.js:15-16` only logs an error).
2. **Release signing uses the debug keystore** in the local prebuild (`android/app/build.gradle:112-115`). `android/` is git-ignored, so EAS regenerates it with managed credentials. A locally built `gradlew assembleRelease` APK is debug-signed and cannot be updated on the Play Store. Build only through EAS, or configure a real keystore.
3. **Tokens are stored in plaintext AsyncStorage and the app allows backup.**
   - Access and refresh tokens and `cached_user` are written to AsyncStorage (`src/store/authStore.js:32-39`, `src/api/axiosConfig.js:107-110`).
   - The manifest has `android:allowBackup="true"` (`android/app/src/main/AndroidManifest.xml:16`). Its backup rules only exclude SecureStore, so the refresh token can end up in a Google backup.
   - `expo-secure-store` is installed and its plugin is configured (`app.json` plugins), but nothing imports it.
4. **Sinhala/Tamil financial terms still need native-speaker review.** `src/i18n/translations.js:7-10` and `src/i18n/screens/si.js:2` say so themselves. The check found 100% key coverage, but a script cannot check quality.
5. **Declared permissions need a decision before Play submission.**
   - The merged main manifest declares `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`, `SYSTEM_ALERT_WINDOW`, and `READ_EXTERNAL_STORAGE`/`WRITE_EXTERNAL_STORAGE` (`AndroidManifest.xml:2-8`).
   - No source file uses audio, overlays or storage. `expo-av` and `expo-image-picker` are dependencies but are never imported.
   - Fix: add `android.blockedPermissions` in `app.json`, or remove the unused packages.

---

## Findings

| # | Severity | Area | Evidence (file:line) | User impact | Fix |
|---|---|---|---|---|---|
| 1 | **Critical (release)** | Config | `.env` `EXPO_PUBLIC_API_BASE_URL=http://localhost…`; `src/api/axiosConfig.js:10-16` | Release build either crashes on launch (variable unset in EAS) or cannot reach the API | Set an HTTPS URL in the EAS preview/production environment; verify with `eas env:list` before building |
| 2 | **High** | Security | `src/store/authStore.js:32-39`, `src/api/axiosConfig.js:65,97,107-110`, `AndroidManifest.xml:16` (`allowBackup="true"`) | On a rooted device, or through a device backup, the refresh token is readable and allows a long-lived session takeover | Keep `token`/`refresh_token` in `expo-secure-store` (already installed); keep `cached_user` in AsyncStorage or exclude it from backup |
| 3 | **High (conditional)** | Config | `android/app/build.gradle:112-115` (`release { signingConfig signingConfigs.debug }`) | A locally built release APK is debug-signed | Release builds go through EAS only, or configure a real keystore |
| 4 | **Medium** | Auth robustness | `src/api/axiosConfig.js:141-162` | If the access token is expired (401) and the `/auth/refresh` call then fails for a transient reason (network drop, 5xx, Supabase outage), the catch at :149 falls through to :157, deletes both tokens and signs the user out. This contradicts the offline-tolerant intent in `authStore.js:94-112` | Clear the session only when refresh returned 400/401, or when there is no refresh token; keep tokens on network errors and 5xx |
| 5 | **Medium** | API robustness | `src/api/axiosConfig.js:102-106` | The refresh request is a bare `axios.post` with **no timeout**. On a hung connection every queued 401 request waits forever on `refreshInFlight`, so screens spin indefinitely | Pass `{ timeout: 15000 }` |
| 6 | **Medium** | API robustness | `src/api/axiosConfig.js:31` | A single 60 s timeout covers every endpoint, including simple list GETs. On a bad network the user waits a minute before seeing an error | Use about 15 s by default and a per-call override for slow endpoints. Chat already uses its own 120 s XHR timeout (`src/api/sse.js:98`) |
| 7 | **Medium** | i18n / errors | `err.message` shown in the UI: `AllTopMoversScreen.js:41`, `NotificationsScreen.js:68`, `RulesScreen.js:56`, `StockBrowseScreen.js:126`, `StockDetailScreen.js:110-111`, `WatchlistScreen.js:35`. English fallbacks in `axiosConfig.js:21,25`. Backend `detail` shown as-is in about 15 places | Sinhala/Tamil users see raw axios English, for example "Network Error", "timeout of 60000ms exceeded" or "Request failed with status code 502" (Caddy 502 bodies have no `detail`) | Map errors with no response, 5xx and timeouts to translated keys (`auth_network_error` and `error_generic` already exist); show backend `detail` only for 4xx validation |
| 8 | **Medium** | Accessibility (contrast) | `palette.faint #6B7078` (`src/theme/tokens.js:18`) used as text directly on the gradient: AI disclaimer `HomeScreen.js:508`, `PortfolioScreen.js:216`, `SplashScreen.js:158` (12pt), `VictoryScreen.js:168` (12pt), `ChatScreen.js:522` (11pt) | Measured ratios are 3.87:1 on `#B6EFD8`, 4.07:1 on `#E6E7F8` and 4.29:1 on `#D9F4EA`, all below AA 4.5:1 for small text. The **"not financial advice" disclaimer** is the text most affected | Use `palette.muted` (#4C525B, 6.1:1 on mint) for disclaimers, or darken `faint` to about #5A5F67 |
| 9 | **Medium** | Accessibility (screen reader) | `src/screens/ChatScreen.js` has no `accessibilityLiveRegion` or `announceForAccessibility` for the streamed answer (grep finds none; only Toast, Assessment and ActionFeedbackModal have them) | TalkBack/VoiceOver users get no notice when the AI answer arrives, which takes about 11 s, in the app's main feature | Announce on `__stream_end` (for example "Answer ready"), or wrap the last AI bubble in `accessibilityLiveRegion="polite"` |
| 10 | **Medium** | Accessibility (touch target) | `src/screens/SplashScreen.js:81-88`: `Pressable` wraps `Chip` (`ui.js:393-396`: paddingVertical 8 + 13pt text, about 34pt tall) with no `chipHit`/`minHeight` | The language picker, the first control a SI/TA user needs, is below the 44pt minimum | Add `style={styles.chipHit}` (`minHeight: sizes.touch`), as Notifications and Rules already do |
| 11 | **Low** | Accessibility (contrast) | Badge: white on `#FF6B6B`, 10pt bold (`ui.js:382`, `TabNavigator.js:222-224`) | 2.78:1. Unread count is hard to read | Use a darker badge, for example `#B3261E` (6.5:1 with white) |
| 12 | **Low** | Accessibility (roles) | No `accessibilityRole` on: `HomeScreen.js:356` (avatar → profile), `:403`, `:407` (portfolio/watchlist pills), `:527` (expand toggle, also lacks `accessibilityState.expanded`), `:573` ("See all"), `:597`; `StockBrowseScreen.js:68`; `StockDetailScreen.js:451` (news opens an external URL and should be `link`) | The screen reader does not announce these as buttons or links | Add `accessibilityRole="button"`/`"link"`, plus `accessibilityState={{ expanded: open }}` on :527 |
| 13 | **Low** | Accessibility | `TabNavigator.js:142,167`: each tab's visible `<Text>` label sits outside the touchable and is not hidden. The bar has no `tablist` role. The badge label reads only `"Alerts, 3"` | Each tab is read twice. The unread count has no meaning attached | Set `importantForAccessibility="no"` on the label Text; label the badge as "Alerts, 3 unread" through t() |
| 14 | **Low** | Accessibility (font scaling) | `allowFontScaling`/`maxFontSizeMultiplier` are never set (good, scaling is on). Some containers have fixed `height`: `ChatScreen.js:541` (suggestion chip `height: 44`, 13pt), `ui.js:385` (`pill` height 62), tab bar slots | At 200% system font, text in fixed-height pills may clip. Not verified on a device | Use `minHeight` instead of `height` for text containers; test at the largest font size on a device |
| 15 | **Low** | Hard-coded string | `src/components/InitialsAvatar.js:10,20`: ``accessibilityLabel={`Profile: ${name \|\| 'Investor'}`}`` | Screen reader speaks English in SI/TA | Use `t('home_profile_settings')`; `home_investor` already exists |
| 16 | **Low** | Hard-coded / locale | Dates use `'en-GB'` and numbers `'en-US'` (`HomeScreen.js:39,52,286`, `NotificationsScreen.js:30`, `StockBrowseScreen.js:40,45`, `StockDetailScreen.js:32,47`, `ui.js:234`). Market cap `"Rs. 1.2B/M/T"` (`StockDetailScreen.js:39-42`). Currency prefix mixes `LKR` (Home, Portfolio, Watchlist) with `Rs`/`Rs.` (StockDetail) | English month names and abbreviations in SI/TA. The currency label is inconsistent between screens | Choose one currency label; take month names from translations or use `si-LK`/`ta-LK` with a fallback |
| 17 | **Low** | Robustness | `ChatScreen.js:230-237`: after `done` on a new chat, the session id is taken from `GET /chat/sessions?active_only=true` → `data[0]` | If several sessions are active, a follow-up message can attach to the wrong conversation | Have the server include `session_id` in the `done` event |
| 18 | **Low** | Robustness | `ChatScreen.js:257-266`: a stream 401 whose refresh fails shows "unreachable" but does not sign out (the stream bypasses the axios interceptor) | Confusing state; the next axios call will sign out anyway | Call the unauthorized handler when the refresh fails |
| 19 | **Low** | Hooks | eslint `exhaustive-deps` (10): `t` is missing from `useCallback` deps in Chat:282, Learn:31, Lesson:24, Notifications:73, Portfolio:72, Rules:61; also `App.js:43`, `Toast.js:56`, `ActionFeedbackModal.js:54`, `AuthSuccessScreen.js:30` | Error text stored in state stays in the old language after a language switch until the next reload | Store error keys rather than strings, or add `language` to the deps |
| 20 | **Low** | Listener cleanup | `src/components/Tour.js:54-59`: the timer is set inside the `AsyncStorage.getItem().then` | If Tour unmounts before getItem resolves, cleanup has already run and the tour opens anyway | Use a `cancelled` flag. All other listeners checked are cleaned up (see below) |
| 21 | **Low** | Re-mounts | eslint `no-unstable-nested-components`: `TabNavigator.js:186` (`tabBar={(props)=>…}`), `ProfileScreen.js:109,121` | Extra re-mounts and lost local state | Hoist the components |
| 22 | **Low** | Tooling | `npx eslint` crashes on the project's own config (eslint-plugin-prettier vs prettier 3.8) | Lint cannot run, so no lint gate | Bump `eslint-plugin-prettier` to v5 or drop the plugin |
| 23 | **Low** | Dependencies | `expo` 54.0.35 vs ~54.0.37 (expo-doctor). Unused deps: `expo-av` (deprecated in SDK 54), `expo-image-picker`, `expo-auth-session`, `expo-crypto`, `expo-secure-store` (finding 2), `react-native-paper`, `date-fns`, `dayjs`, `react-native-shimmer-placeholder` | Larger bundle and extra permissions (blocker 5) | `npx expo install --check`; remove the unused packages |
| 24 | **Low** | Push config | `app.json` notifications plugin `color: "#0052FF"` (off-brand) and no notification `icon`. Channel name `'Alerts'` is hard-coded English (`src/api/api.js:139`) | Android status-bar icon falls back to the launcher icon (white square on many devices) | Add a monochrome notification icon to the plugin config |
| 25 | **Low** | Session hygiene | `authStore.js:165-169`: the 401 handler clears state, but `axiosConfig.js:158` leaves `cached_user` in storage | Profile PII stays on the device after a forced sign-out | Also remove `cached_user` |
| 26 | Info | Network | `axiosConfig.js:70`, `sse.js:65` send `ngrok-skip-browser-warning` to production | Harmless | Remove after leaving ngrok |
| 27 | Info | Lists | Notifications (capped at 100 server-side, `investai-backend/app/routers/notifications.py:49`), Rules, Watchlist and Portfolio holdings render via `.map` in a ScrollView. StockBrowse pages with "show more". Chat, Home tips and AllTopMovers use FlatList | Fine at current data sizes | Switch to FlatList if a list can grow past about 100 rows |

---

## i18n

`qa/scripts/check_i18n.js` copies `src/i18n` to a temp dir and imports the merged tables, so app source is not touched. It then compares en/si/ta and scans `src/` for `t('…')`. It also picks up keys held in data (`labelKey:`, `*_KEYS` arrays) and checks `` t(`…${x}…`) `` template patterns against the English keys. Run it with `node qa/scripts/check_i18n.js [--json]`; it exits 1 if any used key is missing from English.

| Metric | Value |
|---|---|
| Keys, English (merged: translations.js + screens/auth, markets, account + features/onboarding, chat, tour) | **658** |
| Keys, Sinhala (merged: screens/si.js + features.si + inline si) | **658** |
| Keys, Tamil (merged: screens/ta.js + features.ta + inline ta) | **658** |
| Missing or empty in si / ta (falls back to English) | **0 / 0** |
| si / ta values identical to English (excluding neutral values: brand names, numbers, AI/ASPI/CSE) | **0 / 0** |
| si / ta values containing no Sinhala/Tamil script | **0 / 0** |
| si / ta keys not in English (dead) | **0 / 0** |
| Distinct keys referenced from `src/` | 421 |
| `t('key')` used in `src/` but missing from English | **0** |
| Dynamic `` t(`…`) `` patterns | 17, all matching English keys (persona ×3, plan_step ×9, assess_q/k, journey_react ×4, victory_risk ×3) |
| English keys never referenced literally | 237. This is an upper bound: most are reached through dynamic templates (`assess_*`, `plan_step_*`, `home_tip_${i}`) |

- **Backend contract:** persona ids, plan step ids and all 9 `prompt_*` keys in `investai-backend/app/services/plan.py:25-72` exist in all three languages.
- **Script limits:**
  - Coverage is exact for the keys the script checks.
  - Translation *quality*, mixed-language sentences and placeholder parity (`{n}`, `{symbol}`) are not validated.
- **Hard-coded user-visible English found outside t():**
  - Findings 15 and 16 (InitialsAvatar a11y label, `Rs./B/M/T`, en-GB month names).
  - Finding 7 (raw axios/backend error text).
  - The Android notification channel name.
  - Brand "InvestAI" (`SplashScreen.js:75`) and "ISIN" (`StockDetailScreen.js:316`) are acceptable.
  - Assessment option strings (`AssessmentScreen.js:28-43`) are API values that are displayed through `t()`, so they are fine.
  - Sector names come from the API in English and are shown untranslated (`PortfolioScreen.js:298`, Home chips).

## Accessibility summary

- **Touchables:** 49 found (all go through `TouchableTick`/`Pressable`).
  - After manual review, every interactive control has an accessible name, either an explicit label or text children. The icon-only `CircleButton` always passes `accessibilityLabel`.
  - 8 have no role (finding 12).
- **Touch targets:** `sizes.touch = 44` is used consistently (`chipHit`, `minHeight: 44` on links, `CircleButton` adds hitSlop below 44). The one exception is the Splash language chips, at about 34pt (finding 10).
- **Contrast (WCAG 2.x, computed):**
  - ink/white 18.9
  - muted/white 7.88
  - muted/mint 6.13
  - faint/white 4.98
  - faint on gradient 3.87–4.29 (**fail** for small text)
  - faint on lavender/lime/coral cards 3.18 / 3.60 / 2.51 (not currently used as text there)
  - accent ink on accent 7.7–11.1 (pass)
  - white on ink 18.9
  - white on badge 2.78 (**fail**)
  - error on white 6.54
  - dark palette 5.7–7.9 (pass, though the app is locked to light mode in `app.json`)
  - Non-text: the `outline` border colour is 1.48:1 against white (below the 3:1 UI-component guideline). It is decorative on icon circles.
- **Font scaling:** never disabled (good). Fixed-height containers risk clipping (finding 14).
- **Screen-reader order and focus:**
  - The Tour traps focus correctly (`accessibilityViewIsModal`, hides the tab content, Android back closes it).
  - Decorative confetti and pill art are hidden.
  - Gaps: tab labels are read twice (finding 13), streamed chat answers are not announced (finding 9), and the price chart (`StockDetailScreen.js:379`) has no text summary beyond its date caption.
- **Reduced motion:** respected globally (`src/theme/motion.js:16-19`, `TouchableTick`).

## Robustness notes (checked, no issue)

- **Listener cleanup is correct** for:
  - expo-notifications response and push-token subscriptions (`App.js:63,75,78`)
  - BackHandler (`Tour.js:94-95`)
  - the OTP interval (`OTPVerificationScreen.js:26-30`)
  - the CountUp Animated listener (`VictoryScreen.js:50-53`)
  - the ActionFeedbackModal timer
  - SSE abort on unmount (`ChatScreen.js:161`)
  - The module-level reduce-motion listener (`motion.js:18`) is app-lifetime by design.
- **Push registration:**
  - Uses single-flight and dedupes tokens (`api.js:118-171`), which avoids the earlier permission-prompt loop.
  - A cold-start notification tap is queued until `MainTab` exists (`App.js:49-79`).
- **Navigation:**
  - All 18 `navigate()` targets exist in the stack they are called from, or are tab names.
  - Auth success and first-run assessment use `reset()`, so back cannot return to OTP or the quiz.
  - Profile and Assessment hide back when `!canGoBack()`.
  - There is no deep-link `linking` config, so the only entry point is a push tap.
- **Logging:** no tokens or personal data are logged. API URL and status logs are guarded by `__DEV__`. The remaining `console.warn` calls print only `err.message`.
- **Offline behaviour:**
  - Session restore keeps the token and opens from `cached_user` when there is no response or a 5xx (`authStore.js:101-112`).
  - Screens show `EmptyState` with retry.
  - There is no global offline banner or NetInfo; each screen handles errors itself (see finding 7 for the wording).
- **401 handling:**
  - One shared refresh, with a `_retried` guard against loops.
  - Public auth paths are excluded.
  - On final failure the tokens are wiped and the navigator drops to the auth stack (see finding 4 for the over-eager case).
- **Config checked:**
  - `app.json`: package/bundle `lk.investai.mobile`, `versionCode 1`, `buildNumber 1`, portrait, new architecture on.
  - EAS: `appVersionSource: local`, so versionCode must be bumped by hand for every Play upload.
  - Android targetSdk/compileSdk 36, minSdk 24 (RN 0.81 version catalog, used by the prebuild).
  - Icons and splash exist: `icon.png` 1024², `adaptive-icon.png` 1024², `splash-icon.png` 1024×820, `favicon.png` 48².
  - `google-services.json` exists locally and is git-ignored. It is wired through `app.config.js` or the EAS file variable `GOOGLE_SERVICES_JSON`. Its contents were not read.
  - `.env` also holds `EXPO_PUBLIC_SUPABASE_URL`/`_ANON_KEY`, which no source file references, so they are not inlined into the bundle.

## Not covered (needs a device)

- Real TalkBack/VoiceOver pass.
- 200% font-size layout.
- Push delivery end to end.
- Offline toggling.
- Android back on each tab.
- Performance and startup profiling.
- Visual check of the pastel text over imagery.
- Running Expo web through `.claude/launch.json` was possible but was not done in this pass.
