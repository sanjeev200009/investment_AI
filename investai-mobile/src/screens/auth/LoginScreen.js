import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Dimensions,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StatusBar,
  Alert
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { MaterialIcons } from '@expo/vector-icons';
import Svg, { Path, Circle } from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withRepeat,
  withSequence,
  withDelay,
  Easing
} from 'react-native-reanimated';

// Design System & Modular Imports
import { useAppTheme } from '../../hooks/useAppTheme';
import AppButton from '../../components/AppButton';
import AppInput from '../../components/AppInput';
import AppCard from '../../components/AppCard';
import { authApi } from '../../api/authApi';
import { validateEmail, validatePassword } from '../../utils/validation';
import { useAuthStore } from '../../store/authStore';

const { width, height } = Dimensions.get('window');

const LoginScreen = ({ navigation }) => {
  const theme = useAppTheme();
  // Signing in means: get a Supabase access token from our own backend, then
  // hand it to the store. Clerk's signIn.create() is gone — the token it minted
  // was never verifiable by the API.
  const setSession = useAuthStore(state => state.login);

  // Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  // Animation values
  const formSlideUp = useSharedValue(height * 0.5);
  const formOpacity = useSharedValue(0);
  const logoFloat = useSharedValue(0);
  const heroOpacity = useSharedValue(0);

  useEffect(() => {
    heroOpacity.value = withTiming(1, { duration: 800 });
    formSlideUp.value = withDelay(300, withTiming(0, {
      duration: 1000,
      easing: Easing.bezier(0.25, 0.1, 0.25, 1)
    }));
    formOpacity.value = withDelay(300, withTiming(1, { duration: 800 }));

    logoFloat.value = withRepeat(
      withSequence(
        withTiming(-15, { duration: 2000, easing: Easing.inOut(Easing.sin) }),
        withTiming(0, { duration: 2000, easing: Easing.inOut(Easing.sin) })
      ),
      -1,
      true
    );
  }, []);

  const animatedHeroStyle = useAnimatedStyle(() => ({
    opacity: heroOpacity.value,
  }));

  const animatedLogoStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: logoFloat.value }],
  }));

  const animatedFormStyle = useAnimatedStyle(() => ({
    opacity: formOpacity.value,
    transform: [{ translateY: formSlideUp.value }],
  }));

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
          'Verify your email',
          detail || 'Your email is not verified yet. We have sent you a new code.',
          [{
            text: 'Enter code',
            onPress: () => navigation.navigate('OTPVerification',
              { email: email.trim(), type: 'register' }),
          }]
        );
        return;
      }

      const msg = detail
        || (status ? 'Invalid email or password' : 'Cannot reach the server. Check your connection.');
      Alert.alert('Login Failed', msg);
    } finally {
      setLoading(false);
    }
  };

  const isFormValid = email && password && !errors.email && !errors.password;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={[styles.container, { backgroundColor: theme.colors.background }]}
    >
      <StatusBar barStyle="light-content" translucent backgroundColor="transparent" />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        bounces={false}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero Section */}
        <Animated.View style={[styles.heroContainerWrapper, animatedHeroStyle]}>
          <LinearGradient
            colors={theme.colors.gradient}
            style={styles.heroContainer}
          >
            <View style={styles.statusBarSpacer} />

            <Animated.View style={[styles.logoWrapper, animatedLogoStyle]}>
              <View style={[
                styles.logoCard,
                {
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  borderColor: 'rgba(255, 255, 255, 0.2)',
                  borderRadius: theme.radii.xxl,
                }
              ]}>
                <Svg width="80" height="80" viewBox="0 0 100 100">
                  <Path d="M10 80 L30 60 L50 70 L90 20 L90 80 Z" fill="white" opacity="0.4" />
                  <Path d="M10 80 L30 50 L50 65 L90 10" fill="none" stroke="white" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
                  <Circle cx="90" cy="10" fill="white" r="4" />
                </Svg>
              </View>
              <Text style={[styles.brandName, { fontSize: theme.typography.sizes.h1 }]}>InvestAI</Text>
              <Text style={styles.brandSlogan}>Smarter Wealth Growth</Text>
            </Animated.View>
          </LinearGradient>
        </Animated.View>

        {/* Login Form Container */}
        <Animated.View style={[animatedFormStyle]}>
          <AppCard style={styles.formContainer}>
            <View style={styles.formHeader}>
              <Text style={[styles.welcomeText, { color: theme.colors.textPrimary, fontSize: theme.typography.sizes.h3 }]}>Welcome Back</Text>
              <Text style={[styles.subText, { color: theme.colors.textSecondary }]}>Login to your investment dashboard</Text>
            </View>

            <View style={styles.inputGroup}>
              <AppInput
                placeholder="Email Address"
                value={email}
                onChangeText={setEmail}
                error={errors.email}
                icon={<MaterialIcons name="alternate-email" size={20} color={theme.colors.textSecondary} />}
                keyboardType="email-address"
                autoCapitalize="none"
              />

              <AppInput
                placeholder="Password"
                value={password}
                onChangeText={setPassword}
                error={errors.password}
                icon={<MaterialIcons name="lock" size={20} color={theme.colors.textSecondary} />}
                secureTextEntry
              />

              <TouchableOpacity
                style={styles.forgotPassword}
                onPress={() => navigation.navigate('ForgotPassword')}
              >
                <Text style={[styles.forgotPasswordText, { color: theme.colors.primary }]}>Forgot Password?</Text>
              </TouchableOpacity>

              <AppButton
                title="Sign In"
                onPress={handleLogin}
                loading={loading}
                disabled={!email || !password}
                style={styles.signInButton}
              />
              {/* "Sign in with Google" was a Clerk OAuth flow and went with
                  Clerk. Supabase can do Google OAuth, but it needs a Google
                  Cloud OAuth client plus deep-link config, and no FR calls for
                  it — FR-1 is email/password with OTP verification. Left out
                  deliberately rather than left in place and broken. */}
            </View>

            <View style={styles.footer}>
              <Text style={[styles.footerText, { color: theme.colors.textSecondary }]}>
                New here?{' '}
                <Text style={[styles.registerLink, { color: theme.colors.primary }]} onPress={() => navigation.navigate('Register')}>
                  Register
                </Text>
              </Text>
            </View>
          </AppCard>
        </Animated.View>
      </ScrollView>

      {/* Bottom Indicator */}
      <View style={[styles.bottomIndicatorContainer, { backgroundColor: theme.colors.surface }]}>
        <View style={[styles.bottomIndicator, { backgroundColor: theme.colors.divider }]} />
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  heroContainerWrapper: { width: '100%' },
  heroContainer: { height: height * 0.45, justifyContent: 'center', alignItems: 'center', paddingBottom: 40 },
  statusBarSpacer: { height: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight },
  topBar: { width: '100%', flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 32, position: 'absolute', top: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight || 20, zIndex: 20 },
  spacer: { width: 40 },
  statusBarIcons: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logoWrapper: { alignItems: 'center' },
  logoCard: { padding: 24, borderWidth: 1, marginBottom: 20 },
  brandName: { color: 'white', fontWeight: '800', letterSpacing: -0.5, marginBottom: 4 },
  brandSlogan: { fontSize: 18, marginTop: 4, color: 'rgba(224, 242, 254, 0.8)' },
  formContainer: { marginTop: -48, borderTopLeftRadius: 48, borderTopRightRadius: 48, paddingHorizontal: 32, paddingTop: 48, paddingBottom: 40, flex: 1 },
  formHeader: { marginBottom: 32 },
  welcomeText: { fontWeight: '700', marginBottom: 8 },
  subText: { fontSize: 15 },
  inputGroup: { gap: 16 },
  forgotPassword: { alignSelf: 'flex-end', marginTop: 4 },
  forgotPasswordText: { fontSize: 14, fontWeight: '600' },
  signInButton: { marginTop: 16 },
  dividerContainer: { flexDirection: 'row', alignItems: 'center', marginVertical: 12 },
  divider: { flex: 1, height: 1 },
  dividerText: { marginHorizontal: 16, color: '#9CA3AF', fontSize: 14 },
  footer: { marginTop: 32, marginBottom: 20, alignItems: 'center' },
  footerText: { fontSize: 16 },
  registerLink: { fontWeight: '700' },
  bottomIndicatorContainer: { alignItems: 'center', paddingBottom: 12 },
  bottomIndicator: { width: 128, height: 6, borderRadius: 3 }
});

export default LoginScreen;
