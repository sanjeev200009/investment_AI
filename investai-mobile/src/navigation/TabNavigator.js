// src/navigation/TabNavigator.js
//
// v2 tab bar: a floating glass pill of round icon buttons over the gradient,
// as in the design canvas. The focused tab is a larger white circle; the AI
// tab is always the black circle. Alerts shows the unread count.
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, Animated, Easing, useWindowDimensions } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import TouchableTick from '../components/TouchableTick';
import { palette, radii } from '../theme/tokens';
import { tabMotion, isReduceMotion } from '../theme/motion';
import { useT } from '../store/languageStore';
import { notificationsApi } from '../api/api';
import Tour, { useTourStore } from '../components/Tour';

import { HomeStack, MarketsStack, PortfolioStack, AlertsStack } from './TabStacks';
import ChatScreen from '../screens/ChatScreen';

const Tab = createBottomTabNavigator();

const ICONS = {
    Home: 'home',
    Markets: 'show-chart',
    AIChat: 'auto-awesome',
    Portfolio: 'pie-chart-outline',
    Alerts: 'notifications-none',
};
const LABEL_KEYS = {
    Home: 'tab_home',
    Markets: 'tab_markets',
    AIChat: 'tab_ai',
    Portfolio: 'tab_portfolio',
    Alerts: 'tab_alerts',
};

// The tab that just became active springs up from a slightly smaller size.
function Pop({ focused, children }) {
    const scale = useRef(new Animated.Value(1)).current;
    useEffect(() => {
        if (!focused || isReduceMotion()) return;
        scale.setValue(0.8);
        Animated.spring(scale, { toValue: 1, useNativeDriver: true, damping: 9, stiffness: 220, mass: 0.6 }).start();
    }, [focused, scale]);
    return <Animated.View style={{ transform: [{ scale }] }}>{children}</Animated.View>;
}

// A soft lime ring that keeps breathing out of the AI button while it is not
// the open tab, so the assistant always reads as the app's centrepiece.
function Glow({ size, active }) {
    const v = useRef(new Animated.Value(0)).current;
    useEffect(() => {
        if (active || isReduceMotion()) { v.setValue(0); return undefined; }
        const loop = Animated.loop(Animated.timing(v, {
            toValue: 1, duration: 1800, easing: Easing.out(Easing.quad), useNativeDriver: true,
        }));
        loop.start();
        return () => loop.stop();
    }, [active, v]);
    return (
        <Animated.View pointerEvents="none" style={[styles.glow, {
            width: size, height: size, borderRadius: size / 2,
            opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.55, 0] }),
            transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [1, 1.45] }) }],
        }]} />
    );
}

function PillTabBar({ state, navigation }) {
    const insets = useSafeAreaInsets();
    const { width } = useWindowDimensions();
    const { t } = useT();
    // Scale with the phone instead of fixed 50/58 px circles that looked lost on
    // wide screens: five equal slots across the bar, the AI button ~1.35× bigger.
    const slot = (width - 32 - 16) / 5;
    const circle = Math.round(Math.min(Math.max(slot * 0.62, 40), 50));
    const aiSize = Math.round(Math.min(Math.max(slot * 0.92, 58), 72));
    const [unread, setUnread] = useState(0);
    // The first-run tour spotlights each button, so report where they are.
    const setRect = useTourStore(s => s.setRect);
    const itemRefs = useRef({});
    const measure = (name) => itemRefs.current[name]?.measureInWindow((x, y, w, h) => {
        if (w) setRect(name, { x, y, w, h });
    });
    // A button's own onLayout misses its siblings resizing (the focused one
    // grows), so re-measure every button once the tour opens or the tab changes.
    const touring = useTourStore(s => s.visible);
    useEffect(() => {
        const id = setTimeout(() => state.routes.forEach(r => measure(r.name)), 350);
        return () => clearTimeout(id);
    }, [touring, state.index]); // eslint-disable-line react-hooks/exhaustive-deps

    // Refresh the unread count whenever the tab changes; cheap, and keeps the
    // badge honest without a background poll.
    useEffect(() => {
        let cancelled = false;
        notificationsApi.list()
            .then(items => { if (!cancelled) setUnread((items || []).filter(n => !n.is_read).length); })
            .catch(() => {});
        return () => { cancelled = true; };
    }, [state.index]);

    // The retaken assessment has its own Previous/Next footer where the bar sits.
    if (['RetakeAssessment', 'StockDetail'].includes(getFocusedRouteNameFromRoute(state.routes[state.index]))) return null;

    return (
        <View pointerEvents="box-none" style={[styles.wrap, { bottom: Math.max(insets.bottom, 12) }]}>
            <View style={styles.bar}>
                {state.routes.map((route, index) => {
                    const focused = state.index === index;
                    const isAI = route.name === 'AIChat';
                    const onPress = () => {
                        const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
                        if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
                    };
                    const badge = route.name === 'Alerts' && unread > 0 ? unread : 0;
                    const label = t(LABEL_KEYS[route.name]);
                    const a11y = badge ? `${label}, ${badge}` : label;
                    if (isAI) {
                        return (
                            <View key={route.key} style={[styles.slot, { height: circle + 18 }]}>
                                <View style={[styles.aiLift, { width: aiSize, height: aiSize, top: -(aiSize * 0.42) }]}>
                                    <Glow size={aiSize} active={focused} />
                                    <Pop focused={focused}>
                                    <View collapsable={false} ref={el => { itemRefs.current[route.name] = el; }} onLayout={() => measure(route.name)}>
                                    <TouchableTick
                                        onPress={onPress}
                                        accessibilityRole="tab"
                                        accessibilityState={{ selected: focused }}
                                        accessibilityLabel={a11y}
                                        style={[styles.ai, {
                                            width: aiSize, height: aiSize, borderRadius: aiSize / 2,
                                            borderColor: focused ? palette.lime : '#FFFFFF',
                                        }]}
                                    >
                                        <MaterialCommunityIcons name="robot-happy-outline" size={Math.round(aiSize * 0.46)} color="#FFFFFF" />
                                    </TouchableTick>
                                    </View>
                                    </Pop>
                                </View>
                                <Text style={[styles.label, styles.aiLabel, focused && styles.labelOn]} numberOfLines={1}>{label}</Text>
                            </View>
                        );
                    }
                    return (
                        <View key={route.key} style={styles.slot}>
                        <Pop focused={focused}>
                        <View collapsable={false} ref={el => { itemRefs.current[route.name] = el; }} onLayout={() => measure(route.name)}>
                        <TouchableTick
                            onPress={onPress}
                            accessibilityRole="tab"
                            accessibilityState={{ selected: focused }}
                            accessibilityLabel={a11y}
                            style={[styles.item, {
                                width: circle, height: circle,
                                backgroundColor: focused ? palette.lime : 'transparent',
                            }]}
                        >
                            <MaterialIcons name={ICONS[route.name]} size={Math.round(circle * 0.5)} color={focused ? palette.ink : palette.faint} />
                            {badge ? (
                                <View style={styles.badgePill}>
                                    <Text style={styles.badgeText}>{badge > 99 ? '99+' : badge}</Text>
                                </View>
                            ) : null}
                        </TouchableTick>
                        </View>
                        </Pop>
                        <Text style={[styles.label, focused && styles.labelOn]} numberOfLines={1}>{label}</Text>
                        </View>
                    );
                })}
            </View>
        </View>
    );
}

export default function TabNavigator() {
    const touring = useTourStore(s => s.visible);
    return (
        <View style={{ flex: 1 }}>
            {/* While the tour is up, screen readers stay inside its card. */}
            <View style={{ flex: 1 }} importantForAccessibility={touring ? 'no-hide-descendants' : 'auto'}>
                <Tab.Navigator
                    tabBar={(props) => <PillTabBar {...props} />}
                    screenOptions={tabMotion}
                >
                    <Tab.Screen name='Home' component={HomeStack} />
                    <Tab.Screen name='Markets' component={MarketsStack} />
                    <Tab.Screen name='AIChat' component={ChatScreen} />
                    <Tab.Screen name='Portfolio' component={PortfolioStack} />
                    <Tab.Screen name='Alerts' component={AlertsStack} />
                </Tab.Navigator>
            </View>
            <Tour />
        </View>
    );
}

const styles = StyleSheet.create({
    wrap: { position: 'absolute', left: 16, right: 16 },
    bar: {
        flexDirection: 'row', alignItems: 'flex-end', paddingHorizontal: 8, paddingTop: 8, paddingBottom: 6,
        borderRadius: 32, backgroundColor: 'rgba(255,255,255,0.92)',
        borderWidth: 1, borderColor: palette.hairline,
        shadowColor: '#0F1115', shadowOffset: { width: 0, height: 10 }, shadowOpacity: 0.12, shadowRadius: 24, elevation: 10,
    },
    slot: { flex: 1, alignItems: 'center', justifyContent: 'flex-end', gap: 2 },
    item: { borderRadius: radii.full, alignItems: 'center', justifyContent: 'center' },
    label: { fontSize: 11, fontFamily: 'Satoshi-Medium', color: palette.faint },
    labelOn: { color: palette.ink, fontFamily: 'Satoshi-Bold' },
    aiLift: { position: 'absolute', alignSelf: 'center', alignItems: 'center', justifyContent: 'center' },
    ai: {
        alignItems: 'center', justifyContent: 'center', backgroundColor: palette.ink, borderWidth: 3,
        shadowColor: '#0F1115', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.28, shadowRadius: 14, elevation: 12,
    },
    aiLabel: { marginTop: 'auto' },
    glow: { position: 'absolute', backgroundColor: palette.lime },
    badgePill: {
        position: 'absolute', top: 0, right: 0, minWidth: 18, height: 18, paddingHorizontal: 4,
        borderRadius: radii.full, backgroundColor: palette.badge, alignItems: 'center', justifyContent: 'center',
    },
    badgeText: { color: '#FFFFFF', fontSize: 10, fontFamily: 'Satoshi-Bold' },
});
