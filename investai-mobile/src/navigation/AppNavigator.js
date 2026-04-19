// src/navigation/AppNavigator.js
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import TabNavigator from './TabNavigator';
import AuthNavigator from './AuthNavigator';
import SplashScreen from '../screens/SplashScreen';
import FinancialAssessmentScreen from '../screens/FinancialAssessmentScreen';
import StockDetailScreen from '../screens/StockDetailScreen';
import WatchlistScreen from '../screens/WatchlistScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import LearnScreen from '../screens/LearnScreen';

import { useAuthStore } from '../store/authStore';

import { ActivityIndicator, View } from 'react-native';

const Stack = createStackNavigator();

const AppNavigator = () => {
    const { isAuthenticated, isLoading } = useAuthStore();

    if (isLoading) {
        return (
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#000814' }}>
                <ActivityIndicator size="large" color="#003566" />
            </View>
        );
    }

    return (
        <Stack.Navigator screenOptions={{ headerShown: false }}>
            {!isAuthenticated ? (
                <Stack.Screen name='Auth' component={AuthNavigator} />
            ) : (
                <>
                    <Stack.Screen name='MainTab' component={TabNavigator} />
                    <Stack.Screen name='Assessment' component={FinancialAssessmentScreen} />
                    <Stack.Screen name='StockDetail' component={StockDetailScreen} />
                    <Stack.Screen name='Watchlist' component={WatchlistScreen} />
                    <Stack.Screen name='Notifications' component={NotificationsScreen} />
                    <Stack.Screen name='Learn' component={LearnScreen} />
                </>
            )}
        </Stack.Navigator>
    );
}

export default AppNavigator;
