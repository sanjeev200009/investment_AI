// src/api/axiosConfig.js
import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const api = axios.create({
    baseURL: process.env.EXPO_PUBLIC_API_BASE_URL,
    timeout: 15000,
    headers: { 'Content-Type': 'application/json' },
});

// Attach JWT to every request automatically
api.interceptors.request.use(config => {
    const token = useAuthStore.getState().token;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
        console.log(`[API Request] ${config.method.toUpperCase()} ${config.url} - Token Present`);
    } else {
        console.log(`[API Request] ${config.method.toUpperCase()} ${config.url} - NO TOKEN`);
    }
    return config;
});

// Handle 401 globally — log user out without any screen knowing
api.interceptors.response.use(
    res => {
        console.log(`[API Response] ${res.config.method.toUpperCase()} ${res.config.url} - OK (${res.status})`);
        return res;
    },
    err => {
        const status = err.response?.status;
        const msg = err.response?.data?.detail || err.message;
        console.warn(`[API Error] ${err.config?.method?.toUpperCase()} ${err.config?.url} - Status ${status}: ${msg}`);
        
        if (status === 401) {
            console.log('[Auth] Token expired or invalid, logging out...');
            useAuthStore.getState().logout();
        }
        return Promise.reject(err);
    }
);

export default api;
