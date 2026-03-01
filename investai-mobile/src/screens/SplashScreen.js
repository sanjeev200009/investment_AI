// src/screens/SplashScreen.js
// Uses React Native's built-in Animated API for full Expo Go compatibility
import React, { useEffect, useRef, useState } from 'react';
import {
    View, Text, StyleSheet, useWindowDimensions, StatusBar,
    useColorScheme, Animated, PanResponder, TouchableOpacity
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { colors, shadows } from '../theme/theme';

const BUTTON_WIDTH = 300;
const BUTTON_HEIGHT = 70;
const THUMB_SIZE = 56;
const SWIPE_RANGE = BUTTON_WIDTH - THUMB_SIZE - 16;

// ────────── Floating Coin ──────────
const FloatingCoin = ({ delay, style, children, size = 80, gradient }) => {
    const floatAnim = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        const anim = Animated.loop(
            Animated.sequence([
                Animated.timing(floatAnim, { toValue: 1, duration: 2800, useNativeDriver: true }),
                Animated.timing(floatAnim, { toValue: 0, duration: 2800, useNativeDriver: true }),
            ])
        );
        const t = setTimeout(() => anim.start(), delay);
        return () => { clearTimeout(t); anim.stop(); };
    }, []);

    const translateY = floatAnim.interpolate({ inputRange: [0, 1], outputRange: [0, -18] });
    const rotate = floatAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '6deg'] });

    return (
        <Animated.View style={[style, { transform: [{ translateY }, { rotate }] }]}>
            <LinearGradient colors={gradient} style={[styles.coin, { width: size, height: size, borderRadius: size / 2 }]} start={[0, 0]} end={[1, 1]}>
                {children}
            </LinearGradient>
        </Animated.View>
    );
};

// ────────── Main Screen ──────────
export default function SplashScreen({ navigation }) {
    const { width, height } = useWindowDimensions();
    const scheme = useColorScheme();
    const c = colors(scheme);

    const [showPopup, setShowPopup] = useState(false);
    const [swiped, setSwiped] = useState(false);

    // Animations
    const fadeIn = useRef(new Animated.Value(0)).current;
    const thumbX = useRef(new Animated.Value(0)).current;
    const trackColor = useRef(new Animated.Value(0)).current;
    const popupScale = useRef(new Animated.Value(0)).current;
    const popupAlpha = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        Animated.timing(fadeIn, { toValue: 1, duration: 900, useNativeDriver: false }).start();
    }, []);

    // Derived values
    const labelOpacity = thumbX.interpolate({ inputRange: [0, SWIPE_RANGE * 0.45], outputRange: [1, 0], extrapolate: 'clamp' });
    const trackBg = trackColor.interpolate({ inputRange: [0, 1], outputRange: [c.swipeBtn, scheme === 'dark' ? 'rgba(255,255,255,0.22)' : c.primaryLight] });

    const navigateNext = async () => {
        try {
            const token = await AsyncStorage.getItem('token');
            // Navigate to Home (MainTab) as requested, or Auth if strictly needed later
            navigation.replace('MainTab');
        } catch { navigation.replace('MainTab'); }
    };

    const onSwipeComplete = () => {
        if (swiped) return;
        setSwiped(true);
        Animated.spring(thumbX, { toValue: SWIPE_RANGE, useNativeDriver: false }).start();
        setShowPopup(true);
        Animated.parallel([
            Animated.spring(popupScale, { toValue: 1, friction: 7, tension: 120, useNativeDriver: true }),
            Animated.timing(popupAlpha, { toValue: 1, duration: 350, useNativeDriver: true }),
        ]).start();
        setTimeout(navigateNext, 2200);
    };

    const panResponder = PanResponder.create({
        onStartShouldSetPanResponder: () => !swiped,
        onMoveShouldSetPanResponder: () => !swiped,
        onPanResponderMove: (_, gs) => {
            const x = Math.max(0, Math.min(SWIPE_RANGE, gs.dx));
            thumbX.setValue(x);
            trackColor.setValue(x / SWIPE_RANGE);
        },
        onPanResponderRelease: (_, gs) => {
            if (gs.dx > SWIPE_RANGE * 0.78) {
                onSwipeComplete();
            } else {
                Animated.spring(thumbX, { toValue: 0, useNativeDriver: false }).start();
                Animated.timing(trackColor, { toValue: 0, duration: 250, useNativeDriver: false }).start();
            }
        },
    });

    return (
        <View style={styles.root}>
            <StatusBar barStyle={scheme === 'dark' ? 'light-content' : 'dark-content'} translucent backgroundColor="transparent" />
            <LinearGradient colors={c.gradient} style={styles.bg}>

                {/* ── Curved header ── */}
                <View style={styles.curvedWrap}>
                    <View style={[styles.curvedTop, { width: width * 0.85, height: height * 0.5, backgroundColor: c.curved }]}>
                        <View style={styles.coinWrapper}>
                            <FloatingCoin delay={0} size={128} style={styles.centerCoin} gradient={c.coinGradient}><Ionicons name="trending-up" size={68} color="#735A00" /></FloatingCoin>
                            <FloatingCoin delay={900} size={96} style={styles.topRightCoin} gradient={c.coinGradient}><MaterialCommunityIcons name="bitcoin" size={56} color="#735A00" /></FloatingCoin>
                            <FloatingCoin delay={1800} size={96} style={styles.bottomLeftCoin} gradient={c.coinGradient}><Ionicons name="stats-chart" size={56} color="#735A00" /></FloatingCoin>
                            <FloatingCoin delay={1350} size={76} style={styles.sideCoin} gradient={c.coinGradient}><Ionicons name="card" size={46} color="#735A00" /></FloatingCoin>
                        </View>
                    </View>
                </View>

                {/* ── Main content ── */}
                <Animated.View style={[styles.content, { opacity: fadeIn }]}>
                    <View style={styles.textWrap}>
                        <Text style={[styles.title, { color: c.textPrimary, fontSize: width > 400 ? 36 : 30 }]}>
                            The Most Trusted AI Investment Assistant
                        </Text>
                        <Text style={[styles.subtitle, { color: scheme === 'dark' ? 'rgba(255,255,255,0.68)' : 'rgba(3,4,94,0.6)' }]}>
                            Navigate the markets with intelligent insights.
                        </Text>
                    </View>

                    {/* ── Swipe button ── */}
                    <View style={styles.btnCenter}>
                        <Animated.View style={[styles.track, { width: BUTTON_WIDTH, backgroundColor: trackBg }]}>
                            <Animated.Text style={[styles.trackLabel, { opacity: labelOpacity }]}>
                                Swipe to get started
                            </Animated.Text>
                            <Animated.View style={[styles.thumbWrap, { transform: [{ translateX: thumbX }] }]} {...panResponder.panHandlers}>
                                <LinearGradient colors={scheme === 'dark' ? ['#1976D2', '#0D47A1'] : ['#FFFFFF', '#E3F0FF']} style={styles.thumb} start={[0, 0]} end={[1, 1]}>
                                    <Ionicons name="chevron-forward" size={28} color={scheme === 'dark' ? '#FFF' : c.primary} />
                                </LinearGradient>
                            </Animated.View>
                        </Animated.View>
                    </View>
                </Animated.View>

                {/* ── Success popup ── */}
                {showPopup && (
                    <View style={[StyleSheet.absoluteFill, { zIndex: 9999 }]}>
                        <View style={styles.overlay} />
                        <Animated.View style={[styles.popup, { opacity: popupAlpha, transform: [{ scale: popupScale }] }]}>
                            <LinearGradient colors={['#1565C0', '#0D47A1']} style={styles.popupInner} start={[0, 0]} end={[1, 1]}>
                                <View style={styles.checkRing}>
                                    <Ionicons name="sparkles" size={44} color="#1565C0" />
                                </View>
                                <Text style={styles.popupTitle}>Welcome to InvestAI</Text>
                                <Text style={styles.popupSub}>Your smart companion for wealth growth.</Text>
                            </LinearGradient>
                        </Animated.View>
                    </View>
                )}

                <View style={[styles.pill, { backgroundColor: scheme === 'dark' ? 'rgba(255,255,255,0.18)' : 'rgba(3,4,94,0.1)' }]} />
            </LinearGradient>
        </View>
    );
}

const styles = StyleSheet.create({
    root: { flex: 1 },
    bg: { flex: 1 },

    curvedWrap: { position: 'absolute', top: 0, left: 0, width: '100%', zIndex: 5 },
    curvedTop: {
        borderBottomRightRadius: 200,
        overflow: 'hidden',
        justifyContent: 'center',
        alignItems: 'center',
        borderBottomWidth: 1,
        borderRightWidth: 1,
        borderColor: 'rgba(255,255,255,0.05)',
    },
    coinWrapper: { width: 250, height: 250, position: 'relative', justifyContent: 'center', alignItems: 'center' },
    coin: { justifyContent: 'center', alignItems: 'center', borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', elevation: 8, shadowColor: '#000', shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.25, shadowRadius: 8, boxShadow: '0 6 8 rgba(0, 0, 0, 0.25)' },
    centerCoin: { position: 'absolute', zIndex: 3 },
    topRightCoin: { position: 'absolute', top: -38, right: -18, zIndex: 2 },
    bottomLeftCoin: { position: 'absolute', bottom: -18, left: -38, zIndex: 2 },
    sideCoin: { position: 'absolute', top: 52, left: -68, zIndex: 2 },

    content: { flex: 1, justifyContent: 'flex-end', paddingHorizontal: 28, paddingBottom: 64, zIndex: 10 },
    textWrap: { marginBottom: 44 },
    title: { fontFamily: 'Roboto_800ExtraBold', lineHeight: 42, fontWeight: '800', letterSpacing: -0.8 },
    subtitle: { fontSize: 17, marginTop: 14, fontWeight: '500', lineHeight: 26, maxWidth: 310 },

    btnCenter: { alignItems: 'center' },
    track: {
        height: BUTTON_HEIGHT,
        borderRadius: 40,
        paddingHorizontal: 7,
        justifyContent: 'center',
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.12)',
    },
    trackLabel: {
        position: 'absolute',
        left: THUMB_SIZE + 22,
        color: '#FFF',
        fontSize: 15,
        fontWeight: '700',
        letterSpacing: 0.4,
    },
    thumbWrap: { width: THUMB_SIZE, height: THUMB_SIZE },
    thumb: { flex: 1, borderRadius: THUMB_SIZE / 2, justifyContent: 'center', alignItems: 'center', elevation: 6, shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.28, shadowRadius: 5, boxShadow: '0 4 5 rgba(0, 0, 0, 0.28)' },

    overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.58)' },
    popup: { position: 'absolute', top: '32%', alignSelf: 'center', width: '80%', borderRadius: 28, overflow: 'hidden', elevation: 22, ...shadows.card },
    popupInner: { padding: 32, alignItems: 'center' },
    checkRing: { width: 84, height: 84, borderRadius: 42, backgroundColor: '#FFF', justifyContent: 'center', alignItems: 'center', marginBottom: 18 },
    popupTitle: { fontSize: 22, color: '#FFF', fontFamily: 'Roboto_800ExtraBold', textAlign: 'center' },
    popupSub: { fontSize: 14, color: 'rgba(255,255,255,0.82)', marginTop: 10, fontWeight: '500', textAlign: 'center' },

    pill: { position: 'absolute', bottom: 14, alignSelf: 'center', width: 120, height: 5, borderRadius: 3 },
});
