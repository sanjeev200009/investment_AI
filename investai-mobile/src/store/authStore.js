// src/store/authStore.js
//
// The single source of truth for who is signed in. Before the I-02 cutover the
// app had two: Clerk (which minted the tokens the screens actually sent) and
// this store (which held the backend's own user row). They disagreed, and the
// backend accepted Clerk tokens only because it never verified any signature.
// Clerk is gone; the token here is a Supabase access token from /auth/login,
// which app/dependencies.py verifies properly.
import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi } from '../api/authApi';
import { setUnauthorizedHandler } from '../api/axiosConfig';
import { pushApi } from '../api/api';
import { useLanguageStore } from './languageStore';

// Keys this store no longer writes; removed on sign-out so old installs shed them.
const LEGACY_KEYS = ['education_enabled', 'assessment_completed', 'user_assessment'];

const clearLocalSession = async (set) => {
    await AsyncStorage.multiRemove(['token', 'refresh_token', 'cached_user', ...LEGACY_KEYS]);
    set({ token: null, user: null, isAuthenticated: false, isLoading: false });
};

export const useAuthStore = create((set) => ({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true,
    hasCompletedProfileSetup: false,

    login: async (token, user, refreshToken) => {
        await AsyncStorage.setItem('token', token);
        // Kept so axiosConfig can renew the access token silently; Supabase
        // access tokens expire in about an hour.
        if (refreshToken) {
            await AsyncStorage.setItem('refresh_token', refreshToken);
        }
        // Cached so the app can open signed-in while offline.
        await AsyncStorage.setItem('cached_user', JSON.stringify(user));
        set({
            token,
            user,
            isAuthenticated: true,
            isLoading: false,
        });
        // Register this device for push (I-12), best-effort — sign-in never
        // blocks on it. Also loads the saved UI language immediately.
        useLanguageStore.getState().init(true);
        pushApi.register();
    },

    logout: async () => {
        // Server side first, while the token is still valid: stop pushes to this
        // device and revoke the refresh token. Both are best effort; the local
        // sign-out below happens regardless.
        await Promise.allSettled([pushApi.unregister(), authApi.logout()]);
        await clearLocalSession(set);
    },

    /** DELETE /me, then the local half of sign-out. Throws if the server
     * refused, so the caller can say so; nothing local is cleared then. There
     * is no session left to revoke or device token to unregister afterwards. */
    deleteAccount: async () => {
        await authApi.deleteAccount();
        await clearLocalSession(set);
    },

    // Called on app start to restore session
    restoreSession: async () => {
        set({ isLoading: true });
        const token = await AsyncStorage.getItem('token');
        if (token) {
            try {
                // Set token in state FIRST so axios interceptor can see it
                set({ token });

                // Fetch fresh user data from backend
                const user = await authApi.getMe();
                // Re-read: if the access token had expired, axiosConfig's
                // interceptor silently refreshed it during getMe(), and the
                // value read above is now stale.
                const currentToken = (await AsyncStorage.getItem('token')) || token;
                await AsyncStorage.setItem('cached_user', JSON.stringify(user));
                set({
                    token: currentToken,
                    user,
                    isAuthenticated: true,
                    isLoading: false,
                });
                // FCM rotates tokens; re-send on every launch, not only at login.
                useLanguageStore.getState().init(true);
                pushApi.register();
            } catch (err) {
                // A 503 means the backend or its database is down, not that the
                // session is invalid — dropping the token there would sign the
                // user out over a transient outage and lose a working session.
                //
                // The same goes for no response at all (offline, server asleep):
                // that used to fall through to the branch below and delete the
                // tokens, so opening the app on the bus signed the user out.
                const status = err?.response?.status;
                if (!status || (status !== 401 && status !== 403)) {
                    console.warn(`Session restore deferred (${status ? `HTTP ${status}` : 'no response'}); keeping token.`);
                    const cached = await AsyncStorage.getItem('cached_user');
                    let user = null;
                    try { user = cached ? JSON.parse(cached) : null; } catch (_) { user = null; }
                    // With a cached profile, open signed-in; screens show their
                    // own offline/error states and recover on the next request.
                    set(user
                        ? { user, isAuthenticated: true, isLoading: false }
                        : { isLoading: false });
                    return;
                }
                console.log('Session restore failed:', err?.message || err);
                await AsyncStorage.multiRemove(['token', 'refresh_token']);
                set({ token: null, user: null, isAuthenticated: false, isLoading: false });
            }
        } else {
            set({ isLoading: false });
        }
    },

    updateProfile: (updates) => set(state => ({
        user: { ...state.user, ...updates }
    })),

    /**
     * Persist the risk assessment. Throws if the backend rejected it.
     *
     * This used to `console.warn` and carry on, so the local flags said the
     * assessment was done while the server had no risk_profile row — the agent
     * then had no risk tolerance to reason with (FR-2) and nobody could see why.
     * The caller is responsible for telling the user; local state is only
     * written once the server has accepted the results.
     *
     * Returns the scored profile ({ score, category, ... }) so the caller can
     * show it. The server is the only copy; nothing is cached locally.
     */
    setAssessmentResults: async (results) => {
        const profile = await authApi.updateRiskProfile(results);
        // Q14 already set user_profiles.language server-side; switch the UI to
        // match, or the next launch's init(true) would push the old code back.
        const code = { english: 'en', sinhala: 'si', tamil: 'ta' }[String(profile?.preferred_language || '').toLowerCase()];
        if (code) useLanguageStore.getState().setLanguage(code);
        return profile;
    },

    checkProfileSetup: async (userId) => {
        if (!userId) return;
        const done = await AsyncStorage.getItem(`profile_setup_done_${userId}`);
        set({ hasCompletedProfileSetup: done === 'true' });
    },

    setProfileSetupDone: async (userId) => {
        if (!userId) return;
        await AsyncStorage.setItem(`profile_setup_done_${userId}`, 'true');
        set({ hasCompletedProfileSetup: true });
    },
}));

// Let a rejected token end the session. Registered here rather than inside
// axiosConfig so that module stays free of any store import (axiosConfig ->
// authStore -> authApi -> axiosConfig would be a cycle). Without this the
// navigator kept rendering the signed-in stack while every request 401'd.
setUnauthorizedHandler(() => {
    useAuthStore.setState({
        token: null, user: null, isAuthenticated: false, isLoading: false,
    });
});
