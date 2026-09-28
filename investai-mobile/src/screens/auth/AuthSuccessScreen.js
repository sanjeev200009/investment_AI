// src/screens/auth/AuthSuccessScreen.js — v2 "Soft pastel" lime success state.
import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withDelay,
} from 'react-native-reanimated';

import { Screen, Card, PillButton } from '../../components/ui';
import { palette, fonts, radii } from '../../theme/tokens';
import { useT } from '../../store/languageStore';

const AuthSuccessScreen = ({ navigation, route }) => {
    const { t } = useT();
    const {
        title = t('authsuccess_title'),
        message = t('authsuccess_message'),
        buttonLabel = t('authsuccess_back_login')
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
        <Screen
            scroll={false}
            edges={['top', 'bottom']}
            contentStyle={styles.content}
            footer={<View style={styles.footer}><PillButton title={buttonLabel} onPress={handleProceed} /></View>}
        >
            <Card tone="lime" style={styles.card}>
                <Animated.View style={[styles.badge, animatedIconStyle]}>
                    <MaterialIcons name="check" size={56} color={palette.lime} />
                </Animated.View>
                <Text style={styles.title} accessibilityRole="header">{title}</Text>
                <Text style={styles.message}>{message}</Text>
            </Card>
        </Screen>
    );
};

const styles = StyleSheet.create({
    content: { justifyContent: 'center', paddingBottom: 24 },
    card: { paddingVertical: 36, paddingHorizontal: 24, gap: 16 },
    badge: {
        width: 104, height: 104, borderRadius: radii.full, backgroundColor: palette.limeInk,
        alignItems: 'center', justifyContent: 'center', marginBottom: 8,
    },
    title: { fontFamily: fonts.regular, fontSize: 40, lineHeight: 44, letterSpacing: -1.5, color: palette.limeInk },
    message: { fontFamily: fonts.regular, fontSize: 16, lineHeight: 23, color: palette.limeInk },
    footer: { paddingHorizontal: 20, paddingBottom: 16 },
});

export default AuthSuccessScreen;
