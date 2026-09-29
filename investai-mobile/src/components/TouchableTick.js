// src/components/TouchableTick.js
//
// The app's one pressable. A light haptic tick plus "press depth": the element
// sinks to 97% while held and springs back on release (native driver, so it
// stays smooth even while JS is busy). Reduced motion: no scale.
import React, { useRef } from 'react';
import { Pressable, Animated, Platform } from 'react-native';
import * as Haptics from 'expo-haptics';
import { isReduceMotion } from '../theme/motion';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export default function TouchableTick({ style, onPress, onPressIn, onPressOut, pressScale = 0.97, children, ...rest }) {
    const scale = useRef(new Animated.Value(1)).current;

    const springTo = (toValue) => {
        if (isReduceMotion()) return;
        Animated.spring(scale, { toValue, useNativeDriver: true, speed: 40, bounciness: toValue === 1 ? 6 : 0 }).start();
    };

    const handlePress = (e) => {
        if (Platform.OS !== 'web') {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        }
        onPress?.(e);
    };

    return (
        <AnimatedPressable
            {...rest}
            onPress={handlePress}
            onPressIn={(e) => { if (!rest.disabled) springTo(pressScale); onPressIn?.(e); }}
            onPressOut={(e) => { springTo(1); onPressOut?.(e); }}
            style={[style, { transform: [{ scale }] }]}
        >
            {children}
        </AnimatedPressable>
    );
}
