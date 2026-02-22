import React, { useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Dimensions,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StatusBar,
  useColorScheme
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

const { width, height } = Dimensions.get('window');

const LoginScreen = ({ navigation }) => {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';

  // Theme object for dynamic switching
  const theme = {
    background: isDark ? '#000000' : '#F3F4F6',
    formBg: isDark ? '#121212' : '#FFFFFF',
    inputBg: isDark ? '#1E1E1E' : '#F9FAFB',
    inputBorder: isDark ? 'transparent' : '#F3F4F6',
    textPrimary: isDark ? '#FFFFFF' : '#111827',
    textSecondary: isDark ? '#9CA3AF' : '#6B7280',
    primary: '#1976D2',
    divider: isDark ? '#1F2937' : '#E5E7EB',
    googleBtnBg: isDark ? '#1E1E1E' : '#FFFFFF',
    googleBtnBorder: isDark ? '#1F2937' : '#E5E7EB',
    googleText: isDark ? '#FFFFFF' : '#374151',
    heroGradient: isDark ? ['#0A192F', '#1976D2'] : ['#60A5FA', '#3B82F6'],
    bottomIndicator: isDark ? '#1F2937' : '#E5E7EB',
    statusbar: 'light-content'
  };

  // Animation values
  const formSlideUp = useSharedValue(height * 0.5);
  const formOpacity = useSharedValue(0);
  const logoFloat = useSharedValue(0);
  const heroOpacity = useSharedValue(0);

  useEffect(() => {
    // Hero fade in
    heroOpacity.value = withTiming(1, { duration: 800 });

    // Form slide up and fade in
    formSlideUp.value = withDelay(300, withTiming(0, {
      duration: 1000,
      easing: Easing.bezier(0.25, 0.1, 0.25, 1)
    }));
    formOpacity.value = withDelay(300, withTiming(1, { duration: 800 }));

    // Logo floating effect
    logoFloat.value = withRepeat(
      withSequence(
        withTiming(-15, { duration: 2000, easing: Easing.inOut(Easing.sin) }),
        withTiming(0, { duration: 2000, easing: Easing.inOut(Easing.sin) })
      ),
      -1, // infinite
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

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={[styles.container, { backgroundColor: theme.background }]}
    >
      <StatusBar barStyle={theme.statusbar} translucent backgroundColor="transparent" />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        bounces={false}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero Section */}
        <Animated.View style={[styles.heroContainerWrapper, animatedHeroStyle]}>
          <LinearGradient
            colors={theme.heroGradient}
            style={styles.heroContainer}
          >
            <View style={styles.statusBarSpacer} />
            <View style={styles.topBar}>
              <Text style={styles.timeText}>9:41</Text>
              <View style={styles.statusBarIcons}>
                <MaterialIcons name="signal-cellular-alt" size={18} color="white" />
                <MaterialIcons name="wifi" size={18} color="white" />
                <MaterialIcons name="battery-full" size={18} color="white" />
              </View>
            </View>

            <Animated.View style={[styles.logoWrapper, animatedLogoStyle]}>
              <View style={[styles.logoCard, { backgroundColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.2)', borderColor: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.4)' }]}>
                <Svg width="80" height="80" viewBox="0 0 100 100">
                  <Path
                    d="M10 80 L30 60 L50 70 L90 20 L90 80 Z"
                    fill="white"
                    opacity="0.4"
                  />
                  <Path
                    d="M10 80 L30 50 L50 65 L90 10"
                    fill="none"
                    stroke="white"
                    strokeWidth="6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <Circle cx="90" cy="10" fill="white" r="4" />
                </Svg>
              </View>
              <Text style={styles.brandName}>InvestAI</Text>
              <Text style={[styles.brandSlogan, { color: isDark ? 'rgba(224, 242, 254, 0.8)' : '#E0F2FE' }]}>Smarter Wealth Growth</Text>
            </Animated.View>
          </LinearGradient>
        </Animated.View>

        {/* Login Form Container */}
        <Animated.View style={[styles.formContainer, animatedFormStyle, { backgroundColor: theme.formBg }]}>
          <View style={styles.formHeader}>
            <Text style={[styles.welcomeText, { color: theme.textPrimary }]}>Welcome Back</Text>
            <Text style={[styles.subText, { color: theme.textSecondary }]}>Login to your investment dashboard</Text>
          </View>

          <View style={styles.inputGroup}>
            <View style={[styles.inputWrapper, { backgroundColor: theme.inputBg, borderColor: theme.inputBorder, borderWidth: isDark ? 0 : 1 }]}>
              <MaterialIcons name="alternate-email" size={20} color={theme.textSecondary} style={styles.inputIcon} />
              <TextInput
                placeholder="Email Address"
                placeholderTextColor={theme.textSecondary}
                style={[styles.input, { color: theme.textPrimary }]}
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>

            <View style={[styles.inputWrapper, { backgroundColor: theme.inputBg, borderColor: theme.inputBorder, borderWidth: isDark ? 0 : 1 }]}>
              <MaterialIcons name="lock" size={20} color={theme.textSecondary} style={styles.inputIcon} />
              <TextInput
                placeholder="Password"
                placeholderTextColor={theme.textSecondary}
                style={[styles.input, { color: theme.textPrimary }]}
                secureTextEntry
              />
            </View>

            <TouchableOpacity style={styles.forgotPassword}>
              <Text style={[styles.forgotPasswordText, { color: theme.primary }]}>Forgot Password?</Text>
            </TouchableOpacity>

            <TouchableOpacity style={[styles.signInButton, { backgroundColor: theme.primary }]} activeOpacity={0.8}>
              <Text style={styles.signInButtonText}>Sign In</Text>
            </TouchableOpacity>

            <View style={styles.dividerContainer}>
              <View style={[styles.divider, { backgroundColor: theme.divider }]} />
              <Text style={styles.dividerText}>Or continue with</Text>
              <View style={[styles.divider, { backgroundColor: theme.divider }]} />
            </View>

            <TouchableOpacity style={[styles.googleButton, { backgroundColor: theme.googleBtnBg, borderColor: theme.googleBtnBorder }]} activeOpacity={0.7}>
              <Svg width="20" height="20" viewBox="0 0 24 24">
                <Path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  fill="#4285F4"
                />
                <Path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <Path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <Path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 12-4.53z"
                  fill="#EA4335"
                />
              </Svg>
              <Text style={[styles.googleButtonText, { color: theme.googleText }]}>Sign in with Google</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>
              New here?{' '}
              <Text style={[styles.registerLink, { color: theme.primary }]} onPress={() => navigation.navigate('Register')}>
                Register
              </Text>
            </Text>
          </View>
        </Animated.View>
      </ScrollView>

      {/* Bottom Indicator */}
      <View style={[styles.bottomIndicatorContainer, { backgroundColor: theme.formBg }]}>
        <View style={[styles.bottomIndicator, { backgroundColor: theme.bottomIndicator }]} />
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },
  heroContainerWrapper: {
    width: '100%',
  },
  heroContainer: {
    height: height * 0.45,
    justifyContent: 'center',
    alignItems: 'center',
    paddingBottom: 40,
  },
  statusBarSpacer: {
    height: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight,
  },
  topBar: {
    width: '100%',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 32,
    position: 'absolute',
    top: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight || 20,
    zIndex: 20,
  },
  timeText: {
    color: 'white',
    fontSize: 14,
    fontWeight: '600',
  },
  statusBarIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoWrapper: {
    alignItems: 'center',
  },
  logoCard: {
    padding: 24,
    borderRadius: 32,
    borderWidth: 1,
    marginBottom: 20,
  },
  brandName: {
    color: 'white',
    fontSize: 36,
    fontWeight: '800',
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  brandSlogan: {
    fontSize: 18,
    marginTop: 4,
  },
  formContainer: {
    flex: 1,
    marginTop: -48,
    borderTopLeftRadius: 48,
    borderTopRightRadius: 48,
    paddingHorizontal: 32,
    paddingTop: 48,
    paddingBottom: 40,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -10 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 8,
  },
  formHeader: {
    marginBottom: 32,
  },
  welcomeText: {
    fontSize: 26,
    fontWeight: '700',
    marginBottom: 8,
  },
  subText: {
    fontSize: 15,
  },
  inputGroup: {
    gap: 16,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 20,
    paddingHorizontal: 20,
    height: 64,
  },
  inputIcon: {
    marginRight: 16,
  },
  input: {
    flex: 1,
    fontSize: 16,
  },
  forgotPassword: {
    alignSelf: 'flex-end',
    marginTop: 4,
  },
  forgotPasswordText: {
    fontSize: 14,
    fontWeight: '600',
  },
  signInButton: {
    height: 64,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 16,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 5,
  },
  signInButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: '700',
  },
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 12,
  },
  divider: {
    flex: 1,
    height: 1,
  },
  dividerText: {
    marginHorizontal: 16,
    color: '#9CA3AF',
    fontSize: 14,
  },
  googleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 64,
    borderRadius: 20,
    borderWidth: 1,
  },
  googleButtonText: {
    marginLeft: 12,
    fontSize: 16,
    fontWeight: '600',
  },
  footer: {
    marginTop: 32,
    marginBottom: 20,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 16,
  },
  registerLink: {
    fontWeight: '700',
  },
  bottomIndicatorContainer: {
    alignItems: 'center',
    paddingBottom: 12,
  },
  bottomIndicator: {
    width: 128,
    height: 6,
    borderRadius: 3,
  }
});

export default LoginScreen;
