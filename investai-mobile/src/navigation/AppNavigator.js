// src/navigation/AppNavigator.js
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import TabNavigator from './TabNavigator';
import SplashScreen from '../screens/SplashScreen';
import OnboardingScreen from '../screens/auth/OnboardingScreen';
import LoginScreen from '../screens/auth/LoginScreen';
import RegisterScreen from '../screens/auth/RegisterScreen';
import FinancialAssessmentScreen from '../screens/FinancialAssessmentScreen';
import StockDetailScreen from '../screens/StockDetailScreen';
import WatchlistScreen from '../screens/WatchlistScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import LearnScreen from '../screens/LearnScreen';

const Stack = createStackNavigator();

export default function AppNavigator() {
    return (
        <Stack.Navigator screenOptions={{ headerShown: false }}
            initialRouteName='Splash'>
            <Stack.Screen name='Splash' component={SplashScreen} />
            <Stack.Screen name='Onboarding' component={OnboardingScreen} />
            <Stack.Screen name='Login' component={LoginScreen} />
            <Stack.Screen name='Register' component={RegisterScreen} />
            <Stack.Screen name='Assessment' component={FinancialAssessmentScreen} />
            <Stack.Screen name='MainTab' component={TabNavigator} />
            <Stack.Screen name='StockDetail' component={StockDetailScreen} />
            <Stack.Screen name='Watchlist' component={WatchlistScreen} />
            <Stack.Screen name='Notifications' component={NotificationsScreen} />
            <Stack.Screen name='Learn' component={LearnScreen} />
        </Stack.Navigator>
    );
}
