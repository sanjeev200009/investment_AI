// src/store/authStore.js
import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';

export const useAuthStore = create((set) => ({
    user: null,
    token: null,
    riskProfile: null,
    isAuthenticated: false,

    login: async (token, user) => {
        await AsyncStorage.setItem('token', token);
        set({ token, user, isAuthenticated: true });
    },

    logout: async () => {
        await AsyncStorage.removeItem('token');
        set({ token: null, user: null, isAuthenticated: false });
    },

    // Called on app start to restore session
    restoreSession: async () => {
        const token = await AsyncStorage.getItem('token');
        if (token) set({ token, isAuthenticated: true });
    },

    updateProfile: (updates) => set(state => ({
        user: { ...state.user, ...updates }
    })),
}));
