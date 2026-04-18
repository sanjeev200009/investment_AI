// src/navigation/TabNavigator.js
import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons, MaterialIcons } from '@expo/vector-icons';
import { View, StyleSheet } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

import HomeScreen from '../screens/HomeScreen';
import StockBrowseScreen from '../screens/StockBrowseScreen';
import ChatScreen from '../screens/ChatScreen';
import PortfolioScreen from '../screens/PortfolioScreen';
import ProfileScreen from '../screens/ProfileScreen';

const Tab = createBottomTabNavigator();

export default function TabNavigator() {
    const theme = useAppTheme();

    return (
        <Tab.Navigator
            screenOptions={({ route }) => ({
                tabBarActiveTintColor: theme.colors.primary,
                tabBarInactiveTintColor: theme.colors.textSecondary,
                tabBarStyle: {
                    height: 85,
                    backgroundColor: theme.colors.background,
                    borderTopColor: theme.colors.divider,
                    borderTopWidth: 1,
                    paddingBottom: 25,
                    paddingTop: 10,
                },
                tabBarLabelStyle: {
                    fontSize: 10,
                    fontWeight: '700',
                },
                headerShown: false,
                tabBarIcon: ({ focused, color, size }) => {
                    const icons = {
                        Home: focused ? 'home' : 'home-outline',
                        Markets: focused ? 'bar-chart' : 'bar-chart-outline',
                        AIChat: 'sparkles',
                        Portfolio: focused ? 'pie-chart' : 'pie-chart-outline',
                        Profile: focused ? 'person' : 'person-outline',
                    };
                    if (route.name === 'AIChat') {
                        return (
                            <View style={[styles.aiButtonContainer, { borderColor: theme.colors.background }]}>
                                <View style={[styles.aiButton, { backgroundColor: theme.colors.primary }]}>
                                    <MaterialIcons name='smart-toy' size={30} color="#FFFFFF" />
                                </View>
                            </View>
                        );
                    }
                    let iconName = icons[route.name] || 'help-circle';
                    return <Ionicons name={iconName} size={size} color={color} />;
                },
            })}
        >
            <Tab.Screen name='Home' component={HomeScreen} />
            <Tab.Screen name='Markets' component={StockBrowseScreen} />
            <Tab.Screen name='AIChat' component={ChatScreen} options={{ tabBarLabel: 'AI' }} />
            <Tab.Screen name='Portfolio' component={PortfolioScreen} />
            <Tab.Screen name='Profile' component={ProfileScreen} />
        </Tab.Navigator>
    );
}

const styles = StyleSheet.create({
    aiButtonContainer: {
        width: 68,
        height: 68,
        borderRadius: 34,
        borderWidth: 4,
        backgroundColor: 'transparent',
        marginTop: -30,
        justifyContent: 'center',
        alignItems: 'center',
    },
    aiButton: {
        width: 56,
        height: 56,
        borderRadius: 28,
        justifyContent: 'center',
        alignItems: 'center',
        shadowColor: '#0052FF',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 5,
    },
});

