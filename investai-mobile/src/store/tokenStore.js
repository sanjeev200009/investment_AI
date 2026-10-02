// src/store/tokenStore.js
//
// The access and refresh tokens live in the OS keystore (expo-secure-store),
// not AsyncStorage: AsyncStorage is plain text, included in Android backups
// and readable on a rooted phone (QA, Oct 2026). The web build has no
// keystore, so it keeps AsyncStorage there.
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

const SECURE = Platform.OS !== 'web';
const KEYS = ['token', 'refresh_token'];

const get = async (key) => {
    if (!SECURE) return AsyncStorage.getItem(key);
    const value = await SecureStore.getItemAsync(key);
    if (value != null) return value;
    // One-time move for installs from before this change, so an update does
    // not sign everyone out.
    const legacy = await AsyncStorage.getItem(key);
    if (legacy) {
        await SecureStore.setItemAsync(key, legacy);
        await AsyncStorage.removeItem(key);
    }
    return legacy;
};

const set = (key, value) => (SECURE ? SecureStore.setItemAsync(key, value) : AsyncStorage.setItem(key, value));

const clear = async () => {
    await AsyncStorage.multiRemove(KEYS);
    if (SECURE) await Promise.all(KEYS.map((k) => SecureStore.deleteItemAsync(k)));
};

export const tokenStore = { get, set, clear };
