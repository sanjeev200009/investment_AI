// src/navigation/TabNavigator.js
//
// v2 tab bar: a floating glass pill of round icon buttons over the gradient,
// as in the design canvas. The focused tab is a larger white circle; the AI
// tab is always the black circle. Alerts shows the unread count.
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import TouchableTick from '../components/TouchableTick';
import { palette, radii } from '../theme/tokens';
import { tabMotion, isReduceMotion } from '../theme/motion';
import { useT } from '../store/languageStore';
import { notificationsApi } from '../api/api';

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

function PillTabBar({ state, navigation }) {
    const insets = useSafeAreaInsets();
    const { t } = useT();
    const [unread, setUnread] = useState(0);

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
    if (getFocusedRouteNameFromRoute(state.routes[state.index]) === 'RetakeAssessment') return null;

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
                    const size = focused || isAI ? 58 : 50;
                    const bg = isAI ? palette.ink : focused ? '#FFFFFF' : 'rgba(255,255,255,0.7)';
                    const color = isAI ? '#FFFFFF' : focused ? palette.ink : palette.faint;
                    const badge = route.name === 'Alerts' && unread > 0 ? unread : 0;
                    return (
                        <Pop key={route.key} focused={focused}>
                        <TouchableTick
                            onPress={onPress}
                            accessibilityRole="tab"
                            accessibilityState={{ selected: focused }}
                            accessibilityLabel={badge ? `${t(LABEL_KEYS[route.name])}, ${badge}` : t(LABEL_KEYS[route.name])}
                            style={[styles.item, {
                                width: size, height: size, backgroundColor: bg,
                                borderWidth: focused && !isAI ? 1 : 0, borderColor: palette.hairline,
                            }]}
                        >
                            <MaterialIcons name={ICONS[route.name]} size={22} color={color} />
                            {badge ? (
                                <View style={styles.badgePill}>
                                    <Text style={styles.badgeText}>{badge > 99 ? '99+' : badge}</Text>
                                </View>
                            ) : null}
                        </TouchableTick>
                        </Pop>
                    );
                })}
            </View>
        </View>
    );
}

export default function TabNavigator() {
    return (
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
    );
}

const styles = StyleSheet.create({
    wrap: { position: 'absolute', left: 16, right: 16, alignItems: 'center' },
    bar: {
        flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8,
        borderRadius: radii.full, backgroundColor: 'rgba(255,255,255,0.6)',
        shadowColor: '#0F1115', shadowOffset: { width: 0, height: 10 }, shadowOpacity: 0.08, shadowRadius: 24, elevation: 6,
    },
    item: { borderRadius: radii.full, alignItems: 'center', justifyContent: 'center' },
    badgePill: {
        position: 'absolute', top: 0, right: 0, minWidth: 18, height: 18, paddingHorizontal: 4,
        borderRadius: radii.full, backgroundColor: palette.badge, alignItems: 'center', justifyContent: 'center',
    },
    badgeText: { color: '#FFFFFF', fontSize: 10, fontFamily: 'Satoshi-Bold' },
});
