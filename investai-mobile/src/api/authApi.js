// src/api/authApi.js
import api from './axiosConfig';

export const authApi = {
  register: async ({ email, password, full_name }) => {
    const { data } = await api.post('/auth/register', { email, password, full_name });
    return data;
  },
  verifyOTP: async (email, otp_code) => {
    const { data } = await api.post('/auth/verify-otp', { email, otp_code });
    return data;
  },
  resendOTP: async (email) => {
    const { data } = await api.post('/auth/resend-otp', { email });
    return data;
  },
  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password });
    return data;
  },
  forgotPassword: async (email) => {
    const { data } = await api.post('/auth/forgot-password', { email });
    return data;
  },
  verifyResetOTP: async (email, otp_code) => {
    const { data } = await api.post('/auth/verify-reset-otp', { email, otp_code });
    return data; // returns { reset_token: '...' }
  },
  resetPassword: async (email, reset_token, new_password) => {
    const { data } = await api.post('/auth/reset-password', { email, reset_token, new_password });
    return data;
  },
  getMe: async () => {
    const { data } = await api.get('/auth/me');
    return data;
  },
};
