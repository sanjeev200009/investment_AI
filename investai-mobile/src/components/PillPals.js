// src/components/PillPals.js
//
// The "Pill Pals": the Splash screen's four pastel pills drawn as cartoon
// characters (lime Markets, yellow Ask AI, lavender Learn, coral Alerts).
// Each illustration is a stack of same-size SVG layers so every character can
// bob on its own; motion is skipped when the OS asks for reduced motion.
import React, { useEffect, useRef } from 'react';
import { View, Animated, Easing, StyleSheet, AccessibilityInfo, useWindowDimensions } from 'react-native';
import Svg, { G, Rect, Circle, Ellipse, Path, Text as SvgText } from 'react-native-svg';
import { MaterialIcons } from '@expo/vector-icons';
import { palette, fonts } from '../theme/tokens';

const INK = palette.ink;
const LIME = palette.lime;
const YELLOW = palette.yellow;
const LAVENDER = palette.lavender;
const CORAL = palette.coral;
const line = { stroke: INK, strokeWidth: 2.5, strokeLinecap: 'round', strokeLinejoin: 'round' };
const thin = { stroke: INK, strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' };

const sparkle = (x, y, s) =>
  `M${x} ${y - s}Q${x} ${y} ${x + s} ${y}Q${x} ${y} ${x} ${y + s}Q${x} ${y} ${x - s} ${y}Q${x} ${y} ${x} ${y - s}Z`;

// Badge icons drawn around (40,160); callers translate them into place.
const BellIcon = ({ x, y }) => (
  <G transform={`translate(${x} ${y})`}>
    <Path d="M34 163V158a6 6 0 0 1 12 0V163l2 2H32Z" fill="none" {...thin} strokeWidth={1.8} />
    <Circle cx={40} cy={168} r={1.6} fill={INK} />
  </G>
);

function Hero({ viewBox, layers, label, maxWidth = 360 }) {
  const { width: screenW } = useWindowDimensions();
  const width = Math.min(screenW - 40, maxWidth);
  const [, , vw, vh] = viewBox.split(' ').map(Number);
  const height = (width * vh) / vw;
  const anims = useRef(layers.map(() => new Animated.Value(0))).current;

  useEffect(() => {
    let loops = [];
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled().then((reduce) => {
      if (reduce || cancelled) return;
      loops = layers.filter((l) => l.bob).map((l) => {
        const v = anims[layers.indexOf(l)];
        const ease = Easing.inOut(Easing.sin);
        const loop = Animated.loop(Animated.sequence([
          Animated.timing(v, { toValue: 1, duration: l.bob, easing: ease, useNativeDriver: true }),
          Animated.timing(v, { toValue: 0, duration: l.bob, easing: ease, useNativeDriver: true }),
        ]));
        loop.start();
        return loop;
      });
    });
    return () => { cancelled = true; loops.forEach((l) => l.stop()); };
  }, [anims, layers]);

  return (
    <View accessible accessibilityRole="image" accessibilityLabel={label} style={{ width, height, alignSelf: 'center' }}>
      {layers.map((l, i) => (
        <Animated.View
          key={i}
          pointerEvents="none"
          style={[StyleSheet.absoluteFill, l.bob ? {
            transform: [{ translateY: anims[i].interpolate({ inputRange: [0, 1], outputRange: [0, -6] }) }],
          } : null]}
        >
          <Svg width={width} height={height} viewBox={viewBox}>{l.draw}</Svg>
        </Animated.View>
      ))}
    </View>
  );
}

// ── Login: yellow Ask AI pal with a rising-chart phone, lime Markets pal with a key ──
const LOGIN_LAYERS = [
  {
    draw: (
      <G>
        <Circle cx={180} cy={160} r={120} fill="#FFFFFF" fillOpacity={0.55} />
        <Circle cx={180} cy={160} r={138} fill="none" stroke={INK} strokeOpacity={0.14} strokeWidth={1.5} strokeDasharray="3 7" />
        <Ellipse cx={84} cy={273} rx={48} ry={7} fill={INK} fillOpacity={0.1} />
        <Ellipse cx={275} cy={273} rx={40} ry={6} fill={INK} fillOpacity={0.1} />
        <Path d={sparkle(140, 60, 9)} fill={YELLOW} {...thin} />
        <Path d={sparkle(228, 92, 7)} fill={LAVENDER} {...thin} />
        <Path d={sparkle(346, 212, 7)} fill={YELLOW} {...thin} />
        <Path d={sparkle(24, 236, 6)} fill={LIME} {...thin} />
      </G>
    ),
  },
  {
    bob: 1600,
    draw: (
      <G>
        <Rect x={14} y={30} width={78} height={38} rx={19} fill={CORAL} {...line} />
        <Circle cx={33} cy={49} r={12} fill="#FFFFFF" {...thin} />
        <BellIcon x={-7} y={-111} />
        <Rect x={51} y={43} width={30} height={4.5} rx={2.25} fill={palette.coralInk} />
        <Rect x={51} y={52} width={19} height={4.5} rx={2.25} fill={palette.coralInk} fillOpacity={0.45} />
      </G>
    ),
  },
  {
    bob: 1900,
    draw: (
      <G>
        <Circle cx={295} cy={49} r={22} fill={INK} />
        <Circle cx={292} cy={46} r={22} fill={YELLOW} {...line} />
        <Circle cx={292} cy={46} r={15} fill="none" stroke={INK} strokeWidth={1.5} strokeDasharray="2 3" />
        <SvgText x={292} y={51} textAnchor="middle" fontFamily={fonts.medium} fontSize={13} fill={palette.yellowInk}>Rs</SvgText>
      </G>
    ),
  },
  {
    bob: 2100,
    draw: (
      <G>
        <Path d="M46 170C26 160 16 140 18 118" fill="none" {...line} />
        <Circle cx={18} cy={110} r={9} fill={YELLOW} {...line} />
        <Path d="M8 96l-4-6M18 92v-8M28 96l4-6" fill="none" {...thin} />
        <Rect x={44} y={86} width={80} height={184} rx={40} fill={YELLOW} {...line} />
        <Ellipse cx={72} cy={128} rx={5} ry={6.5} fill={INK} />
        <Ellipse cx={96} cy={128} rx={5} ry={6.5} fill={INK} />
        <Circle cx={74} cy={125.5} r={1.8} fill="#FFFFFF" />
        <Circle cx={98} cy={125.5} r={1.8} fill="#FFFFFF" />
        <Circle cx={63} cy={142} r={6} fill={CORAL} fillOpacity={0.75} />
        <Circle cx={105} cy={142} r={6} fill={CORAL} fillOpacity={0.75} />
        <Path d="M75 141Q84 153 93 141Z" fill={INK} {...thin} />
        <Circle cx={84} cy={200} r={18} fill="#FFFFFF" {...thin} />
        <Path d={sparkle(84, 200, 10)} fill="none" {...thin} />
        <Path d={sparkle(93, 191, 3.5)} fill={INK} />
        <Path d="M122 176C136 178 144 172 150 164" fill="none" {...line} />
        <G transform="rotate(8 187 152)">
          <Rect x={158} y={100} width={66} height={112} rx={13} fill={INK} />
          <Rect x={154} y={96} width={66} height={112} rx={13} fill="#FFFFFF" {...line} />
          <Rect x={176} y={103} width={22} height={4} rx={2} fill={INK} />
          <Rect x={164} y={118} width={30} height={5} rx={2.5} fill={INK} fillOpacity={0.85} />
          <Rect x={164} y={127} width={20} height={4} rx={2} fill={INK} fillOpacity={0.3} />
          <Rect x={162} y={140} width={50} height={46} rx={8} fill={LIME} fillOpacity={0.5} />
          <Path d="M166 178L176 168L184 172L196 154L208 146" fill="none" {...line} stroke={palette.limeInk} strokeWidth={3} />
          <Path d="M201 144L209 145L207 153" fill="none" {...line} stroke={palette.limeInk} strokeWidth={3} />
        </G>
        <Circle cx={152} cy={164} r={9} fill={YELLOW} {...line} />
      </G>
    ),
  },
  {
    bob: 1800,
    draw: (
      <G>
        <Rect x={240} y={132} width={70} height={138} rx={35} fill={LIME} {...line} />
        <Ellipse cx={266} cy={170} rx={4.5} ry={6} fill={INK} />
        <Ellipse cx={286} cy={170} rx={4.5} ry={6} fill={INK} />
        <Circle cx={264.5} cy={167.5} r={1.6} fill="#FFFFFF" />
        <Circle cx={284.5} cy={167.5} r={1.6} fill="#FFFFFF" />
        <Circle cx={257} cy={183} r={5} fill={CORAL} fillOpacity={0.8} />
        <Circle cx={295} cy={183} r={5} fill={CORAL} fillOpacity={0.8} />
        <Path d="M268 182Q276 189 284 182" fill="none" {...line} />
        <Circle cx={275} cy={228} r={16} fill="#FFFFFF" {...thin} />
        <Path d="M265 234L271 226L277 230L285 220M280 219.5H285.5V225" fill="none" {...thin} strokeWidth={2.2} />
        <Path d="M308 190C326 184 334 168 332 152" fill="none" {...line} />
        <Rect x={328} y={90} width={8} height={42} rx={3} fill={YELLOW} {...line} />
        <Rect x={335} y={94} width={8} height={6} rx={1.5} fill={YELLOW} {...thin} />
        <Rect x={335} y={104} width={6} height={5} rx={1.5} fill={YELLOW} {...thin} />
        <Circle cx={332} cy={138} r={12} fill={YELLOW} {...line} />
        <Circle cx={332} cy={135} r={4} fill="#FFFFFF" {...thin} />
        <Circle cx={331} cy={151} r={8} fill={LIME} {...line} />
      </G>
    ),
  },
];

// ── Register: lavender Learn pal waters a coin pot that grows a chart; coral Alerts pal cheers ──
const REGISTER_LAYERS = [
  {
    draw: (
      <G>
        <Circle cx={180} cy={130} r={106} fill="#FFFFFF" fillOpacity={0.55} />
        <Circle cx={180} cy={130} r={122} fill="none" stroke={INK} strokeOpacity={0.14} strokeWidth={1.5} strokeDasharray="3 7" />
        <Ellipse cx={59} cy={223} rx={40} ry={6} fill={INK} fillOpacity={0.1} />
        <Ellipse cx={200} cy={223} rx={32} ry={5} fill={INK} fillOpacity={0.1} />
        <Ellipse cx={299} cy={223} rx={40} ry={6} fill={INK} fillOpacity={0.1} />
        <Path d={sparkle(20, 40, 6)} fill={LIME} {...thin} />
        <Path d={sparkle(120, 40, 8)} fill={YELLOW} {...thin} />
        <Path d={sparkle(166, 67, 7)} fill={YELLOW} {...thin} />
        <Path d={sparkle(232, 76, 6)} fill={LAVENDER} {...thin} />
        <Rect x={172} y={168} width={56} height={12} rx={6} fill={YELLOW} {...line} />
        <Path d="M177 180H223L218 213Q217 218 212 218H188Q183 218 182 213Z" fill={YELLOW} {...line} />
        <Circle cx={200} cy={198} r={11} fill="#FFFFFF" {...thin} strokeWidth={1.8} />
        <SvgText x={200} y={202} textAnchor="middle" fontFamily={fonts.medium} fontSize={10} fill={palette.yellowInk}>Rs</SvgText>
        <Path d="M200 168C200 150 198 138 200 121" fill="none" {...line} stroke={palette.limeInk} strokeWidth={3.5} />
        <Path d="M200 152C186 152 178 144 176 134C188 134 198 140 200 152Z" fill={LIME} {...thin} />
        <Path d="M200 142C214 142 222 134 224 124C212 124 202 130 200 142Z" fill={LIME} {...thin} />
        <Rect x={185} y={97} width={9} height={22} rx={3} fill={LAVENDER} {...thin} />
        <Rect x={196} y={86} width={9} height={33} rx={3} fill={YELLOW} {...thin} />
        <Rect x={207} y={72} width={9} height={47} rx={3} fill={LIME} {...thin} />
        <Path d="M177 88L193 70M185 69H194V78" fill="none" {...line} />
        <Ellipse cx={183} cy={112} rx={3} ry={4.5} fill={LAVENDER} stroke={INK} strokeWidth={1.5} />
        <Ellipse cx={178} cy={122} rx={3} ry={4.5} fill={LAVENDER} stroke={INK} strokeWidth={1.5} />
        <Ellipse cx={186} cy={126} rx={3} ry={4.5} fill={LAVENDER} stroke={INK} strokeWidth={1.5} />
      </G>
    ),
  },
  {
    bob: 1800,
    draw: (
      <G>
        <Rect x={24} y={74} width={70} height={146} rx={35} fill={LAVENDER} {...line} />
        <Ellipse cx={50} cy={110} rx={4.5} ry={6} fill={INK} />
        <Ellipse cx={70} cy={110} rx={4.5} ry={6} fill={INK} />
        <Circle cx={52} cy={107.5} r={1.6} fill="#FFFFFF" />
        <Circle cx={72} cy={107.5} r={1.6} fill="#FFFFFF" />
        <Circle cx={42} cy={123} r={5} fill={CORAL} fillOpacity={0.8} />
        <Circle cx={78} cy={123} r={5} fill={CORAL} fillOpacity={0.8} />
        <Path d="M53 122Q60 129 67 122" fill="none" {...line} />
        <Circle cx={59} cy={176} r={16} fill="#FFFFFF" {...thin} />
        <Path d="M50 168L59 170.5V185L50 182.5ZM68 168L59 170.5V185L68 182.5Z" fill="none" {...thin} strokeWidth={1.8} />
        <Path d="M92 140C104 140 112 134 116 126" fill="none" {...line} />
        <Path d="M114 98C114 84 144 84 144 98" fill="none" {...line} />
        <Path d="M150 110L172 98L177 105L152 122Z" fill="#FFFFFF" {...line} />
        <Rect x={108} y={98} width={42} height={32} rx={9} fill="#FFFFFF" {...line} />
        <Rect x={109.5} y={109} width={39} height={7} fill={CORAL} />
        <Circle cx={115} cy={126} r={8} fill={LAVENDER} {...line} />
      </G>
    ),
  },
  {
    bob: 1600,
    draw: (
      <G>
        <Rect x={270} y={52} width={9} height={9} rx={2} fill={LIME} {...thin} strokeWidth={1.8} transform="rotate(18 274 56)" />
        <Rect x={300} y={38} width={8} height={8} rx={2} fill={LAVENDER} {...thin} strokeWidth={1.8} transform="rotate(-24 304 42)" />
        <Rect x={328} y={56} width={9} height={9} rx={2} fill={YELLOW} {...thin} strokeWidth={1.8} transform="rotate(35 332 60)" />
        <Path d="M282 34q4-6 8 0t8 0" fill="none" {...thin} />
        <Path d="M268 140C256 126 252 110 256 96M330 140C342 126 346 110 342 96" fill="none" {...line} />
        <Circle cx={256} cy={90} r={8} fill={CORAL} {...line} />
        <Circle cx={342} cy={90} r={8} fill={CORAL} {...line} />
        <Rect x={264} y={86} width={70} height={134} rx={35} fill={CORAL} {...line} />
        <Path d="M285 120Q290 113 295 120M303 120Q308 113 313 120" fill="none" {...line} />
        <Circle cx={281} cy={131} r={5} fill={palette.badge} fillOpacity={0.55} />
        <Circle cx={317} cy={131} r={5} fill={palette.badge} fillOpacity={0.55} />
        <Path d="M291 129Q299 142 307 129Z" fill={INK} {...thin} />
        <Circle cx={299} cy={180} r={16} fill="#FFFFFF" {...thin} />
        <BellIcon x={259} y={20} />
      </G>
    ),
  },
];

export const LoginHero = ({ label }) => <Hero viewBox="0 0 358 290" layers={LOGIN_LAYERS} label={label} />;
export const RegisterHero = ({ label }) => <Hero viewBox="0 0 358 230" layers={REGISTER_LAYERS} label={label} maxWidth={320} />;

// ── One Pill Pal, for spots: empty states, success, other auth screens ──
// tone: lime | yellow | lavender | coral. mood: happy | joy | calm | oops.
// pose: rest | wave | cheer. badge: any MaterialIcons name, drawn on the belly.
const TONES = {
  lime: [LIME, palette.limeInk], yellow: [YELLOW, palette.yellowInk],
  lavender: [LAVENDER, palette.lavenderInk], coral: [CORAL, palette.coralInk],
};
const ARM_REST_L = 'M22 110C10 120 8 136 14 146';
const ARM_REST_R = 'M98 110C110 120 112 136 106 146';
const ARM_UP_L = 'M22 110C6 100 2 80 8 62';
const ARM_UP_R = 'M98 110C114 100 118 80 112 62';

export function PillPal({ tone = 'lavender', mood = 'happy', pose = 'rest', badge, size = 140, bob = true, confetti = false }) {
  const [fill, ink] = TONES[tone] || TONES.lavender;
  const width = (size * 120) / 220;
  const k = size / 220;
  const v = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!bob) return undefined;
    let loop;
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled().then((reduce) => {
      if (reduce || cancelled) return;
      const ease = Easing.inOut(Easing.sin);
      loop = Animated.loop(Animated.sequence([
        Animated.timing(v, { toValue: 1, duration: 1700, easing: ease, useNativeDriver: true }),
        Animated.timing(v, { toValue: 0, duration: 1700, easing: ease, useNativeDriver: true }),
      ]));
      loop.start();
    });
    return () => { cancelled = true; loop?.stop(); };
  }, [bob, v]);

  const left = pose === 'cheer' ? ARM_UP_L : ARM_REST_L;
  const right = pose === 'rest' ? ARM_REST_R : ARM_UP_R;
  const handL = pose === 'cheer' ? [8, 56] : [14, 150];
  const handR = pose === 'rest' ? [106, 150] : [112, 56];
  const closedEyes = mood === 'joy' || mood === 'calm';

  return (
    <Animated.View
      importantForAccessibility="no-hide-descendants"
      accessibilityElementsHidden
      style={{ width, height: size, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, -5] }) }] }}
    >
      <Svg width={width} height={size} viewBox="0 0 120 220">
        <Ellipse cx={60} cy={212} rx={38} ry={6} fill={INK} fillOpacity={0.1} />
        {confetti ? (
          <G>
            <Rect x={6} y={14} width={8} height={8} rx={2} fill={LIME} {...thin} strokeWidth={1.6} transform="rotate(20 10 18)" />
            <Rect x={100} y={8} width={8} height={8} rx={2} fill={YELLOW} {...thin} strokeWidth={1.6} transform="rotate(-25 104 12)" />
            <Rect x={52} y={0} width={7} height={7} rx={2} fill={CORAL} {...thin} strokeWidth={1.6} transform="rotate(35 55 3)" />
          </G>
        ) : null}
        <Path d={`${left}${right}`} fill="none" {...line} />
        {pose === 'wave' ? <Path d="M100 44l-4-6M112 40v-8" fill="none" {...thin} /> : null}
        <Rect x={20} y={20} width={80} height={180} rx={40} fill={fill} {...line} />
        {closedEyes ? (
          <Path d="M43 67Q48 60 53 67M67 67Q72 60 77 67" fill="none" {...line} />
        ) : (
          <G>
            <Ellipse cx={48} cy={66} rx={5} ry={6.5} fill={INK} />
            <Ellipse cx={72} cy={66} rx={5} ry={6.5} fill={INK} />
            <Circle cx={50} cy={63.5} r={1.8} fill="#FFFFFF" />
            <Circle cx={74} cy={63.5} r={1.8} fill="#FFFFFF" />
          </G>
        )}
        <Circle cx={39} cy={80} r={6} fill={tone === 'coral' ? palette.badge : CORAL} fillOpacity={tone === 'coral' ? 0.55 : 0.8} />
        <Circle cx={81} cy={80} r={6} fill={tone === 'coral' ? palette.badge : CORAL} fillOpacity={tone === 'coral' ? 0.55 : 0.8} />
        {mood === 'joy' ? <Path d="M51 79Q60 91 69 79Z" fill={INK} {...thin} /> : null}
        {mood === 'happy' || mood === 'calm' ? <Path d="M51 80Q60 89 69 80" fill="none" {...line} /> : null}
        {mood === 'oops' ? (
          <G>
            <Circle cx={60} cy={84} r={4.5} fill={INK} />
            <Path d="M92 40Q96 48 92 52Q88 48 92 40Z" fill="#FFFFFF" {...thin} strokeWidth={1.6} />
          </G>
        ) : null}
        <Circle cx={handL[0]} cy={handL[1]} r={8} fill={fill} {...line} />
        <Circle cx={handR[0]} cy={handR[1]} r={8} fill={fill} {...line} />
        {badge ? <Circle cx={60} cy={140} r={20} fill="#FFFFFF" {...thin} /> : null}
      </Svg>
      {badge ? (
        <View style={{ position: 'absolute', left: 40 * k, top: 120 * k, width: 40 * k, height: 40 * k, alignItems: 'center', justifyContent: 'center' }}>
          <MaterialIcons name={badge} size={22 * k} color={ink} />
        </View>
      ) : null}
    </Animated.View>
  );
}

// ── Loader: three pastel pills bobbing in turn ──
export function PillLoader({ label }) {
  const vals = useRef([0, 1, 2].map(() => new Animated.Value(0))).current;
  useEffect(() => {
    const ease = Easing.inOut(Easing.sin);
    const loop = Animated.loop(Animated.stagger(140, vals.map((v) => Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 320, easing: ease, useNativeDriver: true }),
      Animated.timing(v, { toValue: 0, duration: 320, easing: ease, useNativeDriver: true }),
    ]))));
    loop.start();
    return () => loop.stop();
  }, [vals]);
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel={label}
      style={{ flexDirection: 'row', gap: 8, alignSelf: 'center', marginVertical: 32, height: 44, alignItems: 'flex-end' }}>
      {[LIME, YELLOW, LAVENDER].map((c, i) => (
        <Animated.View key={c} style={{
          width: 14, height: 30, borderRadius: 7, backgroundColor: c, borderWidth: 2, borderColor: INK,
          transform: [{ translateY: vals[i].interpolate({ inputRange: [0, 1], outputRange: [0, -12] }) }],
        }} />
      ))}
    </View>
  );
}
