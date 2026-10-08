// src/screens/auth/RegisterScreen.js — v2 "Soft pastel" create account.
import React, { useState } from 'react';
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform, Alert } from 'react-native';

import { Screen, Field, PillButton, Title, Body } from '../../components/ui';
import { RegisterHero } from '../../components/PillPals';
import TouchableTick from '../../components/TouchableTick';
import { palette, fonts } from '../../theme/tokens';
import { authApi } from '../../api/authApi';
import { validateEmail, validateNewPassword, validateFullName, validateConfirmPassword } from '../../utils/validation';
import { useT } from '../../store/languageStore';

const RegisterScreen = ({ navigation }) => {
  const { t } = useT();

  // Form State
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    const nameError = validateFullName(name);
    const emailError = validateEmail(email);
    const passwordError = validateNewPassword(password);
    const confirmError = validateConfirmPassword(password, confirmPassword);

    if (nameError || emailError || passwordError || confirmError) {
      setErrors({ name: nameError, email: emailError, password: passwordError, confirmPassword: confirmError });
      return;
    }

    setErrors({});
    setLoading(true);

    try {
      // POST /auth/register creates the Supabase user, writes the local `users`
      // row, and emails a 6-digit OTP via Brevo. It returns no token — the
      // account is unusable until /auth/verify-otp flips is_email_verified.
      await authApi.register({
        email: email.trim(),
        password,
        full_name: name.trim(),
      });

      navigation.navigate('OTPVerification', { email: email.trim(), type: 'register', password });
    } catch (error) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail;

      // "already registered and verified" is not an error worth a dead end.
      if (status === 400 && typeof detail === 'string' && detail.includes('already registered')) {
        Alert.alert(t('register_already_title'), detail, [
          { text: t('register_go_login'), onPress: () => navigation.navigate('Login') },
          { text: t('cancel'), style: 'cancel' },
        ]);
        return;
      }

      const msg = detail
        || (status ? t('register_failed') : t('auth_network_error'));
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
        <RegisterHero label={t('register_hero_alt')} />

        <View style={styles.intro}>
          <Title style={styles.title}>
            {t('register_title')}{'\n'}
            <Text style={styles.titleLight}>{t('register_slogan')}</Text>
          </Title>
          <Body style={styles.muted}>{t('register_subtitle')}</Body>
        </View>

        <View style={styles.form}>
          <Field
            placeholder={t('register_name')}
            value={name}
            onChangeText={setName}
            error={errors.name}
            autoCapitalize="words"
            icon="person-outline"
            tone="coral"
          />
          <Field
            placeholder={t('login_email')}
            value={email}
            onChangeText={setEmail}
            error={errors.email}
            keyboardType="email-address"
            autoCapitalize="none"
            icon="mail-outline"
            tone="yellow"
          />
          <Field
            placeholder={t('login_password')}
            value={password}
            onChangeText={setPassword}
            error={errors.password}
            secureTextEntry
            icon="lock-outline"
            tone="lavender"
          />
          <Field
            placeholder={t('register_confirm_password')}
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            error={errors.confirmPassword}
            secureTextEntry
            icon="verified-user"
            tone="lime"
          />
          <PillButton
            title={t('register_button')}
            onPress={handleRegister}
            loading={loading}
            disabled={!name || !email || !password || !confirmPassword}
            style={styles.cta}
            knob="coral"
          />
          {/* Google sign-up removed with Clerk — see the note in
              LoginScreen.js. FR-1 is email/password + OTP. */}
        </View>

        <View style={styles.legal}>
          <Text style={styles.small}>{t('register_agree')}</Text>
          <View style={styles.legalRow}>
            <TouchableTick style={styles.legalLink} accessibilityRole="link" onPress={() => navigation.navigate('Legal', { doc: 'terms' })}>
              <Text style={styles.linkSmall}>{t('register_terms')}</Text>
            </TouchableTick>
            <Text style={styles.small}>{t('register_and')}</Text>
            <TouchableTick style={styles.legalLink} accessibilityRole="link" onPress={() => navigation.navigate('Legal', { doc: 'privacy' })}>
              <Text style={styles.linkSmall}>{t('register_privacy')}</Text>
            </TouchableTick>
          </View>
          <Text style={styles.small}>{t('register_disclaimer')}</Text>
        </View>

        <TouchableTick
          style={styles.footer}
          onPress={() => navigation.navigate('Login')}
          accessibilityRole="button"
          accessibilityLabel={`${t('register_have_account')} ${t('register_login')}`}
        >
          <Text style={styles.footerText}>
            {t('register_have_account')}{' '}
            <Text style={styles.link}>{t('register_login')}</Text>
          </Text>
        </TouchableTick>
      </Screen>
    </KeyboardAvoidingView>
  );
};

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { flexGrow: 1, paddingTop: 12, paddingBottom: 24, gap: 20 },
  intro: { gap: 8 },
  title: { fontSize: 34, lineHeight: 38, letterSpacing: -1 },
  titleLight: { fontFamily: fonts.light, color: palette.muted },
  muted: { color: palette.muted },
  form: { gap: 12 },
  cta: { marginTop: 8 },
  legal: { alignItems: 'center', gap: 2 },
  legalRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' },
  legalLink: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 6 },
  small: { ...text, fontSize: 13, color: palette.muted, textAlign: 'center' },
  linkSmall: { ...text, fontFamily: fonts.medium, fontSize: 13, textDecorationLine: 'underline' },
  link: { ...text, fontFamily: fonts.medium, fontSize: 14 },
  footer: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  footerText: { ...text, fontSize: 14, color: palette.muted, textAlign: 'center' },
});

export default RegisterScreen;
