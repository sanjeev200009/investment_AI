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
  StatusBar
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
      style={styles.container}
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
            colors={['#60A5FA', '#3B82F6']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.heroContainer}
          >
            <Animated.View style={[styles.logoWrapper, animatedLogoStyle]}>
              <View style={styles.logoCard}>
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
              <Text style={styles.brandSlogan}>Smarter Wealth Growth</Text>
            </Animated.View>
          </LinearGradient>
        </Animated.View>

        {/* Login Form Container */}
        <Animated.View style={[styles.formContainer, animatedFormStyle]}>
          <View style={styles.formHeader}>
            <Text style={styles.welcomeText}>Welcome Back</Text>
            <Text style={styles.subText}>Login to your investment dashboard</Text>
          </View>

          <View style={styles.inputGroup}>
            <View style={styles.inputWrapper}>
              <MaterialIcons name="alternate-email" size={20} color="#9CA3AF" style={styles.inputIcon} />
              <TextInput
                placeholder="Email Address"
                placeholderTextColor="#9CA3AF"
                style={styles.input}
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>

            <View style={styles.inputWrapper}>
              <MaterialIcons name="lock-outline" size={20} color="#9CA3AF" style={styles.inputIcon} />
              <TextInput
                placeholder="Password"
                placeholderTextColor="#9CA3AF"
                style={styles.input}
                secureTextEntry
              />
            </View>

            <TouchableOpacity style={styles.forgotPassword}>
              <Text style={styles.forgotPasswordText}>Forgot Password?</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.signInButton} activeOpacity={0.8}>
              <Text style={styles.signInButtonText}>Sign In</Text>
            </TouchableOpacity>

            <View style={styles.dividerContainer}>
              <View style={styles.divider} />
              <Text style={styles.dividerText}>Or continue with</Text>
              <View style={styles.divider} />
            </View>

            <TouchableOpacity style={styles.googleButton} activeOpacity={0.7}>
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
              <Text style={styles.googleButtonText}>Sign in with Google</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>
              New here?{' '}
              <Text style={styles.registerLink} onPress={() => navigation.navigate('Register')}>
                Register
              </Text>
            </Text>
          </View>
        </Animated.View>
      </ScrollView>

      {/* Bottom Indicator */}
      <View style={styles.bottomIndicatorContainer}>
        <View style={styles.bottomIndicator} />
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F3F4F6',
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
    paddingBottom: 60,
  },
  logoWrapper: {
    alignItems: 'center',
  },
  logoCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    padding: 20,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.4)',
    marginBottom: 16,
  },
  brandName: {
    color: 'white',
    fontSize: 36,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  brandSlogan: {
    color: '#E0F2FE',
    fontSize: 18,
    opacity: 0.9,
    marginTop: 4,
  },
  formContainer: {
    flex: 1,
    backgroundColor: 'white',
    marginTop: -120, // Moved up further from -80
    borderTopLeftRadius: 60,
    borderTopRightRadius: 60,
    paddingHorizontal: 28,
    paddingTop: 40,
    paddingBottom: 80, // Increased for button visibility
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -10 },
    shadowOpacity: 0.08,
    shadowRadius: 15,
    elevation: 8,
  },
  formHeader: {
    marginBottom: 28,
  },
  welcomeText: {
    fontSize: 26,
    fontWeight: '700',
    color: '#111827',
  },
  subText: {
    fontSize: 15,
    color: '#6B7280',
    marginTop: 4,
  },
  inputGroup: {
    gap: 14,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    paddingHorizontal: 16,
    height: 58,
    borderWidth: 1,
    borderColor: '#F3F4F6',
  },
  inputIcon: {
    marginRight: 12,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: '#111827',
  },
  forgotPassword: {
    alignSelf: 'flex-end',
    marginTop: 4,
  },
  forgotPasswordText: {
    color: '#3B82F6',
    fontSize: 14,
    fontWeight: '600',
  },
  signInButton: {
    backgroundColor: '#3B82F6',
    height: 58,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 12,
    shadowColor: '#3B82F6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 3,
  },
  signInButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: '700',
  },
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 20,
  },
  divider: {
    flex: 1,
    height: 1,
    backgroundColor: '#E5E7EB',
  },
  dividerText: {
    marginHorizontal: 12,
    color: '#9CA3AF',
    fontSize: 14,
  },
  googleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 58,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    backgroundColor: 'white',
  },
  googleButtonText: {
    marginLeft: 12,
    fontSize: 16,
    color: '#374151',
    fontWeight: '600',
  },
  footer: {
    marginTop: 36,
    marginBottom: 40,
    alignItems: 'center',
  },
  footerText: {
    color: '#6B7280',
    fontSize: 16,
  },
  registerLink: {
    color: '#3B82F6',
    fontWeight: '700',
  },
  bottomIndicatorContainer: {
    alignItems: 'center',
    paddingBottom: 8,
    backgroundColor: 'white',
  },
  bottomIndicator: {
    width: 120,
    height: 5,
    backgroundColor: '#E5E7EB',
    borderRadius: 3,
  }
});

export default LoginScreen;
