// src/i18n/translations.js
// Strings for the surfaces a user meets before and during their first session:
// the auth flow and the five main tabs. Full-app coverage is a later milestone;
// this scope (auth + tabs) is the defensible one for FR-6 — every string here
// switches live, without an app restart.
//
// Sinhala (si) and Tamil (ta) translations of financial terminology should be
// reviewed by a reader of each language before submission — machine-translated
// financial terms are a credibility risk the project documentation itself
// flags. The English strings are canonical; the other two are drop-in
// replacements of matching intent, not word-for-word.

import authStrings from './screens/auth';
import marketsStrings from './screens/markets';
import accountStrings from './screens/account';
import siStrings from './screens/si';
import taStrings from './screens/ta';
import onboardingStrings from './features/onboarding';
import chatStrings from './features/chat';
import tourStrings from './features/tour';

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'si', label: 'සිංහල' },
  { code: 'ta', label: 'தமிழ்' },
];

const en = {
  // Tabs
  tab_home: 'Home',
  tab_markets: 'Discover',
  tab_portfolio: 'Portfolio',
  tab_alerts: 'Alerts',
  tab_ai: 'AI',

  // Common
  cancel: 'Cancel',
  save: 'Save',
  delete: 'Delete',
  retry: 'Retry',
  loading: 'Loading…',
  error_generic: 'Something went wrong. Please try again.',

  // Auth
  login_title: 'Welcome back',
  login_subtitle: 'Sign in to continue investing smarter',
  login_email: 'Email',
  login_password: 'Password',
  login_forgot: 'Forgot password?',
  login_button: 'Sign In',
  login_no_account: "Don't have an account?",
  login_register: 'Register',
  register_title: 'Create account',
  register_name: 'Full name',
  otp_verify_title: 'Verify email',
  otp_verify_subtitle: 'Enter the 6-digit code we emailed you',
  otp_verify_button: 'Verify',
  otp_resend: 'Resend code',

  // Home
  home_greeting: 'Good morning',
  home_brief: "Here's your market brief for today.",

  // Markets / watchlist
  watchlist_title: 'Watchlist',
  watchlist_empty: 'Your watchlist is empty. Star a stock to follow it here.',
  watchlist_add: 'Add symbol',
  watchlist_add_hint: 'e.g. HNB.N0000 or COMB',

  // Portfolio
  portfolio_title: 'Portfolio',

  // Alerts
  alerts_title: 'Alerts',
  alerts_empty: 'No notifications yet.',
  alerts_mark_all: 'Mark all read',
  rules_title: 'Investment rules',
  rules_empty: 'No rules yet. Create one to let the agent watch a stock for you.',
  rules_add: 'New rule',
  rules_symbol: 'Symbol',
  rules_condition: 'Condition',
  rules_threshold: 'Threshold',
  rules_create: 'Create rule',
  rule_price_above: 'Price rises above',
  rule_price_below: 'Price falls below',
  rule_change_pct_up: 'Gains more than (%)',
  rule_change_pct_down: 'Falls more than (%)',
  rule_volume_spike: 'Volume exceeds',

  // Learn
  learn_title: 'Learn',
};

const si = {
  tab_home: 'මුල් පිටුව',
  tab_markets: 'වෙළඳපොළ',
  tab_portfolio: 'කළඹ',
  tab_alerts: 'දැනුම්දීම්',
  tab_ai: 'AI',

  cancel: 'අවලංගු කරන්න',
  save: 'සුරකින්න',
  delete: 'මකන්න',
  retry: 'නැවත උත්සාහ කරන්න',
  loading: 'පූරණය වෙමින්…',
  error_generic: 'යම් දෝෂයක් සිදු විය. කරුණාකර නැවත උත්සාහ කරන්න.',

  login_title: 'සාදරයෙන් පිළිගනිමු',
  login_subtitle: 'වඩා නිවැරදිව ආයෝජනය කිරීමට පිවිසෙන්න',
  login_email: 'ඊමේල්',
  login_password: 'මුරපදය',
  login_forgot: 'මුරපදය අමතක වුණාද?',
  login_button: 'පිවිසෙන්න',
  login_no_account: 'ගිණුමක් නැත්තේද?',
  login_register: 'ලියාපදිංචි වන්න',
  register_title: 'ගිණුම සාදන්න',
  register_name: 'සම්පූර්ණ නම',
  otp_verify_title: 'ඊමේල් තහවුරු කරන්න',
  otp_verify_subtitle: 'අප එවූ ඉලක්කම් 6 ඇතුළත් කරන්න',
  otp_verify_button: 'තහවුරු කරන්න',
  otp_resend: 'කේතය නැවත එවන්න',

  home_greeting: 'සුබ උදෑසන',
  home_brief: 'අද ඔබේ වෙළඳපොළ සාරාංශය.',

  watchlist_title: 'නිරීක්ෂණ ලැයිස්තුව',
  watchlist_empty: 'ඔබේ නිරීක්ෂණ ලැයිස්තුව හිස්ය. කොටසක් මෙහි අනුගමනය කිරීමට එයට තරු ලකුණ යොදන්න.',
  watchlist_add: 'කොටසක් එක් කරන්න',
  watchlist_add_hint: 'උදා. HNB.N0000 හෝ COMB',

  portfolio_title: 'ආයෝජන කළඹ',

  alerts_title: 'දැනුම්දීම්',
  alerts_empty: 'තවම දැනුම්දීම් නැත.',
  alerts_mark_all: 'සියල්ල කියවූ ලෙස ලක් කරන්න',
  rules_title: 'ආයෝජන නීති',
  rules_empty: 'තවම නීති නැත. කොටසක් නිරීක්ෂණය කිරීමට නීතියක් සාදන්න.',
  rules_add: 'නව නීතියක්',
  rules_symbol: 'සංකේතය',
  rules_condition: 'කොන්දේසිය',
  rules_threshold: 'සීමාව',
  rules_create: 'නීතිය සාදන්න',
  rule_price_above: 'මිල මෙයට වඩා ඉහළ ගිය විට',
  rule_price_below: 'මිල මෙයට වඩා පහළ ගිය විට',
  rule_change_pct_up: 'මෙයට වඩා (%) ඉහළ ගිය විට',
  rule_change_pct_down: 'මෙයට වඩා (%) පහළ ගිය විට',
  rule_volume_spike: 'ගනුදෙනු පරිමාව මෙය ඉක්මවූ විට',

  learn_title: 'ඉගෙනීම',
};

const ta = {
  tab_home: 'முகப்பு',
  tab_markets: 'சந்தை',
  tab_portfolio: 'தொகுப்பு',
  tab_alerts: 'அறிவிப்புகள்',
  tab_ai: 'AI',

  cancel: 'ரத்து செய்',
  save: 'சேமி',
  delete: 'நீக்கு',
  retry: 'மீண்டும் முயற்சி செய்',
  loading: 'ஏற்றுகிறது…',
  error_generic: 'ஏதோ தவறு ஏற்பட்டது. மீண்டும் முயற்சி செய்க.',

  login_title: 'மீண்டும் வருக',
  login_subtitle: 'சிறப்பான முதலீட்டுக்கு உள்நுழையுங்கள்',
  login_email: 'மின்னஞ்சல்',
  login_password: 'கடவுச்சொல்',
  login_forgot: 'கடவுச்சொல் மறந்ததா?',
  login_button: 'உள்நுழை',
  login_no_account: 'கணக்கு இல்லையா?',
  login_register: 'பதிவு செய்யுங்கள்',
  register_title: 'கணக்கை உருவாக்கு',
  register_name: 'முழு பெயர்',
  otp_verify_title: 'மின்னஞ்சலை உறுதிப்படுத்து',
  otp_verify_subtitle: 'நாங்கள் அனுப்பிய 6 இலக்க குறியீட்டை உள்ளிடுங்கள்',
  otp_verify_button: 'உறுதிப்படுத்து',
  otp_resend: 'குறியீட்டை மீண்டும் அனுப்பு',

  home_greeting: 'காலை வணக்கம்',
  home_brief: 'இன்றைய சந்தை சுருக்கம்.',

  watchlist_title: 'கண்காணிப்புப் பட்டியல்',
  watchlist_empty: 'உங்கள் கண்காணிப்புப் பட்டியல் காலியாக உள்ளது. பங்கைப் பின்தொடர நட்சத்திரத்தைத் தட்டவும்.',
  watchlist_add: 'குறியீட்டைச் சேர்',
  watchlist_add_hint: 'எ.கா. HNB.N0000 அல்லது COMB',

  portfolio_title: 'முதலீட்டுத் தொகுப்பு',

  alerts_title: 'அறிவிப்புகள்',
  alerts_empty: 'இன்னும் அறிவிப்புகள் இல்லை.',
  alerts_mark_all: 'அனைத்தையும் படித்ததாக குறி',
  rules_title: 'முதலீட்டு விதிகள்',
  rules_empty: 'இன்னும் விதிகள் இல்லை. பங்கை கண்காணிக்க விதியை உருவாக்குங்கள்.',
  rules_add: 'புதிய விதி',
  rules_symbol: 'குறியீடு',
  rules_condition: 'நிபந்தனை',
  rules_threshold: 'வரம்பு',
  rules_create: 'விதியை உருவாக்கு',
  rule_price_above: 'விலை இதை விட உயரும்போது',
  rule_price_below: 'விலை இதை விட குறையும்போது',
  rule_change_pct_up: 'இதை விட (%) உயரும்போது',
  rule_change_pct_down: 'இதை விட (%) குறையும்போது',
  rule_volume_spike: 'வர்த்தக அளவு இதைத் தாண்டும்போது',

  learn_title: 'கற்க',
};

// Per-screen strings. The si/ta tables above win over screens/si.js and
// screens/ta.js; any key still missing falls back to English.
const FEATURES = [onboardingStrings, chatStrings, tourStrings];
Object.assign(en, authStrings, marketsStrings, accountStrings, ...FEATURES.map(f => f.en));
const siAll = { ...siStrings, ...Object.assign({}, ...FEATURES.map(f => f.si)), ...si };
const taAll = { ...taStrings, ...Object.assign({}, ...FEATURES.map(f => f.ta)), ...ta };

const TRANSLATIONS = { en, si: siAll, ta: taAll };

export const translate = (lang, key) => {
  const table = TRANSLATIONS[lang] || TRANSLATIONS.en;
  return table[key] ?? TRANSLATIONS.en[key] ?? key;
};
