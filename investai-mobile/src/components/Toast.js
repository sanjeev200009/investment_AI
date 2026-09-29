// src/components/Toast.js
//
// In-app notices: a pastel pill that slides down from the top, stays a moment
// and slides away. Call toast(message, 'success' | 'info' | 'error') from
// anywhere; <ToastHost/> is mounted once in App.js above the navigator.
// Destructive confirmations stay as Alert dialogs; toasts only report.
//
// Note: a React Native <Modal> draws above this host, so errors raised while a
// modal form is still open keep their Alert.
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Text, StyleSheet, AccessibilityInfo, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import TouchableTick from './TouchableTick';
import { palette, fonts, radii } from '../theme/tokens';
import { EASE_OUT, isReduceMotion } from '../theme/motion';

const TONES = {
  success: { bg: palette.lime, ink: palette.limeInk, icon: 'check-circle' },
  info: { bg: palette.lavender, ink: palette.lavenderInk, icon: 'info-outline' },
  error: { bg: palette.coral, ink: palette.coralInk, icon: 'error-outline' },
};
const SHOW_MS = 2800;

let listener = null;
let seq = 0;

export function toast(message, type = 'success') {
  if (!message) return;
  listener?.({ id: ++seq, message: String(message), type: TONES[type] ? type : 'info' });
}

export function ToastHost() {
  const insets = useSafeAreaInsets();
  const [current, setCurrent] = useState(null);
  const p = useRef(new Animated.Value(0)).current;
  const timer = useRef(null);

  const hide = () => {
    clearTimeout(timer.current);
    Animated.timing(p, { toValue: 0, duration: isReduceMotion() ? 120 : 260, useNativeDriver: true })
      .start(({ finished }) => { if (finished) setCurrent(null); });
  };

  useEffect(() => {
    listener = (next) => {
      clearTimeout(timer.current);
      setCurrent(next);
      p.setValue(0);
      Animated.timing(p, { toValue: 1, duration: isReduceMotion() ? 120 : 380, easing: EASE_OUT, useNativeDriver: true }).start();
      // iOS has no live regions; announce explicitly.
      if (Platform.OS === 'ios') AccessibilityInfo.announceForAccessibility?.(next.message);
      timer.current = setTimeout(hide, SHOW_MS);
    };
    return () => { listener = null; clearTimeout(timer.current); };
  }, [p]);

  if (!current) return null;
  const tone = TONES[current.type];
  const style = {
    opacity: p,
    transform: isReduceMotion() ? [] : [{ translateY: p.interpolate({ inputRange: [0, 1], outputRange: [-80, 0] }) }],
  };
  return (
    <Animated.View pointerEvents="box-none" style={[styles.wrap, { top: insets.top + 8 }, style]}>
      <TouchableTick
        onPress={hide}
        accessibilityRole="alert"
        accessibilityLiveRegion="polite"
        accessibilityLabel={current.message}
        style={[styles.pill, { backgroundColor: tone.bg }]}
      >
        <MaterialIcons name={tone.icon} size={20} color={tone.ink} />
        <Text style={[styles.text, { color: tone.ink }]} numberOfLines={2}>{current.message}</Text>
      </TouchableTick>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: 16, right: 16, alignItems: 'center', zIndex: 1000, elevation: 20 },
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 10, maxWidth: '100%',
    borderRadius: radii.full, paddingHorizontal: 18, paddingVertical: 12, minHeight: 48,
    shadowColor: '#0F1115', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.1, shadowRadius: 20,
  },
  text: { flexShrink: 1, fontFamily: fonts.medium, fontSize: 15 },
});
