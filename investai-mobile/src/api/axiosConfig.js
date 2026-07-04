// src/api/axiosConfig.js
import axios from 'axios';
// import { useAuthStore } from '../store/authStore'; // Removed to break circular dependency

const api = axios.create({
    baseURL: process.env.EXPO_PUBLIC_API_BASE_URL,
    timeout: 15000,
    headers: { 'Content-Type': 'application/json' },
});

// Auth logic removed

// Global response interceptor (error handling simplified, no auth)
api.interceptors.response.use(
    res => {
        console.log(`[API Response] ${res.config.method.toUpperCase()} ${res.config.url} - OK (${res.status})`);
        return res;
    },
    err => {
        const status = err.response?.status;
        const msg = err.response?.data?.detail || err.message;
        console.warn(`[API Error] ${err.config?.method?.toUpperCase()} ${err.config?.url} - Status ${status}: ${msg}`);
        return Promise.reject(err);
    }
);

export default api;
