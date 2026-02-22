// src/screens/auth/AuthSuccessScreen.js
import React, { useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    StatusBar,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withDelay,
} from 'react-native-reanimated';

// Design System Imports
import { useAppTheme } from '../../hooks/useAppTheme';
import AppButton from '../../components/AppButton';

const AuthSuccessScreen = ({ navigation, route }) => {
    const theme = useAppTheme();
    const {
        title = 'Success!',
        message = 'Your action was completed successfully.',
        buttonLabel = 'Back to Login'
    } = route.params || {};

    const scale = useSharedValue(0);
    const opacity = useSharedValue(0);

    useEffect(() => {
        scale.value = withSpring(1, { damping: 12 });
        opacity.value = withDelay(200, withSpring(1));
    }, []);

    const animatedIconStyle = useAnimatedStyle(() => ({
        transform: [{ scale: scale.value }],
        opacity: opacity.value,
    }));

    const handleProceed = () => {
        navigation.navigate('Login');
    };

    return (
        <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
            <StatusBar barStyle={theme.isDark ? "light-content" : "dark-content"} />

            <View style={styles.content}>
                <Animated.View style={[styles.iconWrapper, animatedIconStyle, { backgroundColor: theme.isDark ? 'rgba(16, 185, 129, 0.1)' : 'rgba(16, 185, 129, 0.05)' }]}>
                    <MaterialIcons name="check-circle" size={100} color={theme.colors.success} />
                </Animated.View>

                <Text style={[styles.title, { color: theme.colors.textPrimary, fontSize: theme.typography.sizes.h2 }]}>{title}</Text>
                <Text style={[styles.message, { color: theme.colors.textSecondary, fontSize: theme.typography.sizes.body1 }]}>
                    {message}
                </Text>
            </View>

            <View style={styles.footer}>
                <AppButton
                    title={buttonLabel}
                    onPress={handleProceed}
                />
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        padding: 32,
        justifyContent: 'center',
        alignItems: 'center',
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        width: '100%',
    },
    iconWrapper: {
        width: 160,
        height: 160,
        borderRadius: 80,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 40,
    },
    title: {
        fontWeight: '800',
        marginBottom: 16,
        textAlign: 'center',
    },
    message: {
        textAlign: 'center',
        lineHeight: 26,
        paddingHorizontal: 20,
    },
    footer: {
        width: '100%',
        paddingBottom: 40,
    }
});

export default AuthSuccessScreen;
