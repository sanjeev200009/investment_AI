// src/api/axiosConfig.js
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const api = axios.create({
    // The fallback matches what the screens used to hardcode individually, so
    // routing every call through this instance loses nothing when the env var
    // is unset.
    baseURL: process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1',
    timeout: 60000, // Increased to 60 seconds for AI endpoints
    headers: { 'Content-Type': 'application/json' },
});

// The request interceptor was previously deleted with the note "Removed to break
// circular dependency" — axiosConfig imported authStore, which imports authApi,
// which imports axiosConfig. Removing it meant NO request ever carried an
// Authorization header, so every authenticated call 401'd. authStore.getMe()
// failed silently on app start and updateRiskProfile() was swallowed by a
// console.warn, which is why risk profiles never reached the database.
//
// The fix is to read the token straight from AsyncStorage instead of from the
// store. AsyncStorage is the source of truth anyway (authStore.login writes it
// before setting state), so there is no cycle and no ordering hazard.
let onUnauthorized = null;

/** Registered by authStore so a 401 can clear the session without an import cycle. */
export const setUnauthorizedHandler = (handler) => {
    onUnauthorized = handler;
};

// Endpoints where a 401 is an expected answer (bad password, unverified email)
// rather than an expired session. Wiping state on these would be wrong.
// /auth/refresh is included so a failed refresh cannot recurse into itself.
const PUBLIC_PATHS = [
    '/auth/login', '/auth/register', '/auth/verify-otp', '/auth/resend-otp',
    '/auth/forgot-password', '/auth/verify-reset-otp', '/auth/reset-password',
    '/auth/refresh',
];

const isPublic = (url = '') => PUBLIC_PATHS.some(p => url.includes(p));

api.interceptors.request.use(
    async (config) => {
        const token = await AsyncStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        // Sent once here rather than per-call in each screen.
        config.headers['ngrok-skip-browser-warning'] = 'true';
        return config;
    },
    err => Promise.reject(err)
);

// Supabase access tokens last about an hour and the backend now enforces `exp`.
// Clerk's SDK used to refresh transparently on every getToken() call, so without
// this the cutover would have degraded into a forced sign-out mid-session.
//
// A single shared promise means N concurrent 401s (a screen firing three
// requests at once) trigger one refresh, not three — Supabase rotates the
// refresh token on use, so parallel attempts would invalidate each other.
let refreshInFlight = null;

const refreshAccessToken = async () => {
    const refreshToken = await AsyncStorage.getItem('refresh_token');
    if (!refreshToken) return null;

    // A bare axios call, not `api`: going through this instance would attach the
    // dead Authorization header and re-enter these interceptors.
    const { data } = await axios.post(
        `${api.defaults.baseURL}/auth/refresh`,
        { refresh_token: refreshToken },
        { headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' } }
    );
    await AsyncStorage.setItem('token', data.access_token);
    if (data.refresh_token) {
        await AsyncStorage.setItem('refresh_token', data.refresh_token);
    }
    return data.access_token;
};

api.interceptors.response.use(
    res => {
        console.log(`[API Response] ${res.config.method.toUpperCase()} ${res.config.url} - OK (${res.status})`);
        return res;
    },
    async err => {
        const status = err.response?.status;
        const msg = err.response?.data?.detail || err.message;
        const url = err.config?.url || '';
        console.warn(`[API Error] ${err.config?.method?.toUpperCase()} ${url} - Status ${status}: ${msg}`);

        const config = err.config;

        // Try exactly one silent refresh before giving up on the session.
        // `_retried` guards against a refreshed token that is itself rejected,
        // which would otherwise loop.
        if (status === 401 && !isPublic(url) && config && !config._retried) {
            config._retried = true;
            try {
                if (!refreshInFlight) {
                    refreshInFlight = refreshAccessToken().finally(() => {
                        refreshInFlight = null;
                    });
                }
                const newToken = await refreshInFlight;
                if (newToken) {
                    config.headers = { ...config.headers, Authorization: `Bearer ${newToken}` };
                    return api.request(config);
                }
            } catch (refreshErr) {
                console.warn('[API] Token refresh failed:', refreshErr?.message || refreshErr);
            }
        }

        // Refresh was impossible or itself rejected: the session really is over.
        // Clear it so the navigator drops back to the auth flow instead of
        // looping on 401s.
        if (status === 401 && !isPublic(url)) {
            await AsyncStorage.multiRemove(['token', 'refresh_token']);
            if (onUnauthorized) {
                onUnauthorized();
            }
        }
        return Promise.reject(err);
    }
);

export default api;
