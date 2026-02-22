// src/api/authApi.js
import api from './axiosConfig';

export const loginUser = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    return res.data;  // { access_token, user }
};

export const registerUser = async (data) => {
    const res = await api.post('/auth/register', data);
    return res.data;
};

export const submitAssessment = async (answers) => {
    const res = await api.post('/auth/onboarding', { answers });
    return res.data;  // { risk_profile }
};
