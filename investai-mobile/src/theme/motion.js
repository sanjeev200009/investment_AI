// src/theme/motion.js
//
// One motion language for the whole app, matching the floating Pill Pals:
// soft, springy settles instead of hard slides.
//
//   stackMotion   push/pop: the new screen glides in with a slight lift
//                 (scale 0.96 → 1, fade) while the one behind drifts back,
//                 shrinks and dims.
//   revealMotion  big moments (success, entering the app): fade + grow.
//   tabMotion     tab switches: cross-fade with a small rise.
//
// Every interpolator falls back to a plain fade when the OS asks for reduced
// motion.
import { Animated, Easing, AccessibilityInfo, InteractionManager } from 'react-native';

let reduceMotion = false;
AccessibilityInfo.isReduceMotionEnabled().then((v) => { reduceMotion = !!v; }).catch(() => {});
AccessibilityInfo.addEventListener?.('reduceMotionChanged', (v) => { reduceMotion = !!v; });
export const isReduceMotion = () => reduceMotion;

// Fast start, long gentle settle.
export const EASE_OUT = Easing.bezier(0.22, 1, 0.36, 1);

const spec = (duration) => ({ animation: 'timing', config: { duration, easing: EASE_OUT } });
const transitionSpec = { open: spec(420), close: spec(320) };

function softLift({ current, next, layouts }) {
  if (reduceMotion) return { cardStyle: { opacity: current.progress } };
  const w = layouts.screen.width;
  const translate = [current.progress.interpolate({ inputRange: [0, 1], outputRange: [w * 0.22, 0] })];
  const scale = [current.progress.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] })];
  if (next) {
    translate.push(next.progress.interpolate({ inputRange: [0, 1], outputRange: [0, -w * 0.08] }));
    scale.push(next.progress.interpolate({ inputRange: [0, 1], outputRange: [1, 0.94] }));
  }
  return {
    cardStyle: {
      opacity: current.progress.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0, 1, 1] }),
      transform: [
        { translateX: translate.length > 1 ? Animated.add(translate[0], translate[1]) : translate[0] },
        { scale: scale.length > 1 ? Animated.multiply(scale[0], scale[1]) : scale[0] },
      ],
    },
    overlayStyle: {
      opacity: current.progress.interpolate({ inputRange: [0, 1], outputRange: [0, 0.12] }),
    },
  };
}

function reveal({ current }) {
  if (reduceMotion) return { cardStyle: { opacity: current.progress } };
  return {
    cardStyle: {
      opacity: current.progress,
      transform: [{ scale: current.progress.interpolate({ inputRange: [0, 1], outputRange: [0.92, 1] }) }],
    },
  };
}

// Stock detail: the page lifts toward you from a slight 3D tilt, as if the
// tapped card rose off the list and opened.
function cardLift({ current, layouts }) {
  if (reduceMotion) return { cardStyle: { opacity: current.progress } };
  const p = current.progress;
  return {
    cardStyle: {
      opacity: p.interpolate({ inputRange: [0, 0.35, 1], outputRange: [0, 1, 1] }),
      transform: [
        { perspective: 1000 },
        { translateY: p.interpolate({ inputRange: [0, 1], outputRange: [layouts.screen.height * 0.1, 0] }) },
        { rotateX: p.interpolate({ inputRange: [0, 1], outputRange: ['10deg', '0deg'] }) },
        { scale: p.interpolate({ inputRange: [0, 1], outputRange: [0.9, 1] }) },
      ],
    },
    overlayStyle: { opacity: p.interpolate({ inputRange: [0, 1], outputRange: [0, 0.18] }) },
  };
}

export const cardLiftMotion = {
  cardStyleInterpolator: cardLift,
  transitionSpec: { open: spec(480), close: spec(340) },
  gestureDirection: 'vertical',
};

export const stackMotion = {
  headerShown: false,
  gestureEnabled: true,
  gestureDirection: 'horizontal',
  cardOverlayEnabled: true,
  cardStyleInterpolator: softLift,
  transitionSpec,
};

export const revealMotion = {
  cardStyleInterpolator: reveal,
  transitionSpec: { open: spec(520), close: spec(320) },
  gestureEnabled: false,
};

// Tab switches slide a short way in the direction of travel (progress runs
// -1 → 0 → 1 across the tab order) while cross-fading. freezeOnBlur stops
// hidden tabs re-rendering behind the visible one, which is what made switches
// stutter on mid-range phones.
export const tabMotion = {
  headerShown: false,
  freezeOnBlur: true,
  animation: 'shift',
  transitionSpec: spec(260),
  sceneStyleInterpolator: ({ current }) => ({
    sceneStyle: {
      opacity: current.progress.interpolate({ inputRange: [-1, -0.4, 0, 0.4, 1], outputRange: [0, 0.6, 1, 0.6, 0] }),
      transform: reduceMotion ? [] : [{
        translateX: current.progress.interpolate({ inputRange: [-1, 0, 1], outputRange: [-36, 0, 36] }),
      }],
    },
  }),
};

// Run `fn` once the screen has finished arriving: after the tab switch (260 ms,
// which registers no interaction) and after any stack transition (which does).
// Heavy re-renders and charts started mid-transition are what made switches
// stutter. Returns a cancel function, so it fits useEffect / useFocusEffect.
export function afterTransition(fn) {
  let task;
  const timer = setTimeout(() => { task = InteractionManager.runAfterInteractions(fn); }, 280);
  return () => { clearTimeout(timer); task?.cancel(); };
}
