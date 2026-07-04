// src/navigation/AppNavigator.js
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import TabNavigator from './TabNavigator';
import AuthNavigator from './AuthNavigator';
import SplashScreen from '../screens/SplashScreen';
import AssessmentScreen from '../screens/onboarding/AssessmentScreen';

import { useAuthStore } from '../store/authStore';
import { ActivityIndicator, View } from 'react-native';

import { SignedIn, SignedOut } from '@clerk/clerk-expo';

const Stack = createStackNavigator();

const AppNavigator = () => {
    return (
        <>
            <SignedIn>
                <Stack.Navigator screenOptions={{ headerShown: false }}>
                    <Stack.Screen name='MainTab' component={TabNavigator} />
                </Stack.Navigator>
            </SignedIn>
            <SignedOut>
                <AuthNavigator />
            </SignedOut>
        </>
    );
}

export default AppNavigator;
