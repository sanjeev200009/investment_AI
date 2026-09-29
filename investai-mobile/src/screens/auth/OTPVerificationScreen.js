// src/screens/auth/OTPVerificationScreen.js — v2 "Soft pastel" code entry.
import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TextInput, KeyboardAvoidingView, Platform, Alert } from 'react-native';

import { Screen, Header, PillButton, Title, Body } from '../../components/ui';
import { PillPal } from '../../components/PillPals';
import TouchableTick from '../../components/TouchableTick';
import { palette, fonts, radii } from '../../theme/tokens';
import { authApi } from '../../api/authApi';
import { useT } from '../../store/languageStore';

const OTPVerificationScreen = ({ navigation, route }) => {
    const { t } = useT();
    // `password` travels with the navigation (memory only, never stored):
    // the backend sets it on the account at verification, so whoever holds
    // the emailed code chooses the password, not whoever registered first.
    const { email, type, password } = route.params || {};

    // Backend uses 6 digits
    const [otp, setOtp] = useState(['', '', '', '', '', '']);
    const [timer, setTimer] = useState(59);
    const [loading, setLoading] = useState(false);
    const inputs = useRef([]);

    useEffect(() => {
        const interval = setInterval(() => {
            setTimer((prev) => (prev > 0 ? prev - 1 : 0));
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const handleOtpChange = (value, index) => {
        const newOtp = [...otp];
        newOtp[index] = value;
        setOtp(newOtp);

        // Auto-focus next input
        if (value && index < 5) {
            inputs.current[index + 1].focus();
        }
    };

    const handleVerify = async () => {
        const fullOtp = otp.join('');
        if (fullOtp.length < 6) {
            Alert.alert(t('auth_error'), t('otp_incomplete'));
            return;
        }

        setLoading(true);
        try {
            if (type === 'reset') {
                const response = await authApi.verifyResetOTP(email, fullOtp);
                navigation.navigate('ResetPassword', {
                    email,
                    resetToken: response.reset_token
                });
            } else {
                // Marks is_email_verified locally. No token comes back, so the
                // user logs in next — /auth/login is what mints the Supabase
                // access token the API verifies.
                if (!password) {
                    Alert.alert(t('otp_signin_again_title'), t('otp_signin_again_msg'));
                    return;
                }
                await authApi.verifyOTP(email, fullOtp, password);
                navigation.reset({
                    index: 0,
                    routes: [{
                        name: 'AuthSuccess',
                        params: {
                            title: t('otp_verified_title'),
                            message: t('otp_verified_msg'),
                            buttonLabel: t('otp_continue_login'),
                        },
                    }],
                });
            }
        } catch (error) {
            const msg = error?.response?.data?.detail
                || (error?.response ? t('otp_failed')
                    : t('auth_network_error'));
            Alert.alert(t('otp_error_title'), msg);
        } finally {
            setLoading(false);
        }
    };

    const handleResend = async () => {
        try {
            // Both flows resend through our own backend now; Clerk's
            // prepareEmailAddressVerification is gone.
            if (type === 'reset') {
                await authApi.forgotPassword(email);
            } else {
                await authApi.resendOTP(email);
            }
            setTimer(59);
            Alert.alert(t('otp_sent_title'), t('otp_sent_msg'));
        } catch (error) {
            const msg = error?.response?.data?.detail
                || t('otp_resend_failed');
            Alert.alert(t('auth_error'), msg);
        }
    };

    return (
        <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={styles.flex}
        >
            <Screen edges={['top', 'bottom']} contentStyle={styles.content}>
                <Header onBack={() => navigation.goBack()} backLabel={t('auth_back')} />
                <View style={styles.pal}><PillPal tone="yellow" pose="wave" badge="mark-email-read" size={170} /></View>

                <View style={styles.intro}>
                    <Title style={styles.title}>{t('otp_title')}</Title>
                    <Body style={styles.muted}>
                        {t('otp_sent_to')}{'\n'}
                        <Text style={styles.email}>{email}</Text>
                    </Body>
                </View>

                <View style={styles.cells}>
                    {otp.map((digit, index) => (
                        <TextInput
                            key={index}
                            ref={(ref) => (inputs.current[index] = ref)}
                            style={[styles.cell, digit ? styles.cellFilled : null]}
                            accessibilityLabel={t('otp_digit_label').replace('{n}', index + 1)}
                            maxLength={1}
                            keyboardType="number-pad"
                            value={digit}
                            onChangeText={(value) => handleOtpChange(value, index)}
                            onKeyPress={({ nativeEvent }) => {
                                if (nativeEvent.key === 'Backspace' && !digit && index > 0) {
                                    inputs.current[index - 1].focus();
                                }
                            }}
                        />
                    ))}
                </View>

                <View style={styles.timerRow}>
                    <Text style={styles.timerText}>
                        {timer > 0 ? t('otp_resend_in').replace('{time}', `00:${timer.toString().padStart(2, '0')}`) : t('otp_not_received')}
                    </Text>
                    {timer === 0 && (
                        <TouchableTick style={styles.resend} onPress={handleResend} accessibilityRole="button">
                            <Text style={styles.resendText}>{t('otp_resend_now')}</Text>
                        </TouchableTick>
                    )}
                </View>

                <View style={styles.flex} />

                <PillButton
                    title={t('otp_verify_proceed')}
                    knob="yellow"
                    onPress={handleVerify}
                    loading={loading}
                    disabled={otp.some(d => !d) || loading}
                />
            </Screen>
        </KeyboardAvoidingView>
    );
};

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
    flex: { flex: 1 },
    content: { flexGrow: 1, paddingBottom: 24, gap: 32 },
    intro: { gap: 10 },
    pal: { alignItems: 'center', marginVertical: -12 },
    title: { fontSize: 42, lineHeight: 44, letterSpacing: -1.5 },
    muted: { color: palette.muted },
    email: { fontFamily: fonts.medium, color: palette.ink },
    cells: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
    cell: {
        flex: 1, maxWidth: 52, height: 64, borderRadius: radii.full,
        backgroundColor: 'rgba(255,255,255,0.92)', borderWidth: 1.5, borderColor: 'transparent',
        textAlign: 'center', fontSize: 24, fontFamily: fonts.medium, color: palette.ink,
    },
    cellFilled: { borderColor: palette.ink },
    timerRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap', gap: 4, minHeight: 44 },
    timerText: { ...text, fontSize: 15, color: palette.muted },
    resend: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 12, borderRadius: radii.full, backgroundColor: '#FFFFFF' },
    resendText: { ...text, fontFamily: fonts.medium, fontSize: 15 },
});

export default OTPVerificationScreen;
