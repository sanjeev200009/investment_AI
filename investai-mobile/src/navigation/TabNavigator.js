// src/navigation/TabNavigator.js
import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons, MaterialIcons } from '@expo/vector-icons';
import { View, StyleSheet, Platform } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

import { HomeStack, MarketsStack, PortfolioStack, ProfileStack } from './TabStacks';
import ChatScreen from '../screens/ChatScreen';

const Tab = createBottomTabNavigator();

export default function TabNavigator() {
    const theme = useAppTheme();

    return (
        <Tab.Navigator
            screenOptions={({ route }) => ({
                tabBarActiveTintColor: theme.colors.primary,
                tabBarInactiveTintColor: theme.colors.textSecondary,
                tabBarStyle: {
                    height: Platform.OS === 'ios' ? 88 : 68,
                    backgroundColor: theme.colors.background,
                    borderTopColor: theme.colors.divider,
                    borderTopWidth: 1,
                    paddingBottom: Platform.OS === 'ios' ? 30 : 12,
                    paddingTop: 12,
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
                tabBarLabelStyle: {
                    fontSize: 11,
                    fontWeight: '700',
                    marginTop: 4,
                },
                headerShown: false,
                tabBarIcon: ({ focused, color, size }) => {
                    const icons = {
                        Home: focused ? 'home' : 'home-outline',
                        Markets: focused ? 'stats-chart' : 'stats-chart-outline',
                        AIChat: 'sparkles',
                        Portfolio: focused ? 'pie-chart' : 'pie-chart-outline',
                        Profile: focused ? 'person' : 'person-outline',
                    };

                    if (route.name === 'AIChat') {
                        return (
                            <View style={[styles.aiButtonContainer, { borderColor: theme.colors.background }]}>
                                <View style={[styles.aiButton, { backgroundColor: theme.colors.primary }]}>
                                    <MaterialIcons name='smart-toy' size={28} color="#FFFFFF" />
                                </View>
                            </View>
                        );
                    }

                    let iconName = icons[route.name] || 'help-circle';
                    return <Ionicons name={iconName} size={24} color={color} />;
                },
            })}
        >
            <Tab.Screen 
                name='Home' 
                component={HomeStack} 
                options={{ title: 'Home' }}
            />
            <Tab.Screen 
                name='Markets' 
                component={MarketsStack} 
                options={{ title: 'Markets' }}
            />
            <Tab.Screen 
                name='AIChat' 
                component={ChatScreen} 
                options={{ 
                    tabBarLabel: 'AI',
                }} 
            />
            <Tab.Screen 
                name='Portfolio' 
                component={PortfolioStack} 
                options={{ title: 'Portfolio' }}
            />
            <Tab.Screen 
                name='Profile' 
                component={ProfileStack} 
                options={{ title: 'Profile' }}
            />
        </Tab.Navigator>
    );
}

const styles = StyleSheet.create({
    aiButtonContainer: {
        width: 64,
        height: 64,
        borderRadius: 32,
        borderWidth: 4,
        backgroundColor: 'transparent',
        marginTop: -30,
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 50,
    },
    aiButton: {
        width: 50,
        height: 50,
        borderRadius: 25,
        justifyContent: 'center',
        alignItems: 'center',
        shadowColor: '#0052FF',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 6,
    },
});
