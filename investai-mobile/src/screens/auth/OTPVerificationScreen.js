// src/screens/auth/OTPVerificationScreen.js
import React, { useState, useEffect, useRef } from 'react';
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
    Alert,
} from 'react-native';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withTiming,
    withDelay,
    Easing
} from 'react-native-reanimated';

// Design System Imports
import { useAppTheme } from '../../hooks/useAppTheme';
import AppButton from '../../components/AppButton';
import AppCard from '../../components/AppCard';
import AppHeader from '../../components/AppHeader';
import { authApi } from '../../api/authApi';

const { height } = Dimensions.get('window');

const OTPVerificationScreen = ({ navigation, route }) => {
    const theme = useAppTheme();
    const { email } = route.params || {};
    
    // Backend uses 6 digits
    const [otp, setOtp] = useState(['', '', '', '', '', '']);
    const [timer, setTimer] = useState(59);
    const [loading, setLoading] = useState(false);
    const inputs = useRef([]);

    // Animation values
    const formSlideUp = useSharedValue(height * 0.5);
    const formOpacity = useSharedValue(0);

    useEffect(() => {
        formSlideUp.value = withDelay(100, withTiming(0, {
            duration: 800,
            easing: Easing.bezier(0.25, 0.1, 0.25, 1)
        }));
        formOpacity.value = withDelay(100, withTiming(1, { duration: 600 }));

        const interval = setInterval(() => {
            setTimer((prev) => (prev > 0 ? prev - 1 : 0));
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const animatedFormStyle = useAnimatedStyle(() => ({
        opacity: formOpacity.value,
        transform: [{ translateY: formSlideUp.value }],
    }));

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
            Alert.alert('Error', 'Please enter the complete 6-digit code');
            return;
        }

        setLoading(true);
        try {
            await authApi.verifyOTP(email, fullOtp);
            // On success, go to AuthSuccess then Login
            navigation.replace('AuthSuccess');
        } catch (error) {
            const msg = error?.response?.data?.detail || 'Verification failed. Please check the code.';
            Alert.alert('Verification Error', msg);
        } finally {
            setLoading(false);
        }
    };

    const handleResend = async () => {
        try {
            await authApi.resendOTP(email);
            setTimer(59);
            Alert.alert('Sent', 'A new verification code has been sent to your email.');
        } catch (error) {
            Alert.alert('Error', 'Failed to resend code. Please try again later.');
        }
    };

    return (
        <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={[styles.container, { backgroundColor: theme.colors.background }]}
        >
            <AppHeader onBack={() => navigation.goBack()} transparent />

            <ScrollView
                contentContainerStyle={styles.scrollContent}
                bounces={false}
                showsVerticalScrollIndicator={false}
            >
                <View style={styles.headerSpacer} />

                <Animated.View style={[styles.formWrapper, animatedFormStyle]}>
                    <AppCard style={styles.formContainer}>
                        <View style={styles.formHeader}>
                            <Text style={[styles.title, { color: theme.colors.textPrimary, fontSize: theme.typography.sizes.h3 }]}>Verification</Text>
                            <Text style={[styles.subText, { color: theme.colors.textSecondary }]}>
                                Enter the 6-digit code sent to{"\n"}
                                <Text style={{ fontWeight: '700', color: theme.colors.primary }}>{email}</Text>
                            </Text>
                        </View>

                        <View style={styles.otpContainer}>
                            {otp.map((digit, index) => (
                                <TextInput
                                    key={index}
                                    ref={(ref) => (inputs.current[index] = ref)}
                                    style={[
                                        styles.otpInput,
                                        {
                                            backgroundColor: theme.colors.field,
                                            color: theme.colors.textPrimary,
                                            borderColor: digit ? theme.colors.primary : theme.colors.border,
                                            borderWidth: theme.isDark ? 0 : 1,
                                            borderRadius: theme.radii.lg,
                                        }
                                    ]}
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

                        <View style={styles.timerContainer}>
                            <Text style={[styles.timerText, { color: theme.colors.textSecondary }]}>
                                {timer > 0 ? `Resend code in 00:${timer.toString().padStart(2, '0')}` : "Didn't receive code?"}
                            </Text>
                            {timer === 0 && (
                                <TouchableOpacity onPress={handleResend}>
                                    <Text style={[styles.resendLink, { color: theme.colors.primary }]}> Resend Now</Text>
                                </TouchableOpacity>
                            )}
                        </View>

                        <AppButton
                            title="Verify & Proceed"
                            onPress={handleVerify}
                            loading={loading}
                            style={styles.verifyButton}
                            disabled={otp.some(d => !d) || loading}
                        />
                    </AppCard>
                </Animated.View>
            </ScrollView>
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
    headerSpacer: {
        height: height * 0.15,
    },
    formWrapper: {
        flex: 1,
    },
    formContainer: {
        flex: 1,
        borderTopLeftRadius: 48,
        borderTopRightRadius: 48,
        paddingHorizontal: 32,
        paddingTop: 48,
    },
    formHeader: {
        marginBottom: 40,
    },
    title: {
        fontWeight: '700',
        marginBottom: 12,
    },
    subText: {
        fontSize: 16,
        lineHeight: 24,
    },
    otpContainer: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginBottom: 32,
    },
    otpInput: {
        width: 48,
        height: 56,
        textAlign: 'center',
        fontSize: 22,
        fontWeight: '700',
    },
    timerContainer: {
        flexDirection: 'row',
        justifyContent: 'center',
        marginBottom: 40,
    },
    timerText: {
        fontSize: 15,
    },
    resendLink: {
        fontSize: 15,
        fontWeight: '700',
    },
    verifyButton: {
        marginTop: 'auto',
        marginBottom: 20,
    }
});

export default OTPVerificationScreen;
