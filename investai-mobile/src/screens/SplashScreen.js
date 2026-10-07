// src/screens/SplashScreen.js — v2 "Soft pastel" splash.
//
// Four pastel pills with faces (Markets, Ask AI, Learn, Alerts) over the
// gradient, a light-weight headline, and a black swipe-to-start pill. Also
// rendered by AppNavigator, without a navigator, while the saved session
// restores; a completed swipe then does nothing until the stack swaps in.
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, Animated, PanResponder, Pressable, Easing } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import Svg, { Circle, Ellipse, Path } from 'react-native-svg';
import { isReduceMotion } from '../theme/motion';
import { Screen, IconCircle, Chip, accent } from '../components/ui';
import { palette, fonts, radii } from '../theme/tokens';
import { useT, useLanguageStore } from '../store/languageStore';
import { LANGUAGES } from '../i18n/translations';

const PILLS = [
    { tone: 'lime', icon: 'show-chart', labelKey: 'splash_pill_markets', offset: 0 },
    { tone: 'yellow', icon: 'auto-awesome', labelKey: 'splash_pill_ai', offset: 60 },
    { tone: 'lavender', icon: 'menu-book', labelKey: 'splash_pill_learn', offset: 18 },
    { tone: 'coral', icon: 'notifications-none', labelKey: 'splash_pill_alerts', offset: 90 },
];

// A small face for each capsule: blinks now and then, beams when tapped.
function PillFace({ tone, happy }) {
    const [blink, setBlink] = useState(false);
    useEffect(() => {
        if (isReduceMotion()) return undefined;
        let timer;
        const schedule = () => {
            timer = setTimeout(() => {
                setBlink(true);
                timer = setTimeout(() => { setBlink(false); schedule(); }, 140);
            }, 2400 + Math.random() * 3200);
        };
        schedule();
        return () => clearTimeout(timer);
    }, []);
    const ink = palette.ink;
    const cheek = tone === 'coral' ? palette.badge : palette.coral;
    const closed = blink || happy;
    return (
        <Svg width={44} height={30} viewBox="0 0 44 30">
            {closed ? (
                <Path d={happy ? 'M10 11Q14 6 18 11M26 11Q30 6 34 11' : 'M10 10H18M26 10H34'} stroke={ink} strokeWidth={2.2} strokeLinecap="round" fill="none" />
            ) : (
                <>
                    <Ellipse cx={14} cy={10} rx={3.2} ry={4} fill={ink} />
                    <Ellipse cx={30} cy={10} rx={3.2} ry={4} fill={ink} />
                    <Circle cx={15.2} cy={8.4} r={1.1} fill="#FFFFFF" />
                    <Circle cx={31.2} cy={8.4} r={1.1} fill="#FFFFFF" />
                </>
            )}
            <Circle cx={7} cy={18} r={3.4} fill={cheek} fillOpacity={0.7} />
            <Circle cx={37} cy={18} r={3.4} fill={cheek} fillOpacity={0.7} />
            {happy
                ? <Path d="M16 18Q22 27 28 18Z" fill={ink} />
                : <Path d="M16 19Q22 24 28 19" stroke={ink} strokeWidth={2.2} strokeLinecap="round" fill="none" />}
        </Svg>
    );
}

const TRACK_PAD = 8;
const KNOB = 56;

export default function SplashScreen({ navigation }) {
    const { t, language } = useT();
    const setLanguage = useLanguageStore(state => state.setLanguage);
    const trackRef = useRef(0);
    const knobX = useRef(new Animated.Value(0)).current;
    // Capsules slide up from the bottom one by one; each one that lands pushes
    // its neighbour aside a little as it squeezes into place. No looping motion.
    // A tap lifts a capsule ("discover") and its neighbours lean away.
    const rise = useRef(PILLS.map(() => new Animated.Value(isReduceMotion() ? 1 : 0))).current;
    const push = useRef(PILLS.map(() => new Animated.Value(0))).current;
    const lift = useRef(PILLS.map(() => new Animated.Value(0))).current;
    const [happy, setHappy] = useState(-1);
    const done = useRef(false);

    const ease = Easing.out(Easing.cubic);
    const nudge = (i, dir) => {
        if (i < 0 || i >= PILLS.length) return;
        Animated.sequence([
            Animated.timing(push[i], { toValue: dir * 7, duration: 160, easing: ease, useNativeDriver: true }),
            Animated.timing(push[i], { toValue: 0, duration: 340, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        ]).start();
    };

    useEffect(() => {
        if (isReduceMotion()) return;
        rise.forEach((v, i) => Animated.timing(v, {
            toValue: 1, duration: 720, delay: 120 + i * 150, easing: ease, useNativeDriver: true,
        }).start(({ finished }) => { if (finished) nudge(i - 1, -1); }));
    }, [rise]);

    const discover = (i) => {
        setHappy(i);
        if (!isReduceMotion()) {
            Animated.sequence([
                Animated.timing(lift[i], { toValue: 1, duration: 260, easing: ease, useNativeDriver: true }),
                Animated.delay(600),
                Animated.timing(lift[i], { toValue: 0, duration: 420, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
            ]).start(() => setHappy(h => (h === i ? -1 : h)));
            nudge(i - 1, -1);
            nudge(i + 1, 1);
        } else {
            setTimeout(() => setHappy(h => (h === i ? -1 : h)), 900);
        }
    };

    const maxX = () => Math.max(trackRef.current - KNOB - TRACK_PAD * 2, 0);

    const finish = () => {
        if (done.current) return;
        done.current = true;
        Animated.timing(knobX, { toValue: maxX(), duration: 180, useNativeDriver: true }).start(() => {
            navigation?.navigate('Login');
            setTimeout(() => { done.current = false; knobX.setValue(0); }, 600);
        });
    };

    const pan = useRef(PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderMove: (_, g) => knobX.setValue(Math.min(Math.max(g.dx, 0), maxX())),
        onPanResponderRelease: (_, g) => {
            if (g.dx > maxX() * 0.6) finish();
            else Animated.spring(knobX, { toValue: 0, useNativeDriver: true }).start();
        },
    })).current;

    return (
        <Screen scroll={false} edges={['top', 'bottom']} contentStyle={styles.content}>
            <View style={styles.brand}>
                <View style={styles.logo}><MaterialIcons name="trending-up" size={20} color="#FFFFFF" /></View>
                <Text style={styles.brandText}>InvestAI</Text>
            </View>

            {/* First thing a new user sees: pick the app language. */}
            <View style={styles.langs} accessibilityRole="radiogroup" accessibilityLabel={t('profile_language')}>
                {LANGUAGES.map(({ code, label }) => (
                    <Pressable
                        key={code}
                        onPress={() => setLanguage(code)}
                        accessibilityRole="radio"
                        accessibilityState={{ selected: language === code }}
                    >
                        <Chip label={label} selected={language === code} />
                    </Pressable>
                ))}
            </View>

            <View style={styles.pills} importantForAccessibility="no-hide-descendants">
                {PILLS.map((p, i) => {
                    const a = accent(p.tone);
                    const translateY = Animated.add(
                        rise[i].interpolate({ inputRange: [0, 1], outputRange: [520, 0] }),
                        lift[i].interpolate({ inputRange: [0, 1], outputRange: [0, -18] }),
                    );
                    // Each capsule arrives slightly turned and straightens as it lands.
                    const turn = rise[i].interpolate({ inputRange: [0, 1], outputRange: [i % 2 ? '7deg' : '-7deg', '0deg'] });
                    return (
                        <Pressable key={p.tone} onPress={() => discover(i)} accessible={false}>
                            <Animated.View style={[styles.pill, {
                                backgroundColor: a.bg, marginTop: p.offset,
                                transform: [{ translateX: push[i] }, { translateY }, { rotateZ: turn }],
                            }]}>
                                <View style={{ alignItems: 'center', gap: 8 }}>
                                    <IconCircle icon={p.icon} color={a.ink} borderColor="rgba(0,0,0,0.15)" size={52} />
                                    <PillFace tone={p.tone} happy={happy === i} />
                                </View>
                                <Text style={[styles.pillLabel, { color: a.ink }]}>{t(p.labelKey)}</Text>
                            </Animated.View>
                        </Pressable>
                    );
                })}
            </View>

            <View style={{ gap: 12 }}>
                <Text style={styles.title} accessibilityRole="header">
                    {t('splash_title_1')}{'\n'}
                    <Text style={styles.titleLight}>{t('splash_title_2')}</Text>
                </Text>
                <Text style={styles.subtitle}>{t('splash_subtitle')}</Text>
            </View>

            <View
                style={styles.track}
                onLayout={(e) => { trackRef.current = e.nativeEvent.layout.width; }}
                accessible
                accessibilityRole="button"
                accessibilityLabel={t('splash_swipe')}
                accessibilityActions={[{ name: 'activate' }]}
                onAccessibilityAction={finish}
            >
                <Text style={styles.trackText}>{t('splash_swipe')}</Text>
                <Animated.View {...pan.panHandlers} style={[styles.knob, { transform: [{ translateX: knobX }] }]}>
                    <MaterialIcons name="arrow-forward" size={22} color={palette.ink} />
                </Animated.View>
            </View>
            <Text style={styles.footnote}>{t('splash_disclaimer')}</Text>
        </Screen>
    );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
    content: { paddingTop: 24, paddingBottom: 16, gap: 20, justifyContent: 'space-between' },
    brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
    logo: { width: 40, height: 40, borderRadius: radii.full, backgroundColor: palette.ink, alignItems: 'center', justifyContent: 'center' },
    brandText: { ...text, fontFamily: fonts.medium, fontSize: 20 },
    langs: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
    pills: { flex: 1, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 12, maxHeight: 380 },
    pill: {
        width: 72, height: 240, borderRadius: radii.full, paddingVertical: 10,
        alignItems: 'center', justifyContent: 'space-between',
    },
    pillLabel: { fontFamily: fonts.medium, fontSize: 14, transform: [{ rotate: '-90deg' }], width: 120, textAlign: 'center', marginBottom: 50 },
    title: { ...text, fontSize: 44, lineHeight: 46, letterSpacing: -1.5 },
    titleLight: { fontFamily: fonts.light, color: palette.muted },
    subtitle: { ...text, fontSize: 16, lineHeight: 23, color: palette.muted, maxWidth: 320 },
    track: {
        height: 72, borderRadius: radii.full, backgroundColor: palette.ink, padding: TRACK_PAD,
        justifyContent: 'center',
    },
    trackText: { ...text, color: '#FFFFFF', fontSize: 17, textAlign: 'center', paddingLeft: KNOB },
    knob: {
        position: 'absolute', left: TRACK_PAD, width: KNOB, height: KNOB, borderRadius: radii.full,
        backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center',
    },
    footnote: { ...text, fontSize: 12, color: palette.faint, textAlign: 'center' },
});
