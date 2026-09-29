// src/components/Tour.js
//
// First-run guided tour: a coach-mark overlay mounted by TabNavigator above the
// floating tab bar. Step 1 is a centred welcome card; steps 2-6 dim the screen
// with a round cut-out that glides between the tab buttons, and a speech-bubble
// card (with a Pill Pal) points down at the highlighted tab.
//
// The tab bar reports each button's window position into useTourStore; the
// overlay measures its own window origin and subtracts it, so both agree even
// under edge-to-edge. Completion (finish or skip) is saved in AsyncStorage
// under 'tour_done_v1'; replayTour() clears it and opens the tour again.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
    View, Text, StyleSheet, Animated, BackHandler, AccessibilityInfo, findNodeHandle, useWindowDimensions,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import TouchableTick from './TouchableTick';
import { PillPal } from './PillPals';
import { palette, fonts, radii } from '../theme/tokens';
import { isReduceMotion, EASE_OUT } from '../theme/motion';
import { useT } from '../store/languageStore';

const DONE_KEY = 'tour_done_v1';
const HOLE_R = 38;         // fits the 58pt focused / AI buttons with a margin
const DIM = 'rgba(15,17,21,0.62)';

const STEPS = [
    { tab: null, title: 'tour_welcome_title', body: 'tour_welcome_body', tone: 'lavender', pose: 'wave', mood: 'joy' },
    { tab: 'Home', title: 'tab_home', body: 'tour_home_body', tone: 'lime', badge: 'home' },
    { tab: 'Markets', title: 'tab_markets', body: 'tour_markets_body', tone: 'yellow', badge: 'search' },
    { tab: 'AIChat', title: 'tab_ai', body: 'tour_ai_body', tone: 'lavender', badge: 'auto-awesome' },
    { tab: 'Portfolio', title: 'tab_portfolio', body: 'tour_portfolio_body', tone: 'lime', badge: 'pie-chart-outline' },
    { tab: 'Alerts', title: 'tab_alerts', body: 'tour_alerts_body', tone: 'coral', badge: 'notifications-none', pose: 'cheer', mood: 'joy' },
];

export const useTourStore = create((set) => ({
    visible: false,
    rects: {},   // tab route name -> { x, y, w, h } in window coordinates
    setRect: (name, rect) => set((s) => ({ rects: { ...s.rects, [name]: rect } })),
    open: () => set({ visible: true }),
    close: () => set({ visible: false }),
}));

export async function replayTour() {
    try { await AsyncStorage.removeItem(DONE_KEY); } catch (_) { /* replay anyway */ }
    useTourStore.getState().open();
}

export default function Tour() {
    const visible = useTourStore((s) => s.visible);

    // First run: open once the tabs have had a moment to lay out.
    useEffect(() => {
        let timer;
        AsyncStorage.getItem(DONE_KEY)
            .then((done) => { if (!done) timer = setTimeout(() => useTourStore.getState().open(), 700); })
            .catch(() => {});
        return () => clearTimeout(timer);
    }, []);

    return visible ? <TourOverlay /> : null;
}

function TourOverlay() {
    const { t } = useT();
    const { width, height } = useWindowDimensions();
    const rects = useTourStore((s) => s.rects);
    const close = useTourStore((s) => s.close);
    const [step, setStep] = useState(0);
    const [origin, setOrigin] = useState({ x: 0, y: 0, w: width, h: height });
    const rootRef = useRef(null);
    const titleRef = useRef(null);

    const fade = useRef(new Animated.Value(0)).current;       // whole overlay
    const card = useRef(new Animated.Value(0)).current;       // card enter per step
    const spot = useRef(new Animated.ValueXY({ x: width / 2, y: -HOLE_R * 3 })).current;

    const s = STEPS[step];
    const last = step === STEPS.length - 1;
    const r = s.tab ? rects[s.tab] : null;
    const target = r
        ? { x: r.x - origin.x + r.w / 2, y: r.y - origin.y + r.h / 2 }
        : { x: origin.w / 2, y: -HOLE_R * 3 };   // welcome: hole parked off-screen above

    const finish = useCallback(() => {
        AsyncStorage.setItem(DONE_KEY, '1').catch(() => {});
        Animated.timing(fade, { toValue: 0, duration: isReduceMotion() ? 0 : 220, useNativeDriver: true })
            .start(() => close());
    }, [fade, close]);

    useEffect(() => {
        Animated.timing(fade, { toValue: 1, duration: isReduceMotion() ? 0 : 260, easing: EASE_OUT, useNativeDriver: true }).start();
        const sub = BackHandler.addEventListener('hardwareBackPress', () => { finish(); return true; });
        return () => sub.remove();
    }, [fade, finish]);

    // Each step: the spotlight glides to its tab and the card pops in.
    useEffect(() => {
        const reduce = isReduceMotion();
        if (reduce) spot.setValue(target);
        else Animated.spring(spot, { toValue: target, useNativeDriver: true, damping: 18, stiffness: 140, mass: 0.9 }).start();
        card.setValue(0);
        Animated.timing(card, { toValue: 1, duration: reduce ? 120 : 360, easing: EASE_OUT, useNativeDriver: true }).start();
        const focus = setTimeout(() => {
            const node = titleRef.current && findNodeHandle(titleRef.current);
            if (node) AccessibilityInfo.setAccessibilityFocus(node);
        }, 400);
        return () => clearTimeout(focus);
    }, [step, target.x, target.y]); // eslint-disable-line react-hooks/exhaustive-deps

    const measureRoot = () => {
        rootRef.current?.measureInWindow((x, y, w, h) => { if (w) setOrigin({ x, y, w, h }); });
    };

    const ring = HOLE_R + Math.max(width, height) * 1.5;   // border thick enough to cover the screen
    const cardW = origin.w - 32;
    const tailX = Math.min(Math.max(target.x - 16 - 10, 28), cardW - 48);
    const cardPos = r
        ? { position: 'absolute', left: 16, right: 16, bottom: origin.h - (target.y - HOLE_R) + 22 }
        : { position: 'absolute', left: 16, right: 16, top: origin.h * 0.24 };

    return (
        <Animated.View
            ref={rootRef}
            onLayout={measureRoot}
            style={[StyleSheet.absoluteFill, styles.root, { opacity: fade }]}
            onStartShouldSetResponder={() => true}
            accessibilityViewIsModal
        >
            {/* Dim layer: a huge ring whose transparent middle is the cut-out. */}
            <Animated.View
                pointerEvents="none"
                importantForAccessibility="no-hide-descendants"
                style={{
                    position: 'absolute', left: -ring, top: -ring, width: ring * 2, height: ring * 2,
                    borderRadius: ring, borderWidth: ring - HOLE_R, borderColor: DIM,
                    transform: spot.getTranslateTransform(),
                }}
            >
                <View style={styles.halo} />
            </Animated.View>

            <Animated.View
                style={[cardPos, {
                    opacity: card,
                    transform: [
                        { translateY: card.interpolate({ inputRange: [0, 1], outputRange: [isReduceMotion() ? 0 : 12, 0] }) },
                        { scale: card.interpolate({ inputRange: [0, 1], outputRange: [isReduceMotion() ? 1 : 0.94, 1] }) },
                    ],
                }]}
                accessibilityLabel={t('tour_a11y_label')}
            >
                <View style={styles.card}>
                    <View style={styles.cardTop}>
                        <PillPal tone={s.tone} mood={s.mood || 'happy'} pose={s.pose || 'rest'} badge={s.badge} size={s.tab ? 96 : 120} />
                        <View style={{ flex: 1, gap: 6 }}>
                            <Text ref={titleRef} accessible accessibilityRole="header" style={styles.title}>{t(s.title)}</Text>
                            <Text style={styles.body}>{t(s.body)}</Text>
                        </View>
                    </View>

                    <View
                        style={styles.dots}
                        accessible
                        accessibilityLabel={t('tour_step').replace('{n}', String(step + 1)).replace('{total}', String(STEPS.length))}
                    >
                        {STEPS.map((_, i) => (
                            <View key={i} style={[styles.dot, i === step && styles.dotOn]} />
                        ))}
                    </View>

                    <View style={styles.actions}>
                        {!last ? (
                            <TouchableTick onPress={finish} accessibilityRole="button" accessibilityLabel={t('tour_skip')} style={styles.skip}>
                                <Text style={styles.skipText}>{t('tour_skip')}</Text>
                            </TouchableTick>
                        ) : null}
                        <View style={{ flex: 1 }} />
                        {step > 0 ? (
                            <TouchableTick onPress={() => setStep(step - 1)} accessibilityRole="button" accessibilityLabel={t('tour_back')} style={[styles.btn, styles.btnGhost]}>
                                <Text style={styles.btnGhostText}>{t('tour_back')}</Text>
                            </TouchableTick>
                        ) : null}
                        <TouchableTick
                            onPress={last ? finish : () => setStep(step + 1)}
                            accessibilityRole="button"
                            accessibilityLabel={last ? t('tour_done') : t('tour_next')}
                            style={[styles.btn, styles.btnInk]}
                        >
                            <Text style={styles.btnInkText}>{last ? t('tour_done') : t('tour_next')}</Text>
                        </TouchableTick>
                    </View>
                </View>
                {r ? <View style={[styles.tail, { left: tailX }]} /> : null}
            </Animated.View>
        </Animated.View>
    );
}

const styles = StyleSheet.create({
    root: { zIndex: 100, elevation: 100 },
    halo: {
        width: HOLE_R * 2, height: HOLE_R * 2, borderRadius: HOLE_R,
        borderWidth: 3, borderColor: palette.lime,
    },
    card: {
        backgroundColor: '#FFFFFF', borderRadius: radii.xxl, padding: 18, gap: 14,
        shadowColor: '#0F1115', shadowOffset: { width: 0, height: 12 }, shadowOpacity: 0.18, shadowRadius: 24, elevation: 8,
    },
    cardTop: { flexDirection: 'row', alignItems: 'center', gap: 14 },
    title: { fontFamily: fonts.bold, fontSize: 20, color: palette.ink, letterSpacing: -0.3 },
    body: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 21, color: palette.muted },
    dots: { flexDirection: 'row', gap: 6, alignSelf: 'center', paddingVertical: 2 },
    dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: palette.hairline },
    dotOn: { width: 20, backgroundColor: palette.ink },
    actions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    skip: { minHeight: 44, paddingHorizontal: 8, justifyContent: 'center' },
    skipText: { fontFamily: fonts.medium, fontSize: 15, color: palette.faint },
    btn: { minHeight: 44, paddingHorizontal: 18, borderRadius: radii.full, alignItems: 'center', justifyContent: 'center' },
    btnGhost: { borderWidth: 1, borderColor: palette.outline },
    btnGhostText: { fontFamily: fonts.medium, fontSize: 15, color: palette.ink },
    btnInk: { backgroundColor: palette.ink },
    btnInkText: { fontFamily: fonts.bold, fontSize: 15, color: '#FFFFFF' },
    tail: {
        position: 'absolute', bottom: -9, width: 20, height: 20, backgroundColor: '#FFFFFF',
        borderRadius: 3, transform: [{ rotate: '45deg' }],
    },
});
