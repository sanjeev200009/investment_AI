// src/screens/auth/LoginScreen.js — v2 "Soft pastel" sign in.
import React, { useState } from 'react';
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform, Alert } from 'react-native';

import { Screen, Field, PillButton, Title, Body, accent, ACCENT_CYCLE } from '../../components/ui';
import TouchableTick from '../../components/TouchableTick';
import { palette, fonts, radii } from '../../theme/tokens';
import { authApi } from '../../api/authApi';
import { validateEmail, validatePassword } from '../../utils/validation';
import { useAuthStore } from '../../store/authStore';
import { useT } from '../../store/languageStore';

// Decorative pastel pills from the sign-in mockup (staggered heights).
const DECO_OFFSETS = [0, 30, 10, 44];

const LoginScreen = ({ navigation }) => {
  const { t } = useT();
  // Signing in means: get a Supabase access token from our own backend, then
  // hand it to the store. Clerk's signIn.create() is gone — the token it minted
  // was never verifiable by the API.
  const setSession = useAuthStore(state => state.login);

  // Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    const emailError = validateEmail(email);
    const passwordError = validatePassword(password);

    if (emailError || passwordError) {
      setErrors({ email: emailError, password: passwordError });
      return;
    }

    setErrors({});
    setLoading(true);

    try {
      const data = await authApi.login(email.trim(), password);
      // TokenResponse (routers/auth.py) already carries everything the store
      // needs, so there is no follow-up /auth/me round trip on the login path.
      await setSession(data.access_token, {
        user_id: data.user_id,
        email: data.email,
        full_name: data.full_name,
      }, data.refresh_token);
      // No navigation call: AppNavigator swaps to the signed-in stack as soon
      // as isAuthenticated flips.
    } catch (error) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail;

      // 403 is specifically "registered but OTP never entered" — send them to
      // finish verifying instead of showing a dead end.
      if (status === 403) {
        try {
          await authApi.resendOTP(email.trim());
        } catch (_) {
          // Non-fatal: they can still use "Resend" on the OTP screen.
        }
        Alert.alert(
          t('login_verify_title'),
          detail || t('login_verify_msg'),
          [{
            text: t('login_enter_code'),
            onPress: () => navigation.navigate('OTPVerification',
              { email: email.trim(), type: 'register', password }),
          }]
        );
        return;
      }

      const msg = detail
        || (status ? t('login_invalid') : t('auth_network_error'));
      Alert.alert(t('login_failed'), msg);
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
        <View style={styles.deco} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
          {ACCENT_CYCLE.map((tone, i) => (
            <View key={tone} style={[styles.decoPill, { backgroundColor: accent(tone).bg, marginTop: DECO_OFFSETS[i] }]} />
          ))}
        </View>

        <View style={styles.intro}>
          <Title style={styles.title}>{t('login_title')}</Title>
          <Body style={styles.muted}>{t('login_subtitle')}</Body>
        </View>

        <View style={styles.form}>
          <Field
            placeholder={t('login_email')}
            value={email}
            onChangeText={setEmail}
            error={errors.email}
            keyboardType="email-address"
            autoCapitalize="none"
          />
          <Field
            placeholder={t('login_password')}
            value={password}
            onChangeText={setPassword}
            error={errors.password}
            secureTextEntry
          />
          <TouchableTick
            style={styles.forgot}
            onPress={() => navigation.navigate('ForgotPassword')}
            accessibilityRole="button"
          >
            <Text style={styles.link}>{t('login_forgot')}</Text>
          </TouchableTick>
          <PillButton
            title={t('login_button')}
            onPress={handleLogin}
            loading={loading}
            disabled={!email || !password}
          />
          {/* "Sign in with Google" was a Clerk OAuth flow and went with
              Clerk. Supabase can do Google OAuth, but it needs a Google
              Cloud OAuth client plus deep-link config, and no FR calls for
              it — FR-1 is email/password with OTP verification. Left out
              deliberately rather than left in place and broken. */}
        </View>

        <View style={styles.flex} />

        <TouchableTick
          style={styles.footer}
          onPress={() => navigation.navigate('Register')}
          accessibilityRole="button"
          accessibilityLabel={`${t('login_no_account')} ${t('login_register')}`}
        >
          <Text style={styles.footerText}>
            {t('login_no_account')}{' '}
            <Text style={styles.link}>{t('login_register')}</Text>
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
  deco: { flexDirection: 'row', gap: 10 },
  decoPill: { width: 64, height: 150, borderRadius: radii.full },
  intro: { gap: 8 },
  title: { fontSize: 42, lineHeight: 44, letterSpacing: -1.5 },
  muted: { color: palette.muted },
  form: { gap: 12 },
  forgot: { alignSelf: 'flex-end', minHeight: 44, justifyContent: 'center', paddingHorizontal: 8 },
  link: { ...text, fontFamily: fonts.medium, fontSize: 14 },
  footer: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  footerText: { ...text, fontSize: 14, color: palette.muted, textAlign: 'center' },
});

export default LoginScreen;
