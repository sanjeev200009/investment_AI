// src/navigation/AppNavigator.js
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import TabNavigator from './TabNavigator';
import AuthNavigator from './AuthNavigator';
import SplashScreen from '../screens/SplashScreen';
import FinancialAssessmentScreen from '../screens/FinancialAssessmentScreen';

import { useAuthStore } from '../store/authStore';
import { ActivityIndicator, View } from 'react-native';

const Stack = createStackNavigator();

const AppNavigator = () => {
    const { isAuthenticated, isLoading, hasCompletedAssessment } = useAuthStore();

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
            ) : !hasCompletedAssessment ? (
                <Stack.Screen name='Assessment' component={FinancialAssessmentScreen} />
            ) : (
                <>
                    {/* The TabNavigator now hosts all main screens, keeping the tab bar visible */}
                    <Stack.Screen name='MainTab' component={TabNavigator} />
                    
                    {/* Modals or Global screens that should hide the tab bar can still go here if needed */}
                </>
            )}
        </Stack.Navigator>
    );
}

export default AppNavigator;
