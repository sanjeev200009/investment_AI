// src/navigation/TabNavigator.js
import React, { useEffect, useRef } from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons, MaterialIcons } from '@expo/vector-icons';
import { View, Text, StyleSheet, Platform, Animated } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

import { HomeStack, MarketsStack, PortfolioStack, AlertsStack } from './TabStacks';
import ChatScreen from '../screens/ChatScreen';

const Tab = createBottomTabNavigator();

const AnimatedTabItem = ({ focused, routeName, theme }) => {
    const scaleValue = useRef(new Animated.Value(focused ? 1 : 0)).current;

    useEffect(() => {
        Animated.spring(scaleValue, {
            toValue: focused ? 1 : 0,
            useNativeDriver: true,
            tension: 60,
            friction: 8,
        }).start();
    }, [focused]);

    if (routeName === 'AIChat') {
        return (
            <View style={{ alignItems: 'center', justifyContent: 'center', marginTop: -24 }}>
                <View style={[styles.aiButtonContainer, { borderColor: theme.colors.background }]}>
                    <View style={[styles.aiButton, { backgroundColor: theme.colors.primary }]}>
                        <MaterialIcons name='smart-toy' size={28} color="#FFFFFF" />
                    </View>
                </View>
                <Text style={{ fontSize: 11, fontFamily: 'Satoshi-Bold', color: theme.colors.textSecondary, marginTop: 4 }}>AI</Text>
            </View>
        );
    }

    const icons = {
        Home: 'home',
        Markets: 'explore',
        Portfolio: 'pie-chart',
        Alerts: 'notifications',
    };
    
    const labels = {
        Home: 'Home',
        Markets: 'Discover',
        Portfolio: 'Portfolio',
        Alerts: 'Alerts',
    };

    const iconName = icons[routeName] || 'help-circle';
    const label = labels[routeName] || routeName;
    const color = focused ? theme.colors.primary : theme.colors.textSecondary;

    const opacity = scaleValue.interpolate({
        inputRange: [0, 1],
        outputRange: [0, 1]
    });
    
    const scale = scaleValue.interpolate({
        inputRange: [0, 1],
        outputRange: [0.8, 1]
    });

    return (
        <View style={{ alignItems: 'center', justifyContent: 'center', paddingVertical: 6, paddingHorizontal: 16 }}>
            <Animated.View style={[StyleSheet.absoluteFillObject, { 
                backgroundColor: '#cfe5ff', // Slight blue color
                borderRadius: 12, 
                opacity,
                transform: [{ scale }],
                zIndex: 0
            }]} />
            
            <View style={{ alignItems: 'center', justifyContent: 'center', zIndex: 1 }}>
                <MaterialIcons name={iconName} size={24} color={color} />
                <Text style={{ 
                    fontSize: 11, 
                    fontFamily: focused ? 'Satoshi-Bold' : 'Satoshi-Medium', 
                    color: color, 
                    marginTop: 2 
                }}>
                    {label}
                </Text>
            </View>
        </View>
    );
};

export default function TabNavigator() {
    const theme = useAppTheme();

    return (
        <Tab.Navigator
            screenOptions={({ route }) => ({
                tabBarShowLabel: false,
                tabBarStyle: {
                    height: Platform.OS === 'ios' ? 88 : 68,
                    backgroundColor: theme.colors.background,
                    borderTopColor: theme.colors.divider,
                    borderTopWidth: 1,
                    paddingBottom: Platform.OS === 'ios' ? 30 : 8,
                    paddingTop: 8,
                    // Modern subtle shadow for the tab bar
                    ...Platform.select({
                        ios: {
                            shadowColor: '#000',
                            shadowOffset: { width: 0, height: -2 },
                            shadowOpacity: 0.05,
                            shadowRadius: 10,
                        },
                        android: {
                            elevation: 8,
                        }
                    })
                },
                headerShown: false,
                tabBarIcon: ({ focused }) => (
                    <AnimatedTabItem focused={focused} routeName={route.name} theme={theme} />
                ),
            })}
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
    aiButtonContainer: {
        width: 56,
        height: 56,
        borderRadius: 28,
        borderWidth: 4,
        backgroundColor: 'transparent',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 50,
    },
    aiButton: {
        width: 44,
        height: 44,
        borderRadius: 22,
        justifyContent: 'center',
        alignItems: 'center',
        shadowColor: '#0052FF',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 6,
    },
});
