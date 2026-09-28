// src/api/authApi.js
import api from './axiosConfig';

export const authApi = {
  register: async ({ email, password, full_name }) => {
    const { data } = await api.post('/auth/register', { email, password, full_name });
    return data;
  },
  // The password is set on the account here, not at registration, so only the
  // person holding the emailed code can choose it.
  verifyOTP: async (email, otp_code, password) => {
    const { data } = await api.post('/auth/verify-otp', { email, otp_code, password });
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
  logout: async () => {
    await api.post('/auth/logout');
  },
  getMe: async () => {
    const { data } = await api.get('/auth/me');
    return data;
  },
  updateProfile: async (full_name) => {
    const { data } = await api.patch('/me', { full_name });
    return data;
  },
  // `answers` is keyed by question id, e.g. { "1": "Retirement", "11": 60 }.
  // The backend scores it against app/services/risk_scoring.py and rejects any
  // option it does not recognise with a 422 naming the question.
  updateRiskProfile: async (answers) => {
    const { data } = await api.post('/me/risk-profile', { answers });
    return data;
  },
  getAssessmentQuestions: async () => {
    const { data } = await api.get('/me/assessment/questions');
    return data;
  },
};
