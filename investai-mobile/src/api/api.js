// src/api/api.js
// Typed wrappers for the endpoints this app calls. Auth headers, token refresh
// and the ngrok bypass all live in axiosConfig's request interceptor, so no
// screen needs to handle a token.
import { Platform } from 'react-native';
import api from './axiosConfig';

// ── Watchlist (I-09) ─────────────────────────────────────────────────────────
export const watchlistApi = {
  list: async () => {
    const { data } = await api.get('/watchlist');
    return data;
  },
  add: async (symbol) => {
    const { data } = await api.post('/watchlist', { symbol });
    return data;
  },
  remove: async (symbol) => {
    await api.delete(`/watchlist/${encodeURIComponent(symbol)}`);
  },
};

// ── Learn (proposal 6.5) ─────────────────────────────────────────────────────
export const learnApi = {
  list: async () => {
    const { data } = await api.get('/learn/lessons');
    return data;
  },
  get: async (id) => {
    const { data } = await api.get(`/learn/lessons/${encodeURIComponent(id)}`);
    return data;
  },
};

// ── Personal plan ────────────────────────────────────────────────────────────
// GET /me/plan: persona, next steps, lesson order and chat starters. Resolves
// to null when the endpoint is unavailable, so callers simply hide plan UI.
export const planApi = {
  get: async () => {
    try {
      const { data } = await api.get('/me/plan');
      return data && Array.isArray(data.steps) ? data : null;
    } catch (_) {
      return null;
    }
  },
};

// ── Investment rules (I-10) ──────────────────────────────────────────────────
export const rulesApi = {
  list: async () => {
    const { data } = await api.get('/rules');
    return data;
  },
  create: async (symbol, condition_type, threshold) => {
    const { data } = await api.post('/rules', { symbol, condition_type, threshold });
    return data;
  },
  update: async (ruleId, patch) => {
    const { data } = await api.patch(`/rules/${ruleId}`, patch);
    return data;
  },
  remove: async (ruleId) => {
    await api.delete(`/rules/${ruleId}`);
  },
};

// ── Notifications (I-11) ─────────────────────────────────────────────────────
export const notificationsApi = {
  list: async () => {
    const { data } = await api.get('/notifications/');
    return data;
  },
  markRead: async (notifId) => {
    const { data } = await api.patch(`/notifications/${notifId}/read`);
    return data;
  },
  markAllRead: async () => {
    const { data } = await api.post('/notifications/read-all');
    return data;
  },
  remove: async (notifId) => {
    await api.delete(`/notifications/${notifId}`);
  },
};

// ── Recommendations (I-13) ───────────────────────────────────────────────────
export const recommendationsApi = {
  top: async (limit = 5) => {
    const { data } = await api.get('/recommendations', { params: { limit } });
    return data;
  },
};

// ── Device token + language (I-12 / I-15) ────────────────────────────────────
export const deviceApi = {
  registerToken: async (device_token) => {
    const { data } = await api.post('/me/device-token', { device_token });
    return data;
  },
  setLanguage: async (language) => {
    const { data } = await api.post('/me/language', { language });
    return data;
  },
};

// ── Push registration (I-12) ─────────────────────────────────────────────────
// expo-notifications obtains the FCM registration token on Android. Until this
// ran after sign-in, no token ever left the device: the backend's whole push
// path was complete and permanently starved (I-12's third broken layer).
//
// expo-notifications is lazy-required: the module touches native code that is
// absent from the web bundle, and a top-level import would crash `expo start
// --web` even though nothing here runs there.
let lastSentToken = null;
let registering = null;

export const pushApi = {
  // Single-flight: sign-in, app launch and token rotation can all ask at once.
  register: () => {
    if (!registering) {
      registering = pushApi._register().finally(() => { registering = null; });
    }
    return registering;
  },
  _register: async () => {
    try {
      const Notifications = require('expo-notifications');
      // Without a handler, a push that lands while the app is open is dropped.
      Notifications.setNotificationHandler({
        handleNotification: async () => ({
          shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false,
        }),
      });
      // Android 13+ shows no permission prompt until a channel exists; this is
      // also the channel app.json names as FCM's default for background pushes.
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'Alerts',
          importance: Notifications.AndroidImportance.HIGH,
        });
      }
      // Android 13+ and iOS both require an explicit grant before a token is
      // useful. Ask only when not yet granted and the OS still allows asking:
      // every request opens the system permission activity, even when it is
      // already granted, which pauses and resumes the app.
      let { status, canAskAgain } = await Notifications.getPermissionsAsync();
      if (status !== 'granted' && canAskAgain) {
        ({ status } = await Notifications.requestPermissionsAsync());
      }
      if (status !== 'granted') return;
      const token = await Notifications.getDevicePushTokenAsync();
      await pushApi.sendToken(token?.data);
    } catch (err) {
      // Expected on the iOS simulator and in Expo Go on iOS (FCM v1 push needs
      // a dev/EAS build there). Never blocks sign-in.
      if (__DEV__) console.warn('[Push] token registration skipped:', err?.message || err);
    }
  },
  // Send a token to the backend once. getDevicePushTokenAsync() itself fires
  // the push-token listener, and that listener used to call register() again:
  // an endless request-permission loop that flipped the app in and out of the
  // system permission screen (202 times in two minutes on an Android 16 phone).
  sendToken: async (token) => {
    if (!token || token === lastSentToken) return;
    lastSentToken = token;
    try {
      await deviceApi.registerToken(token);
    } catch (err) {
      lastSentToken = null; // retry on the next launch or rotation
      throw err;
    }
  },
  unregister: async () => {
    lastSentToken = null; // the next account to sign in registers this device again
    try {
      await api.delete('/me/device-token');
    } catch (_) { /* best effort on logout */ }
  },
};
