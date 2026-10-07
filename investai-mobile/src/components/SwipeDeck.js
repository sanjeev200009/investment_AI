// src/components/SwipeDeck.js
//
// A calm 3D card stack: the top card follows the finger with a slight tilt,
// the two cards behind sit smaller and lower in perspective, and a swipe past
// a third of the width sends the top card off and lifts the next one into
// place. The deck loops. Reduced motion: no tilt, cards simply change.
import React, { useRef, useState } from 'react';
import { View, Animated, PanResponder, Easing } from 'react-native';
import { isReduceMotion } from '../theme/motion';

const BEHIND = 2;     // cards visible behind the top one
const STEP_Y = 10;    // each card behind sits this much lower
const STEP_SCALE = 0.05;

export default function SwipeDeck({ items, renderCard, onIndexChange, label }) {
  const [index, setIndex] = useState(0);
  const [width, setWidth] = useState(0);
  const [height, setHeight] = useState(0);
  const dx = useRef(new Animated.Value(0)).current;
  const lift = useRef(new Animated.Value(0)).current; // 0..1 while the next card rises
  const busy = useRef(false);
  const widthRef = useRef(0);
  // The pan handler is created once; it reads the current list and callback here.
  const latest = useRef({ items, onIndexChange });
  latest.current = { items, onIndexChange };

  const advance = (dir) => {
    const { items: list, onIndexChange: changed } = latest.current;
    if (busy.current || list.length < 2) return;
    busy.current = true;
    const calm = isReduceMotion();
    Animated.parallel([
      Animated.timing(dx, {
        toValue: dir * (widthRef.current || 400) * 1.3,
        duration: calm ? 0 : 260, easing: Easing.out(Easing.cubic), useNativeDriver: true,
      }),
      Animated.timing(lift, { toValue: 1, duration: calm ? 0 : 260, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
    ]).start(() => {
      setIndex(i => {
        const next = (i + 1) % list.length;
        changed?.(next);
        return next;
      });
      dx.setValue(0);
      lift.setValue(0);
      busy.current = false;
    });
  };

  const pan = useRef(PanResponder.create({
    // Only claim clearly horizontal drags, so the page still scrolls vertically.
    onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy) * 1.5,
    onPanResponderTerminationRequest: () => false,
    onPanResponderMove: (_, g) => {
      dx.setValue(g.dx);
      lift.setValue(Math.min(Math.abs(g.dx) / ((widthRef.current || 400) * 0.6), 1));
    },
    onPanResponderRelease: (_, g) => {
      const w = widthRef.current || 400;
      if (Math.abs(g.dx) > w * 0.3 || Math.abs(g.vx) > 0.6) advance(Math.sign(g.dx || g.vx) || 1);
      else {
        Animated.parallel([
          Animated.spring(dx, { toValue: 0, useNativeDriver: true, speed: 14, bounciness: 4 }),
          Animated.spring(lift, { toValue: 0, useNativeDriver: true, speed: 14, bounciness: 0 }),
        ]).start();
      }
    },
  })).current;

  const tilt = isReduceMotion() ? '0deg' : dx.interpolate({
    inputRange: [-300, 0, 300], outputRange: ['-8deg', '0deg', '8deg'], extrapolate: 'clamp',
  });
  const turn = isReduceMotion() ? '0deg' : dx.interpolate({
    inputRange: [-300, 0, 300], outputRange: ['10deg', '0deg', '-10deg'], extrapolate: 'clamp',
  });

  const layers = [];
  for (let d = Math.min(BEHIND, items.length - 1); d >= 0; d--) {
    const i = (index + d) % items.length;
    const isTop = d === 0;
    // Cards behind move one step forward as `lift` goes 0 → 1.
    const scale = lift.interpolate({ inputRange: [0, 1], outputRange: [1 - d * STEP_SCALE, 1 - Math.max(d - 1, 0) * STEP_SCALE] });
    const translateY = lift.interpolate({ inputRange: [0, 1], outputRange: [d * STEP_Y, Math.max(d - 1, 0) * STEP_Y] });
    const transform = isTop
      ? [{ perspective: 900 }, { translateX: dx }, { rotateZ: tilt }, { rotateY: turn }]
      : [{ perspective: 900 }, { translateY }, { scale }, { rotateX: `${d * 4}deg` }];
    layers.push(
      <Animated.View
        key={`${i}-${d}`}
        {...(isTop ? pan.panHandlers : {})}
        onLayout={isTop ? e => setHeight(h => Math.max(h, e.nativeEvent.layout.height)) : undefined}
        style={{ position: 'absolute', left: 0, right: 0, top: 0, opacity: isTop ? 1 : 1 - d * 0.18, transform }}
        accessible={isTop}
        accessibilityLabel={isTop ? label?.(i) : undefined}
        accessibilityActions={isTop ? [{ name: 'increment' }] : undefined}
        onAccessibilityAction={isTop ? () => advance(1) : undefined}
        importantForAccessibility={isTop ? 'yes' : 'no-hide-descendants'}
      >
        {renderCard(items[i], i)}
      </Animated.View>,
    );
  }

  return (
    <View
      onLayout={e => { widthRef.current = e.nativeEvent.layout.width; setWidth(e.nativeEvent.layout.width); }}
      style={{ height: (height || 140) + BEHIND * STEP_Y }}
    >
      {width > 0 ? layers : null}
    </View>
  );
}
