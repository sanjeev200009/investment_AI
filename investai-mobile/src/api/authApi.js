// src/api/authApi.js
import axios from 'axios';

// Base URL from environment variables or default
const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || 'https://api.investai.example.com';

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 10000,
});

/**
 * Authentication API matching the production-ready modular structure.
 */
export const authApi = {
    login: async (email, password) => {
        try {
            // const response = await apiClient.post('/auth/login', { email, password });
            // return response.data;

            // Simulate API call for development
            await new Promise(resolve => setTimeout(resolve, 1500));
            return { success: true, token: 'mock-jwt-token', user: { email, name: 'User' } };
        } catch (error) {
            throw error.response?.data?.message || 'Login failed';
        }
    },

    register: async (userData) => {
        try {
            // const response = await apiClient.post('/auth/register', userData);
            // return response.data;

            await new Promise(resolve => setTimeout(resolve, 1500));
            return { success: true, message: 'Registration successful' };
        } catch (error) {
            throw error.response?.data?.message || 'Registration failed';
        }
    },

    sendResetOTP: async (email) => {
        try {
            // const response = await apiClient.post('/auth/forgot-password', { email });
            // return response.data;

            await new Promise(resolve => setTimeout(resolve, 1500));
            return { success: true, message: 'OTP sent to your email' };
        } catch (error) {
            throw error.response?.data?.message || 'Failed to send OTP';
        }
    },

    verifyOTP: async (email, otp) => {
        try {
            // const response = await apiClient.post('/auth/verify-otp', { email, otp });
            // return response.data;

            await new Promise(resolve => setTimeout(resolve, 1000));
            return { success: true, token: 'mock-reset-token' };
        } catch (error) {
            throw error.response?.data?.message || 'Invalid OTP';
        }
    },

    resetPassword: async (token, newPassword) => {
        try {
            // const response = await apiClient.post('/auth/reset-password', { token, newPassword });
            // return response.data;

            await new Promise(resolve => setTimeout(resolve, 1500));
            return { success: true, message: 'Password reset successful' };
        } catch (error) {
            throw error.response?.data?.message || 'Password reset failed';
        }
    }
};

export default authApi;
