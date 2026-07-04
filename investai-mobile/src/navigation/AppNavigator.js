// src/navigation/AppNavigator.js
import React, { useEffect, useState } from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import TabNavigator from './TabNavigator';
import AuthNavigator from './AuthNavigator';
import SplashScreen from '../screens/SplashScreen';
import AssessmentScreen from '../screens/onboarding/AssessmentScreen';

import { useAuthStore } from '../store/authStore';
import { ActivityIndicator, View } from 'react-native';

import { useUser, useAuth } from '@clerk/clerk-expo';

const Stack = createStackNavigator();

const SignedInStack = () => {
    const { user } = useUser();
    const { hasCompletedProfileSetup, checkProfileSetup } = useAuthStore();
    const [isChecking, setIsChecking] = useState(true);

    useEffect(() => {
        if (user) {
            checkProfileSetup(user.id).finally(() => setIsChecking(false));
        }
    }, [user]);

    if (isChecking) {
        return (
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                <ActivityIndicator size="large" color="#1976D2" />
            </View>
        );
    }

    return (
        <Stack.Navigator 
            initialRouteName={hasCompletedProfileSetup ? 'MainTab' : 'ProfileSetup'}
            screenOptions={{ headerShown: false }}
        >
            <Stack.Screen name='ProfileSetup' component={AssessmentScreen} />
            <Stack.Screen name='MainTab' component={TabNavigator} />
        </Stack.Navigator>
    );
};

const AppNavigator = () => {
    const { isLoaded, isSignedIn } = useAuth();

    if (!isLoaded) {
        return <SplashScreen />;
    }

    return isSignedIn ? <SignedInStack /> : <AuthNavigator />;
}

export default AppNavigator;
