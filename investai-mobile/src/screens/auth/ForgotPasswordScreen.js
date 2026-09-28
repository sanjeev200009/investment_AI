// src/screens/auth/ForgotPasswordScreen.js — v2 "Soft pastel" reset request.
import React, { useState } from 'react';
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform, Alert } from 'react-native';

import { Screen, Header, Field, PillButton, Title, Body } from '../../components/ui';
import { PillPal } from '../../components/PillPals';
import TouchableTick from '../../components/TouchableTick';
import { palette, fonts } from '../../theme/tokens';
import { authApi } from '../../api/authApi';
import { validateEmail } from '../../utils/validation';
import { useT } from '../../store/languageStore';

const ForgotPasswordScreen = ({ navigation }) => {
    const { t } = useT();

    // Form State
    const [email, setEmail] = useState('');
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSendLink = async () => {
        const emailError = validateEmail(email);
        if (emailError) {
            setError(emailError);
            return;
        }

        setError(null);
        setLoading(true);

        try {
            // authApi exposes this as forgotPassword; the old call was to a
            // non-existent `sendResetOTP`, so this threw "not a function" and
            // the reset flow could never even start.
            await authApi.forgotPassword(email.trim());
            // Linear Flow: Forgot -> OTP -> Reset -> Success
            navigation.navigate('OTPVerification', { email: email.trim(), type: 'reset' });
        } catch (err) {
            const msg = err?.response?.data?.detail
                || err?.message
                || t('forgot_send_failed');
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
                <Header onBack={() => navigation.goBack()} backLabel={t('auth_back')} />
                <View style={styles.pal}><PillPal tone="coral" mood="oops" badge="question-mark" size={170} /></View>

                <View style={styles.intro}>
                    <Title style={styles.title}>
                        {t('forgot_title')}{'\n'}
                        <Text style={styles.titleLight}>{t('forgot_slogan')}</Text>
                    </Title>
                    <Body style={styles.muted}>{t('forgot_subtitle')}</Body>
                </View>

                <View style={styles.form}>
                    <Field
                        placeholder={t('login_email')}
                        icon="mail-outline"
                        tone="yellow"
                        value={email}
                        onChangeText={setEmail}
                        error={error}
                        keyboardType="email-address"
                        autoCapitalize="none"
                    />
                    <PillButton
                        title={t('forgot_send_code')}
                        knob="coral"
                        onPress={handleSendLink}
                        loading={loading}
                        disabled={!email}
                    />
                </View>

                <View style={styles.flex} />

                <TouchableTick
                    style={styles.footer}
                    onPress={() => navigation.navigate('Login')}
                    accessibilityRole="button"
                    accessibilityLabel={`${t('forgot_back_to')} ${t('register_login')}`}
                >
                    <Text style={styles.footerText}>
                        {t('forgot_back_to')} <Text style={styles.link}>{t('register_login')}</Text>
                    </Text>
                </TouchableTick>
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
    title: { fontSize: 40, lineHeight: 44, letterSpacing: -1.5 },
    titleLight: { fontFamily: fonts.light, color: palette.muted },
    muted: { color: palette.muted },
    form: { gap: 16 },
    link: { ...text, fontFamily: fonts.medium, fontSize: 14 },
    footer: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    footerText: { ...text, fontSize: 14, color: palette.muted, textAlign: 'center' },
});

export default ForgotPasswordScreen;
