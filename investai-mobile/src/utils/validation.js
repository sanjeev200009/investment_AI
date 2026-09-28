// src/utils/validation.js
//
// Messages are translated here, in the one place every form calls, using the
// language currently selected (read from the store, since these are plain
// functions rather than components).
import { translate } from '../i18n/translations';
import { useLanguageStore } from '../store/languageStore';

const msg = (key) => translate(useLanguageStore.getState().language, key);

/**
 * Validates an email address.
 */
export const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email) return msg('val_email_required');
    if (!emailRegex.test(email)) return msg('val_email_invalid');
    return null;
};

/**
 * Validates password strength.
 */
export const validatePassword = (password) => {
    if (!password) return msg('val_password_required');
    if (password.length < 8) return msg('val_password_short');
    return null;
};

/**
 * Validates that two passwords match.
 */
export const validateConfirmPassword = (password, confirmPassword) => {
    if (!confirmPassword) return msg('val_confirm_required');
    if (password !== confirmPassword) return msg('val_password_mismatch');
    return null;
};

/**
 * Validates full name.
 */
export const validateFullName = (name) => {
    if (!name) return msg('val_name_required');
    if (name.trim().length < 2) return msg('val_name_short');
    return null;
};

/**
 * Validates OTP code. The backend issues 6-digit codes.
 */
export const validateOTP = (otp) => {
    if (!otp) return msg('val_otp_required');
    if (otp.length !== 6) return msg('val_otp_length');
    return null;
};
