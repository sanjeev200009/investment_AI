// src/screens/auth/ResetPasswordScreen.js — v2 "Soft pastel" new password.
import React, { useState } from 'react';
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform, Alert } from 'react-native';

import { Screen, Field, PillButton, Title, Body } from '../../components/ui';
import { PillPal } from '../../components/PillPals';
import TouchableTick from '../../components/TouchableTick';
import { palette, fonts } from '../../theme/tokens';
import { authApi } from '../../api/authApi';
import { validatePassword, validateConfirmPassword } from '../../utils/validation';
import { useT } from '../../store/languageStore';

const ResetPasswordScreen = ({ navigation, route }) => {
    const { t } = useT();
    // Both come from OTPVerificationScreen after /auth/verify-reset-otp. The
    // previous version sent the literal string 'mock-token' as the only
    // argument, so every reset failed with "Invalid or expired reset token".
    const { email, resetToken } = route.params || {};

    // Form State
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);

    const handleResetPassword = async () => {
        const passwordError = validatePassword(password);
        const confirmError = validateConfirmPassword(password, confirmPassword);

        if (passwordError || confirmError) {
            setErrors({ password: passwordError, confirmPassword: confirmError });
            return;
        }

        setErrors({});
        setLoading(true);

        try {
            if (!email || !resetToken) {
                // Only reachable if this screen is entered out of order.
                throw new Error(t('reset_session_expired'));
            }
            await authApi.resetPassword(email, resetToken, password);
            // reset(), not navigate(): the reset token is single-use, so going
            // "back" to this form could only fail.
            navigation.reset({
                index: 0,
                routes: [{
                    name: 'AuthSuccess',
                    params: {
                        title: t('reset_success_title'),
                        message: t('reset_success_msg'),
                        buttonLabel: t('authsuccess_back_login'),
                    },
                }],
            });
        } catch (err) {
            // err is an Error or an axios error — Alert needs a string, and the
            // previous `Alert.alert('Error', err)` rendered nothing useful.
            const msg = err?.response?.data?.detail
                || err?.message
                || t('reset_failed');
            Alert.alert(t('auth_error'), msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={styles.flex}
        >
            <Screen edges={['top', 'bottom']} contentStyle={styles.content}>
                <View style={styles.pal}><PillPal tone="lime" pose="wave" badge="lock-reset" size={170} /></View>
                <View style={styles.intro}>
                    <Title style={styles.title}>
                        {t('reset_title')}{'\n'}
                        <Text style={styles.titleLight}>{t('reset_slogan')}</Text>
                    </Title>
                    <Body style={styles.muted}>{t('reset_subtitle')}</Body>
                </View>

                <View style={styles.form}>
                    <Field
                        placeholder={t('reset_new_password')}
                        icon="lock-outline"
                        tone="lavender"
                        value={password}
                        onChangeText={setPassword}
                        error={errors.password}
                        secureTextEntry
                    />
                    <Field
                        placeholder={t('reset_confirm_password')}
                        icon="verified-user"
                        tone="lime"
                        value={confirmPassword}
                        onChangeText={setConfirmPassword}
                        error={errors.confirmPassword}
                        secureTextEntry
                    />
                    <PillButton
                        title={t('reset_save')}
                        knob="lime"
                        onPress={handleResetPassword}
                        loading={loading}
                        disabled={!password || !confirmPassword}
                        style={styles.cta}
                    />
                </View>

                <View style={styles.flex} />

                <TouchableTick
                    style={styles.footer}
                    onPress={() => navigation.navigate('Login')}
                    accessibilityRole="button"
                    accessibilityLabel={`${t('reset_remember')} ${t('register_login')}`}
                >
                    <Text style={styles.footerText}>
                        {t('reset_remember')} <Text style={styles.link}>{t('register_login')}</Text>
                    </Text>
                </TouchableTick>
            </Screen>
        </KeyboardAvoidingView>
    );
};

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
    flex: { flex: 1 },
    content: { flexGrow: 1, paddingTop: 32, paddingBottom: 24, gap: 32 },
    intro: { gap: 10 },
    pal: { alignItems: 'center', marginBottom: -12 },
    title: { fontSize: 40, lineHeight: 44, letterSpacing: -1.5 },
    titleLight: { fontFamily: fonts.light, color: palette.muted },
    muted: { color: palette.muted },
    form: { gap: 12 },
    cta: { marginTop: 8 },
    link: { ...text, fontFamily: fonts.medium, fontSize: 14 },
    footer: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    footerText: { ...text, fontSize: 14, color: palette.muted, textAlign: 'center' },
});

export default ResetPasswordScreen;
