// src/store/languageStore.js
// UI + AI output language. The preference has three homes, deliberately:
//
//   1. AsyncStorage — instant, offline, drives this session's UI immediately.
//   2. The zustand store — so screens re-render on change without a restart
//      (FR-6 requires switchable-without-restart).
//   3. user_profiles.language on the backend (POST /me/language) — what the
//      agent reads to decide which language to answer in. The risk quiz
//      already writes this column via /me/risk-profile; this is the settings
//      toggle writing the same column rather than a second preference.
//
// The backend call is best-effort: offline it degrades to a UI-only switch and
// reconciles on the next successful call.
import { tokenStore } from './tokenStore';
import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { deviceApi } from '../api/api';
import { translate } from '../i18n/translations';

const KEY = 'app_language';
// How much the user knows about investing; picks plain or expert wording.
// Device-only: it changes words on screen, nothing the server needs.
const LEVEL_KEY = 'app_word_level';
const LEVELS = ['beginner', 'intermediate', 'expert'];
// Codes supported end to end: the translations file, /me/language, and the
// agent's language steering (app/services/agent/memory.py) must agree.
const SUPPORTED = ['en', 'si', 'ta'];

export const useLanguageStore = create((set) => ({
    language: 'en',
    level: 'beginner',
    ready: false,

    setLevel: async (level) => {
        if (!LEVELS.includes(level)) return;
        set({ level });
        try { await AsyncStorage.setItem(LEVEL_KEY, level); } catch { /* best-effort */ }
    },

    // syncToServer: after sign-in, push a language picked on the splash
    // (before there was an account to save it to) up to /me/language.
    init: async (syncToServer = false) => {
        try {
            const level = await AsyncStorage.getItem(LEVEL_KEY);
            if (LEVELS.includes(level)) set({ level });
        } catch { /* default stays beginner */ }
        try {
            const saved = await AsyncStorage.getItem(KEY);
            if (SUPPORTED.includes(saved)) {
                set({ language: saved, ready: true });
                if (syncToServer) deviceApi.setLanguage(saved).catch(() => {});
            } else set({ ready: true });
        } catch {
            set({ ready: true });
        }
    },

    setLanguage: async (code) => {
        if (!SUPPORTED.includes(code)) return;
        // Optimistic: the switch must feel instant (FR-6). A failed backend
        // call leaves the UI switch in place — it is still what the user asked
        // for on this device — and the AI-output language follows on the next
        // successful save.
        set({ language: code });
        try {
            await AsyncStorage.setItem(KEY, code);
        } catch { /* persistence is best-effort; the session still switches */ }
        try {
            // Signed out (splash picker): nothing to save to yet; init(true)
            // sends it after sign-in.
            if (await tokenStore.get('token')) await deviceApi.setLanguage(code);
        } catch (err) {
            console.warn('[i18n] Could not persist language to server:', err?.message || err);
        }
    },
}));

// Convenience hook: `const { t } = useT()` returns a translator bound to the
// current language, so screens render `t('alerts_title')` and re-render
// automatically when the language changes.
export const useT = () => {
    const language = useLanguageStore(state => state.language);
    const level = useLanguageStore(state => state.level);
    return { t: (key) => translate(language, key, level), language, level };
};
