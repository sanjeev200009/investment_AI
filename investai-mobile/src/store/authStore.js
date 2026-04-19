import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi } from '../api/authApi';

export const useAuthStore = create((set) => ({
    user: null,
    token: null,
    riskProfile: null,
    isAuthenticated: false,
    isLoading: true,
    isEducationEnabled: false,
    hasCompletedAssessment: false,
    userAssessment: null,

    login: async (token, user) => {
        await AsyncStorage.setItem('token', token);
        const savedEdu = await AsyncStorage.getItem('education_enabled');
        const assessmentDone = await AsyncStorage.getItem('assessment_completed');
        set({ 
            token, 
            user, 
            isAuthenticated: true, 
            isLoading: false, 
            isEducationEnabled: savedEdu === 'true',
            hasCompletedAssessment: assessmentDone === 'true'
        });
    },

    logout: async () => {
        await AsyncStorage.removeItem('token');
        set({ token: null, user: null, isAuthenticated: false, isLoading: false });
    },

    // Called on app start to restore session
    restoreSession: async () => {
        set({ isLoading: true });
        const token = await AsyncStorage.getItem('token');
        const savedEdu = await AsyncStorage.getItem('education_enabled');
        if (token) {
            try {
                // Fetch fresh user data from backend
                const user = await authApi.getMe();
                const assessmentDone = await AsyncStorage.getItem('assessment_completed');
                set({ 
                    token, 
                    user, 
                    isAuthenticated: true, 
                    isLoading: false, 
                    isEducationEnabled: savedEdu === 'true',
                    hasCompletedAssessment: assessmentDone === 'true'
                });
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

    setEducationEnabled: async (enabled) => {
        await AsyncStorage.setItem('education_enabled', enabled.toString());
        set({ isEducationEnabled: enabled });
    },

    setAssessmentCompleted: async (completed) => {
        await AsyncStorage.setItem('assessment_completed', completed.toString());
        set({ hasCompletedAssessment: completed });
    },
    setAssessmentResults: async (results) => {
        await AsyncStorage.setItem('assessment_completed', 'true');
        await AsyncStorage.setItem('user_assessment', JSON.stringify(results));
        set({ userAssessment: results, hasCompletedAssessment: true });
    },
}));
