// src/navigation/TabStacks.js
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';

import HomeScreen from '../screens/HomeScreen';
import StockBrowseScreen from '../screens/StockBrowseScreen';
import PortfolioScreen from '../screens/PortfolioScreen';
import ProfileScreen from '../screens/ProfileScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import WatchlistScreen from '../screens/WatchlistScreen';
import LearnScreen from '../screens/LearnScreen';
import StockDetailScreen from '../screens/StockDetailScreen';
import FinancialAssessmentScreen from '../screens/FinancialAssessmentScreen';

const Stack = createStackNavigator();

const screenOptions = {
    headerShown: false,
};

export const HomeStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="HomeMain" component={HomeScreen} />
        <Stack.Screen name="Notifications" component={NotificationsScreen} />
        <Stack.Screen name="Watchlist" component={WatchlistScreen} />
        <Stack.Screen name="Learn" component={LearnScreen} />
        <Stack.Screen name="Assessment" component={FinancialAssessmentScreen} />
    </Stack.Navigator>
);

export const MarketsStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="MarketsMain" component={StockBrowseScreen} />
        <Stack.Screen name="StockDetail" component={StockDetailScreen} />
        <Stack.Screen name="Watchlist" component={WatchlistScreen} />
    </Stack.Navigator>
);

export const PortfolioStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="PortfolioMain" component={PortfolioScreen} />
        <Stack.Screen name="StockDetail" component={StockDetailScreen} />
    </Stack.Navigator>
);

export const ProfileStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="ProfileMain" component={ProfileScreen} />
        <Stack.Screen name="Notifications" component={NotificationsScreen} />
    </Stack.Navigator>
);
