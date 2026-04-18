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
import { validateEmail, validatePassword, validateFullName, validateConfirmPassword } from '../../utils/validation';

const { width, height } = Dimensions.get('window');

const RegisterScreen = ({ navigation }) => {
  const theme = useAppTheme();

  // Form State
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
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

  const handleRegister = async () => {
    const nameError = validateFullName(name);
    const emailError = validateEmail(email);
    const passwordError = validatePassword(password);
    const confirmError = validateConfirmPassword(password, confirmPassword);

    if (nameError || emailError || passwordError || confirmError) {
      setErrors({ name: nameError, email: emailError, password: passwordError, confirmPassword: confirmError });
      return;
    }

    setErrors({});
    setLoading(true);

    try {
      await authApi.register({ email, password, full_name: name });
      // Navigate to OTP screen, passing the email
      navigation.navigate('OTPVerify', { email });
    } catch (error) {
      const msg = error?.response?.data?.detail || 'Registration failed';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

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
        <Animated.View style={[styles.heroContainerWrapper, animatedHeroStyle]}>
          <LinearGradient colors={theme.colors.gradient} style={styles.heroContainer}>
            <View style={styles.statusBarSpacer} />
            <View style={styles.topBar}>
              <View style={styles.spacer} />
              <View style={styles.statusBarIcons}>
                <MaterialIcons name="signal-cellular-alt" size={18} color="white" />
                <MaterialIcons name="wifi" size={18} color="white" />
                <MaterialIcons name="battery-full" size={18} color="white" />
              </View>
            </View>

            <Animated.View style={[styles.logoWrapper, animatedLogoStyle]}>
              <View style={[styles.logoCard, { backgroundColor: 'rgba(255, 255, 255, 0.1)', borderColor: 'rgba(255, 255, 255, 0.2)', borderRadius: theme.radii.xxl }]}>
                <Svg width="80" height="80" viewBox="0 0 100 100">
                  <Path d="M10 80 L30 60 L50 70 L90 20 L90 80 Z" fill="white" opacity="0.4" />
                  <Path d="M10 80 L30 50 L50 65 L90 10" fill="none" stroke="white" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
                  <Circle cx="90" cy="10" fill="white" r="4" />
                </Svg>
              </View>
              <Text style={[styles.brandName, { fontSize: theme.typography.sizes.h1 }]}>InvestAI</Text>
              <Text style={styles.brandSlogan}>Join the Future of Investing</Text>
            </Animated.View>
          </LinearGradient>
        </Animated.View>

        <Animated.View style={[animatedFormStyle]}>
          <AppCard style={styles.formContainer}>
            <View style={styles.formHeader}>
              <Text style={[styles.welcomeText, { color: theme.colors.textPrimary, fontSize: theme.typography.sizes.h3 }]}>Create Account</Text>
              <Text style={[styles.subText, { color: theme.colors.textSecondary }]}>Start your journey with InvestAI today</Text>
            </View>

            <View style={styles.inputGroup}>
              <AppInput
                placeholder="Full Name"
                value={name}
                onChangeText={setName}
                error={errors.name}
                icon={<MaterialIcons name="person-outline" size={20} color={theme.colors.textSecondary} />}
                autoCapitalize="words"
              />

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
                icon={<MaterialIcons name="lock-outline" size={20} color={theme.colors.textSecondary} />}
                secureTextEntry
              />

              <AppInput
                placeholder="Confirm Password"
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                error={errors.confirmPassword}
                icon={<MaterialIcons name="lock-reset" size={20} color={theme.colors.textSecondary} />}
                secureTextEntry
              />

              <AppButton
                title="Create Account"
                onPress={handleRegister}
                loading={loading}
                disabled={!name || !email || !password || !confirmPassword}
                style={styles.signInButton}
              />

              <View style={styles.dividerContainer}>
                <View style={[styles.divider, { backgroundColor: theme.colors.divider }]} />
                <Text style={styles.dividerText}>Or sign up with</Text>
                <View style={[styles.divider, { backgroundColor: theme.colors.divider }]} />
              </View>

              <AppButton
                variant="secondary"
                title="Sign up with Google"
                onPress={() => { }}
                icon={
                  <Svg width="20" height="20" viewBox="0 0 24 24">
                    <Path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                    <Path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                    <Path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                    <Path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 12-4.53z" fill="#EA4335" />
                  </Svg>
                }
              />
            </View>

            <View style={styles.footer}>
              <Text style={[styles.footerText, { color: theme.colors.textSecondary }]}>
                Already have an account?{' '}
                <Text style={[styles.registerLink, { color: theme.colors.primary }]} onPress={() => navigation.navigate('Login')}>
                  Login
                </Text>
              </Text>
            </View>
          </AppCard>
        </Animated.View>
      </ScrollView>

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
  heroContainer: { height: height * 0.4, justifyContent: 'center', alignItems: 'center', paddingBottom: 40 },
  statusBarSpacer: { height: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight },
  topBar: { width: '100%', flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 32, position: 'absolute', top: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight || 20, zIndex: 20 },
  spacer: { width: 40 },
  statusBarIcons: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logoWrapper: { alignItems: 'center' },
  logoCard: { padding: 20, borderWidth: 1, marginBottom: 16 },
  brandName: { color: 'white', fontWeight: '800', letterSpacing: -0.5 },
  brandSlogan: { fontSize: 16, marginTop: 4, color: 'rgba(224, 242, 254, 0.8)' },
  formContainer: { marginTop: -48, borderTopLeftRadius: 48, borderTopRightRadius: 48, paddingHorizontal: 32, paddingTop: 48, paddingBottom: 40, flex: 1 },
  formHeader: { marginBottom: 28 },
  welcomeText: { fontWeight: '700', marginBottom: 8 },
  subText: { fontSize: 15 },
  inputGroup: { gap: 14 },
  signInButton: { marginTop: 24 },
  dividerContainer: { flexDirection: 'row', alignItems: 'center', marginVertical: 10 },
  divider: { flex: 1, height: 1 },
  dividerText: { marginHorizontal: 16, color: '#9CA3AF', fontSize: 13 },
  footer: { marginTop: 28, marginBottom: 20, alignItems: 'center' },
  footerText: { fontSize: 15 },
  registerLink: { fontWeight: '700' },
  bottomIndicatorContainer: { alignItems: 'center', paddingBottom: 12 },
  bottomIndicator: { width: 128, height: 6, borderRadius: 3 }
});

export default RegisterScreen;
