// src/components/Motion.js
//
// Small motion building blocks from the motion system canvas:
//   <Rise index>        a list row rising in from a slight 3D angle (first 8 only)
//   <CoinStar>          the watchlist star that flips like a coin, with a pill burst
//   <Skeleton>, <SkeletonRows>  content-shaped placeholders with one soft sheen
// All native-driver (transform/opacity) and plain when reduced motion is on.
import React, { useEffect, useRef } from 'react';
import { View, Animated, Easing, StyleSheet, useWindowDimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { MaterialIcons } from '@expo/vector-icons';
import TouchableTick from './TouchableTick';
import { palette, radii } from '../theme/tokens';
import { EASE_OUT, isReduceMotion } from '../theme/motion';

const MAX_STAGGER = 8;

export function Rise({ index = 0, children, style }) {
  const animate = index < MAX_STAGGER && !isReduceMotion();
  const p = useRef(new Animated.Value(animate ? 0 : 1)).current;
  useEffect(() => {
    if (!animate) return;
    Animated.timing(p, { toValue: 1, duration: 420, delay: index * 40, easing: EASE_OUT, useNativeDriver: true }).start();
  }, [animate, index, p]);
  if (!animate) return <View style={style}>{children}</View>;
  return (
    <Animated.View style={[style, {
      opacity: p,
      transform: [
        { perspective: 700 },
        { translateY: p.interpolate({ inputRange: [0, 1], outputRange: [20, 0] }) },
        { rotateX: p.interpolate({ inputRange: [0, 1], outputRange: ['-12deg', '0deg'] }) },
      ],
    }]}>
      {children}
    </Animated.View>
  );
}

const BURST = [
  { x: -30, y: -28, r: '-40deg', c: palette.lime },
  { x: 28, y: -30, r: '30deg', c: palette.lavender },
  { x: 32, y: 18, r: '60deg', c: palette.coral },
  { x: -28, y: 22, r: '-70deg', c: palette.yellow },
];

export function CoinStar({ on, onPress, disabled, label, size = 56 }) {
  const flip = useRef(new Animated.Value(on ? 1 : 0)).current;
  const burst = useRef(new Animated.Value(0)).current;
  const first = useRef(true);

  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (isReduceMotion()) { flip.setValue(on ? 1 : 0); return; }
    Animated.spring(flip, { toValue: on ? 1 : 0, useNativeDriver: true, damping: 10, stiffness: 140 }).start();
    if (on) {
      burst.setValue(0);
      Animated.timing(burst, { toValue: 1, duration: 700, delay: 120, easing: EASE_OUT, useNativeDriver: true }).start();
    }
  }, [on, flip, burst]);

  const front = flip.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] });
  const back = flip.interpolate({ inputRange: [0, 1], outputRange: ['180deg', '360deg'] });
  const face = { ...StyleSheet.absoluteFillObject, borderRadius: radii.full, alignItems: 'center', justifyContent: 'center', backfaceVisibility: 'hidden' };

  return (
    <TouchableTick onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityLabel={label}
      accessibilityState={{ selected: !!on, disabled: !!disabled }} style={{ width: size, height: size }}>
      {BURST.map((b) => (
        <Animated.View key={b.c} pointerEvents="none" style={{
          position: 'absolute', left: size / 2 - 3, top: size / 2 - 6, width: 6, height: 12, borderRadius: 6, backgroundColor: b.c,
          opacity: burst.interpolate({ inputRange: [0, 0.1, 1], outputRange: [0, 1, 0] }),
          transform: [
            { translateX: burst.interpolate({ inputRange: [0, 1], outputRange: [0, b.x] }) },
            { translateY: burst.interpolate({ inputRange: [0, 1], outputRange: [0, b.y] }) },
            { rotate: burst.interpolate({ inputRange: [0, 1], outputRange: ['0deg', b.r] }) },
          ],
        }} />
      ))}
      <Animated.View style={[face, { backgroundColor: '#FFFFFF', transform: [{ perspective: 400 }, { rotateY: front }] }]}>
        <MaterialIcons name="star-border" size={24} color={palette.ink} />
      </Animated.View>
      <Animated.View style={[face, { backgroundColor: palette.yellow, borderWidth: 2, borderColor: palette.ink, transform: [{ perspective: 400 }, { rotateY: back }] }]}>
        <MaterialIcons name="star" size={24} color={palette.ink} />
      </Animated.View>
    </TouchableTick>
  );
}

// One shared sheen value so every skeleton on screen sweeps in step.
function useSheen() {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (isReduceMotion()) return undefined;
    const loop = Animated.loop(Animated.timing(v, { toValue: 1, duration: 1400, easing: Easing.inOut(Easing.ease), useNativeDriver: true }));
    loop.start();
    return () => loop.stop();
  }, [v]);
  return v;
}

export function Skeleton({ style, sheen }) {
  const { width } = useWindowDimensions();
  return (
    <View style={[{ backgroundColor: 'rgba(255,255,255,0.6)', overflow: 'hidden', borderRadius: 16 }, style]}>
      {sheen ? (
        <Animated.View style={{ ...StyleSheet.absoluteFillObject, width: 180,
          transform: [{ translateX: sheen.interpolate({ inputRange: [0, 1], outputRange: [-180, width] }) }] }}>
          <LinearGradient colors={['rgba(255,255,255,0)', 'rgba(255,255,255,0.9)', 'rgba(255,255,255,0)']}
            start={{ x: 0, y: 0.5 }} end={{ x: 1, y: 0.5 }} style={{ flex: 1 }} />
        </Animated.View>
      ) : null}
    </View>
  );
}

// Stock-row placeholders: circle, two text lines, a change pill.
export function SkeletonRows({ count = 6, label }) {
  const sheen = useSheen();
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel={label} style={{ gap: 10 }}>
      {Array.from({ length: count }).map((_, i) => (
        <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 28, backgroundColor: 'rgba(255,255,255,0.45)' }}>
          <Skeleton sheen={sheen} style={{ width: 44, height: 44, borderRadius: radii.full }} />
          <View style={{ flex: 1, gap: 8 }}>
            <Skeleton sheen={sheen} style={{ width: '55%', height: 12, borderRadius: 6 }} />
            <Skeleton sheen={sheen} style={{ width: '35%', height: 10, borderRadius: 6 }} />
          </View>
          <Skeleton sheen={sheen} style={{ width: 56, height: 22, borderRadius: radii.full }} />
        </View>
      ))}
    </View>
  );
}

// Home's first load: hero figure, stat row, pill row, rows.
export function HomeSkeleton({ label }) {
  const sheen = useSheen();
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel={label} style={{ gap: 22 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ flex: 1, gap: 8 }}>
          <Skeleton sheen={sheen} style={{ width: '40%', height: 12, borderRadius: 6 }} />
          <Skeleton sheen={sheen} style={{ width: '70%', height: 22, borderRadius: 8 }} />
        </View>
        <Skeleton sheen={sheen} style={{ width: 56, height: 56, borderRadius: radii.full }} />
      </View>
      <Skeleton sheen={sheen} style={{ height: 120, borderRadius: 32 }} />
      <View style={{ flexDirection: 'row', gap: 10 }}>
        {[0, 1, 2].map((i) => <Skeleton key={i} sheen={sheen} style={{ flex: 1, height: 96, borderRadius: 28 }} />)}
      </View>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <Skeleton sheen={sheen} style={{ width: 72, height: 200, borderRadius: radii.full }} />
        <Skeleton sheen={sheen} style={{ width: 72, height: 200, borderRadius: radii.full }} />
        <Skeleton sheen={sheen} style={{ flex: 1, height: 200, borderRadius: 32 }} />
      </View>
    </View>
  );
}
