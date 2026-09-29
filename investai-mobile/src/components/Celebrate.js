// src/components/Celebrate.js
//
// A burst of pastel pills that fly out from the middle of the parent and fall
// away. Place it inside a relatively positioned View; it fills it and never
// takes touches. Every change of `fire` (e.g. a counter) replays the burst;
// `loop` keeps bursting until unmounted. Native driver only; nothing is drawn
// when the OS asks for reduced motion.
import React, { useEffect, useRef } from 'react';
import { View, Animated, Easing, StyleSheet } from 'react-native';
import { palette } from '../theme/tokens';
import { isReduceMotion } from '../theme/motion';

const TONES = [palette.lime, palette.yellow, palette.lavender, palette.coral, palette.mint];

// Fixed spread so every burst looks the same, and the same on every device.
const pieces = (count, spread) => Array.from({ length: count }, (_, i) => {
  const angle = (i / count) * Math.PI * 2 + (i % 3) * 0.35;
  const dist = spread * (0.55 + ((i * 37) % 45) / 100);
  return {
    dx: Math.cos(angle) * dist,
    dy: Math.sin(angle) * dist * 0.8 - spread * 0.35,
    spin: `${((i * 73) % 2 ? 1 : -1) * (180 + ((i * 53) % 360))}deg`,
    color: TONES[i % TONES.length],
  };
});

export default function Celebrate({ fire = 0, count = 18, spread = 140, loop = false }) {
  const p = useRef(new Animated.Value(0)).current;
  const set = useRef(pieces(count, spread)).current;
  const reduce = isReduceMotion();

  useEffect(() => {
    if (reduce || (!fire && !loop)) return undefined;
    p.setValue(0);
    const burst = Animated.timing(p, { toValue: 1, duration: 1300, easing: Easing.out(Easing.quad), useNativeDriver: true });
    const anim = loop
      ? Animated.loop(Animated.sequence([burst, Animated.delay(600)]), { resetBeforeIteration: true })
      : burst;
    anim.start();
    return () => anim.stop();
  }, [fire, loop, reduce, p]);

  if (reduce) return null;
  return (
    <View pointerEvents="none" style={styles.fill} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
      {set.map((s, i) => (
        <Animated.View
          key={i}
          style={[styles.pill, {
            backgroundColor: s.color,
            opacity: p.interpolate({ inputRange: [0, 0.05, 0.7, 1], outputRange: [0, 1, 1, 0] }),
            transform: [
              { translateX: p.interpolate({ inputRange: [0, 1], outputRange: [0, s.dx] }) },
              // Up and out, then gravity takes over.
              { translateY: p.interpolate({ inputRange: [0, 0.45, 1], outputRange: [0, s.dy, s.dy + spread * 0.9] }) },
              { rotate: p.interpolate({ inputRange: [0, 1], outputRange: ['0deg', s.spin] }) },
              { scale: p.interpolate({ inputRange: [0, 0.15, 1], outputRange: [0.3, 1, 0.8] }) },
            ],
          }]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  pill: {
    position: 'absolute', width: 9, height: 20, borderRadius: 5,
    borderWidth: 1.5, borderColor: palette.ink,
  },
});
