// src/navigation/AppNavigator.js
//
// Gate: which stack renders is decided by the auth store, not by Clerk. The
// previous version asked Clerk (`useAuth().isSignedIn`) while every API call
// carried a token from a different system, so the app could show the signed-in
// stack to a user the backend did not recognise.
import React, { useEffect, useState } from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { stackMotion, revealMotion } from '../theme/motion';
import TabNavigator from './TabNavigator';
import AuthNavigator from './AuthNavigator';
import AssessmentScreen from '../screens/onboarding/AssessmentScreen';

import { useAuthStore } from '../store/authStore';
import { ScreenLoader } from '../components/ui';

const Stack = createStackNavigator();

const SignedInStack = () => {
    const user = useAuthStore(state => state.user);
    const hasCompletedProfileSetup = useAuthStore(state => state.hasCompletedProfileSetup);
    const checkProfileSetup = useAuthStore(state => state.checkProfileSetup);
    const [isChecking, setIsChecking] = useState(true);

    // user_id is the backend's own column (and the Supabase auth uid), which is
    // what the profile-setup flag is keyed by. Clerk's `user.id` was a different
    // identifier entirely, so the flag never matched after a reinstall.
    const userId = user?.user_id;

    useEffect(() => {
        if (!userId) return;
        let cancelled = false;
        checkProfileSetup(userId).finally(() => {
            if (!cancelled) setIsChecking(false);
        });
        return () => { cancelled = true; };
    }, [userId, checkProfileSetup]);

    if (isChecking) {
        return <ScreenLoader />;
    }

    return (
        <Stack.Navigator
            initialRouteName={hasCompletedProfileSetup ? 'MainTab' : 'ProfileSetup'}
            screenOptions={stackMotion}
        >
            <Stack.Screen name='ProfileSetup' component={AssessmentScreen} />
            <Stack.Screen name='MainTab' component={TabNavigator} options={revealMotion} />
        </Stack.Navigator>
    );
};

const AppNavigator = () => {
    // isLoading is true until restoreSession() has settled, which replaces
    // Clerk's isLoaded. App.js kicks that off on mount.
    const isLoading = useAuthStore(state => state.isLoading);
    const isAuthenticated = useAuthStore(state => state.isAuthenticated);

    // A plain loader while the saved session restores: the swipe-to-start splash
    // belongs to onboarding (AuthNavigator), not to every launch of a signed-in app.
    if (isLoading) {
        return <ScreenLoader />;
    }

    return isAuthenticated ? <SignedInStack /> : <AuthNavigator />;
}

export default AppNavigator;
