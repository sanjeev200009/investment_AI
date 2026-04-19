import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi } from '../api/authApi';

export const useAuthStore = create((set) => ({
    user: null,
    token: null,
    riskProfile: null,
    isAuthenticated: false,
    isLoading: true, // Added to handle startup loading

    login: async (token, user) => {
        await AsyncStorage.setItem('token', token);
        set({ token, user, isAuthenticated: true, isLoading: false });
    },

    logout: async () => {
        await AsyncStorage.removeItem('token');
        set({ token: null, user: null, isAuthenticated: false, isLoading: false });
    },

    // Called on app start to restore session
    restoreSession: async () => {
        set({ isLoading: true });
        const token = await AsyncStorage.getItem('token');
        if (token) {
            try {
                // Fetch fresh user data from backend
                const user = await authApi.getMe();
                set({ token, user, isAuthenticated: true, isLoading: false });
            } catch (err) {
                console.log('Session restore failed:', err);
                await AsyncStorage.removeItem('token');
                set({ token: null, user: null, isAuthenticated: false, isLoading: false });
            }
        } else {
            set({ isLoading: false });
        }
    },

    updateProfile: (updates) => set(state => ({
        user: { ...state.user, ...updates }
    })),
}));
