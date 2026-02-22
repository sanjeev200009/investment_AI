// src/navigation/TabNavigator.js
import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { View, StyleSheet } from 'react-native';
import { colors } from '../theme/theme';

import HomeScreen from '../screens/HomeScreen';
import StockBrowseScreen from '../screens/StockBrowseScreen';
import ChatScreen from '../screens/ChatScreen';
import PortfolioScreen from '../screens/PortfolioScreen';
import ProfileScreen from '../screens/ProfileScreen';

const Tab = createBottomTabNavigator();

export default function TabNavigator() {
    return (
        <Tab.Navigator
            screenOptions={({ route }) => ({
                tabBarActiveTintColor: colors.primary,
                tabBarInactiveTintColor: '#9E9E9E',
                tabBarStyle: { height: 60, backgroundColor: colors.bgCard },
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
                            <View style={styles.aiTab}>
                                <Ionicons name='sparkles' size={26} color={colors.bgCard} />
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
    aiTab: {
        width: 56, height: 56, borderRadius: 28,
        backgroundColor: colors.primary,
        justifyContent: "center", alignItems: "center",
        marginBottom: 10,
        shadowColor: '#000', shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3, shadowRadius: 6, elevation: 8,
    },
});
