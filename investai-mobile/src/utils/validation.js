// src/utils/validation.js

/**
 * Validates an email address.
 */
export const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email) return 'Email is required';
    if (!emailRegex.test(email)) return 'Please enter a valid email address';
    return null;
};

/**
 * Validates password strength.
 */
export const validatePassword = (password) => {
    if (!password) return 'Password is required';
    if (password.length < 8) return 'Password must be at least 8 characters';
    return null;
};

/**
 * Validates that two passwords match.
 */
export const validateConfirmPassword = (password, confirmPassword) => {
    if (!confirmPassword) return 'Please confirm your password';
    if (password !== confirmPassword) return 'Passwords do not match';
    return null;
};

/**
 * Validates full name.
 */
export const validateFullName = (name) => {
    if (!name) return 'Full name is required';
    if (name.trim().length < 2) return 'Please enter your full name';
    return null;
};

/**
 * Validates OTP code.
 */
export const validateOTP = (otp) => {
    if (!otp) return 'OTP is required';
    if (otp.length !== 4 && otp.length !== 6) return 'Invalid OTP length';
    return null;
};
