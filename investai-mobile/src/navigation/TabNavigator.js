import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialIcons } from '@expo/vector-icons';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
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
                tabBarInactiveTintColor: theme.isDark ? '#64748B' : '#94A3B8',
                tabBarStyle: {
                    height: 85,
                    backgroundColor: theme.isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)',
                    borderTopColor: theme.isDark ? '#1E293B' : '#E2E8F0',
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
                        Home: 'grid-view',
                        Markets: 'monitoring',
                        AIChat: 'smart-toy',
                        Portfolio: 'account-balance-wallet',
                        Profile: 'settings',
                    };

                    if (route.name === 'AIChat') {
                        return (
                            <View style={[styles.aiButtonContainer, { borderColor: theme.isDark ? '#0A0A0A' : '#F9FAFB' }]}>
                                <View style={[styles.aiButton, { backgroundColor: theme.colors.primary }]}>
                                    <MaterialIcons name='smart-toy' size={30} color="#FFFFFF" />
                                </View>
                            </View>
                        );
                    }

                    let iconName = icons[route.name] || 'help-outline';
                    return <MaterialIcons name={iconName} size={26} color={color} />;
                },
            })}
        >
            <Tab.Screen
                name='Home'
                component={HomeScreen}
                options={{ tabBarLabel: 'Dashboard' }}
            />
            <Tab.Screen
                name='Markets'
                component={StockBrowseScreen}
                options={{ tabBarLabel: 'Markets' }}
            />
            <Tab.Screen
                name='AIChat'
                component={ChatScreen}
                options={{
                    tabBarLabel: '',
                    tabBarButton: (props) => (
                        <TouchableOpacity
                            {...props}
                            activeOpacity={0.8}
                            style={styles.aiTabButton}
                        />
                    )
                }}
            />
            <Tab.Screen
                name='Portfolio'
                component={PortfolioScreen}
                options={{ tabBarLabel: 'Portfolio' }}
            />
            <Tab.Screen
                name='Profile'
                component={ProfileScreen}
                options={{ tabBarLabel: 'Settings' }}
            />
        </Tab.Navigator>
    );
}

const styles = StyleSheet.create({
    aiTabButton: {
        top: -15,
        justifyContent: 'center',
        alignItems: 'center',
    },
    aiButtonContainer: {
        width: 65,
        height: 65,
        borderRadius: 32.5,
        borderWidth: 4,
        backgroundColor: 'transparent',
        justifyContent: 'center',
        alignItems: 'center',
    },
    aiButton: {
        width: 56,
        height: 56,
        borderRadius: 28,
        justifyContent: "center",
        alignItems: "center",
        shadowColor: '#0052FF',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.4,
        shadowRadius: 10,
        elevation: 10,
    },
});
