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
import { validatePassword, validateConfirmPassword } from '../../utils/validation';

const { width, height } = Dimensions.get('window');

const ResetPasswordScreen = ({ navigation }) => {
    const theme = useAppTheme();

    // Form State
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
            await authApi.resetPassword('mock-token', password);
            // Linear Flow Ends with Success State
            navigation.navigate('AuthSuccess', {
                title: 'Reset Successful!',
                message: 'Your password has been changed successfully. You can now login with your new credentials.',
                buttonLabel: 'Back to Login'
            });
        } catch (err) {
            Alert.alert('Error', err);
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
                            <Text style={[styles.brandName, { fontSize: theme.typography.sizes.h3 }]}>InvestAI</Text>
                            <Text style={styles.brandSlogan}>Reset Your Security</Text>
                        </Animated.View>
                    </LinearGradient>
                </Animated.View>

                <Animated.View style={[animatedFormStyle]}>
                    <AppCard style={styles.formContainer}>
                        <View style={styles.formHeader}>
                            <Text style={[styles.welcomeText, { color: theme.colors.textPrimary, fontSize: theme.typography.sizes.h3 }]}>New Password</Text>
                            <Text style={[styles.subText, { color: theme.colors.textSecondary }]}>Please create a secure new password for your account.</Text>
                        </View>

                        <View style={styles.inputGroup}>
                            <AppInput
                                placeholder="New Password"
                                value={password}
                                onChangeText={setPassword}
                                error={errors.password}
                                icon={<MaterialIcons name="lock-outline" size={20} color={theme.colors.textSecondary} />}
                                secureTextEntry
                            />

                            <AppInput
                                placeholder="Confirm New Password"
                                value={confirmPassword}
                                onChangeText={setConfirmPassword}
                                error={errors.confirmPassword}
                                icon={<MaterialIcons name="lock-reset" size={20} color={theme.colors.textSecondary} />}
                                secureTextEntry
                            />

                            <AppButton
                                title="Save Password"
                                onPress={handleResetPassword}
                                loading={loading}
                                disabled={!password || !confirmPassword}
                                style={{ marginTop: 24 }}
                            />
                        </View>

                        <TouchableOpacity style={styles.footer} onPress={() => navigation.navigate('Login')}>
                            <Text style={[styles.footerText, { color: theme.colors.textSecondary }]}>
                                Remember password? <Text style={[styles.registerLink, { color: theme.colors.primary }]}>Login</Text>
                            </Text>
                        </TouchableOpacity>
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
    heroContainer: { height: height * 0.45, justifyContent: 'center', alignItems: 'center', paddingBottom: 40 },
    statusBarSpacer: { height: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight },
    topBar: { width: '100%', flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 32, position: 'absolute', top: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight || 20, zIndex: 20 },
    spacer: { width: 40 },
    statusBarIcons: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    logoWrapper: { alignItems: 'center' },
    logoCard: { padding: 24, borderWidth: 1, marginBottom: 20 },
    brandName: { color: 'white', fontWeight: '800', letterSpacing: -0.5 },
    brandSlogan: { fontSize: 16, marginTop: 4, color: 'rgba(224, 242, 254, 0.8)' },
    formContainer: { marginTop: -48, borderTopLeftRadius: 48, borderTopRightRadius: 48, paddingHorizontal: 32, paddingTop: 48, paddingBottom: 40, flex: 1 },
    formHeader: { marginBottom: 32 },
    welcomeText: { fontWeight: '700', marginBottom: 12 },
    subText: { fontSize: 15, lineHeight: 22 },
    inputGroup: { gap: 16 },
    footer: { marginTop: 32, marginBottom: 20, alignItems: 'center' },
    footerText: { fontSize: 16 },
    registerLink: { fontWeight: '700' },
    bottomIndicatorContainer: { alignItems: 'center', paddingBottom: 12 },
    bottomIndicator: { width: 128, height: 6, borderRadius: 3 }
});

export default ResetPasswordScreen;
