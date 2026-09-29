// src/navigation/TabStacks.js
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { stackMotion, cardLiftMotion } from '../theme/motion';

import HomeScreen from '../screens/HomeScreen';
import StockBrowseScreen from '../screens/StockBrowseScreen';
import AllTopMoversScreen from '../screens/AllTopMoversScreen';
import PortfolioScreen from '../screens/PortfolioScreen';
import ProfileScreen from '../screens/ProfileScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import WatchlistScreen from '../screens/WatchlistScreen';
import RulesScreen from '../screens/RulesScreen';
import LearnScreen from '../screens/LearnScreen';
import StockDetailScreen from '../screens/StockDetailScreen';
import LessonScreen from '../screens/LessonScreen';
import LegalScreen from '../screens/LegalScreen';
import AssessmentScreen from '../screens/onboarding/AssessmentScreen';

const Stack = createStackNavigator();

const screenOptions = stackMotion;

export const HomeStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="HomeMain" component={HomeScreen} />
        <Stack.Screen name="StockDetail" component={StockDetailScreen} options={cardLiftMotion} />
        <Stack.Screen name="Notifications" component={NotificationsScreen} />
        <Stack.Screen name="Rules" component={RulesScreen} />
        <Stack.Screen name="Watchlist" component={WatchlistScreen} />
        <Stack.Screen name="ProfileMain" component={ProfileScreen} />
        <Stack.Screen name="RetakeAssessment" component={AssessmentScreen} />
        <Stack.Screen name="Legal" component={LegalScreen} />
        <Stack.Screen name="Learn" component={LearnScreen} />
        <Stack.Screen name="Lesson" component={LessonScreen} />
    </Stack.Navigator>
);

export const MarketsStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="MarketsMain" component={StockBrowseScreen} />
        <Stack.Screen name="StockDetail" component={StockDetailScreen} options={cardLiftMotion} />
        <Stack.Screen name="Watchlist" component={WatchlistScreen} />
        <Stack.Screen name="AllTopMovers" component={AllTopMoversScreen} />
        <Stack.Screen name="Rules" component={RulesScreen} />
    </Stack.Navigator>
);

export const PortfolioStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="PortfolioMain" component={PortfolioScreen} />
        <Stack.Screen name="StockDetail" component={StockDetailScreen} options={cardLiftMotion} />
        <Stack.Screen name="Rules" component={RulesScreen} />
    </Stack.Navigator>
);

export const AlertsStack = () => (
    <Stack.Navigator screenOptions={screenOptions}>
        <Stack.Screen name="Notifications" component={NotificationsScreen} />
        <Stack.Screen name="Rules" component={RulesScreen} />
        <Stack.Screen name="ProfileMain" component={ProfileScreen} />
        <Stack.Screen name="RetakeAssessment" component={AssessmentScreen} />
        <Stack.Screen name="Legal" component={LegalScreen} />
    </Stack.Navigator>
);
