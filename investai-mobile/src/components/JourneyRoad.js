// src/components/JourneyRoad.js
//
// The onboarding quiz as a road: a switchback that winds up the card in three
// rows, one stop per question, with a Pill Pal walking to the current stop.
// Geometry is computed, not measured, so the Pal's path (translate X/Y
// interpolated through the stops and the turns) runs on the native driver.
// Reduced motion: the Pal jumps to its stop.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Animated, Easing, StyleSheet } from 'react-native';
import Svg, { Path, Circle, G } from 'react-native-svg';
import { PillPal } from './PillPals';
import { palette } from '../theme/tokens';
import { isReduceMotion } from '../theme/motion';

const ROWS = 3;
const PAL = 54;                       // PillPal height on the road
const PAL_W = (PAL * 120) / 220;
const TURN_SAMPLES = [0.25, 0.5, 0.75];

function geometry(width, height, total) {
  const perRow = Math.ceil(total / ROWS);
  const r = (height - 22 - (PAL + 6)) / ((ROWS - 1) * 2);   // turn radius
  const xL = 22 + r * 0.6;
  const xR = width - 22 - r * 0.6;
  const rowLen = xR - xL;
  const rowY = (k) => height - 22 - k * 2 * r;

  const stop = (i) => {
    const k = Math.floor(i / perRow);
    const t = (i % perRow) / (perRow - 1);
    return { x: k % 2 ? xR - t * rowLen : xL + t * rowLen, y: rowY(k) };
  };
  const stops = Array.from({ length: total }, (_, i) => stop(i));

  // Interpolation points: every stop, plus a few on each semicircular turn.
  const input = [];
  const xs = [];
  const ys = [];
  stops.forEach((p, i) => {
    input.push(i); xs.push(p.x); ys.push(p.y);
    if ((i + 1) % perRow === 0 && i < total - 1) {
      const k = Math.floor(i / perRow);
      const right = k % 2 === 0;
      const cx = right ? xR : xL;
      const cy = rowY(k) - r;
      TURN_SAMPLES.forEach((f) => {
        const th = right ? Math.PI / 2 - f * Math.PI : Math.PI / 2 + f * Math.PI;
        input.push(i + f); xs.push(cx + r * Math.cos(th)); ys.push(cy + r * Math.sin(th));
      });
    }
  });

  // Road path, from a little before the first stop to a little past the last.
  const startX = xL - r * 0.5;
  let d = `M${startX} ${rowY(0)}`;
  const pre = xL - startX;
  const along = [];               // distance along the road to each stop
  for (let k = 0; k < ROWS; k++) {
    const first = stops[k * perRow];
    const last = stops[Math.min((k + 1) * perRow, total) - 1];
    if (!first) break;
    d += ` L${last.x} ${last.y}`;
    const next = stops[(k + 1) * perRow];
    if (next) d += ` A${r} ${r} 0 0 ${k % 2 ? 1 : 0} ${next.x} ${next.y}`;
  }
  const end = stops[total - 1];
  const lastRowRight = Math.floor((total - 1) / perRow) % 2 === 0;
  const endX = end.x + (lastRowRight ? r * 0.5 : -r * 0.5);
  d += ` L${endX} ${end.y}`;
  for (let i = 0; i < total; i++) {
    const k = Math.floor(i / perRow);
    along.push(pre + k * (rowLen + Math.PI * r) + ((i % perRow) / (perRow - 1)) * rowLen);
  }
  const length = along[total - 1] + r * 0.5;

  return { stops, input, xs, ys, d, along, length, flag: { x: endX, y: end.y } };
}

/**
 * total     number of stops
 * current   index of the stop the Pal is on
 * kinds     per stop: 'profile' | 'knowledge'
 * results   per stop: true (right) | false (wrong) for answered knowledge stops
 * pal       PillPal props for the walker (tone, mood, pose, badge)
 */
export default function JourneyRoad({ total, current, kinds = [], results = {}, pal = {}, height = 210, label }) {
  const [width, setWidth] = useState(0);
  const g = useMemo(() => (width ? geometry(width, height, total) : null), [width, height, total]);
  const pos = useRef(new Animated.Value(current)).current;
  const hop = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isReduceMotion()) { pos.setValue(current); return undefined; }
    const step = Animated.sequence([
      Animated.timing(hop, { toValue: 1, duration: 110, easing: Easing.out(Easing.quad), useNativeDriver: true }),
      Animated.timing(hop, { toValue: 0, duration: 110, easing: Easing.in(Easing.quad), useNativeDriver: true }),
    ]);
    const walk = Animated.parallel([
      Animated.timing(pos, { toValue: current, duration: 720, easing: Easing.inOut(Easing.cubic), useNativeDriver: true }),
      Animated.sequence([step, step, step]),
    ]);
    walk.start();
    return () => walk.stop();
  }, [current, pos, hop]);

  return (
    <View
      style={[styles.wrap, { height }]}
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 1, max: total, now: current + 1 }}
    >
      {g ? (
        <>
          <Svg width={width} height={height}>
            <Path d={g.d} fill="none" stroke={palette.ink} strokeOpacity={0.08} strokeWidth={26} strokeLinecap="round" strokeLinejoin="round" />
            <Path d={g.d} fill="none" stroke="#FFFFFF" strokeWidth={22} strokeLinecap="round" strokeLinejoin="round" />
            <Path
              d={g.d} fill="none" stroke={palette.lime} strokeWidth={10} strokeLinecap="round"
              strokeDasharray={`${g.along[current]} ${g.length + 40}`}
            />
            <Path d={g.d} fill="none" stroke={palette.outline} strokeWidth={2} strokeDasharray="5 9" />
            {g.stops.map((p, i) => {
              const knowledge = kinds[i] === 'knowledge';
              const passed = i < current;
              let fill = knowledge ? palette.yellow : '#FFFFFF';
              if (passed) fill = knowledge ? (results[i] === false ? palette.coral : palette.lime) : palette.ink;
              return (
                <Circle
                  key={i} cx={p.x} cy={p.y} r={i === current ? 9 : knowledge ? 7.5 : 6}
                  fill={i === current ? '#FFFFFF' : fill}
                  stroke={palette.ink} strokeOpacity={passed || i === current ? 1 : 0.35}
                  strokeWidth={i === current ? 3 : 1.5}
                />
              );
            })}
            <G transform={`translate(${g.flag.x} ${g.flag.y})`}>
              <Path d="M0 0V-26" stroke={palette.ink} strokeWidth={2} strokeLinecap="round" />
              <Path d="M0 -26L14 -21L0 -16Z" fill={palette.coral} stroke={palette.ink} strokeWidth={1.5} strokeLinejoin="round" />
            </G>
          </Svg>
          <Animated.View
            pointerEvents="none"
            style={[styles.pal, {
              transform: [
                { translateX: pos.interpolate({ inputRange: g.input, outputRange: g.xs.map((x) => x - PAL_W / 2), extrapolate: 'clamp' }) },
                { translateY: pos.interpolate({ inputRange: g.input, outputRange: g.ys.map((y) => y - PAL + 8), extrapolate: 'clamp' }) },
                { translateY: hop.interpolate({ inputRange: [0, 1], outputRange: [0, -7] }) },
              ],
            }]}
          >
            <PillPal size={PAL} bob={false} {...pal} />
          </Animated.View>
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { width: '100%' },
  pal: { position: 'absolute', left: 0, top: 0 },
});
