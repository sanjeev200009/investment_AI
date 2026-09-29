// src/navigation/AuthNavigator.js
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { stackMotion, revealMotion } from '../theme/motion';

// Screen Imports
import LoginScreen from '../screens/auth/LoginScreen';
import RegisterScreen from '../screens/auth/RegisterScreen';
import ForgotPasswordScreen from '../screens/auth/ForgotPasswordScreen';
import OTPVerificationScreen from '../screens/auth/OTPVerificationScreen';
import ResetPasswordScreen from '../screens/auth/ResetPasswordScreen';
import AuthSuccessScreen from '../screens/auth/AuthSuccessScreen';
import SplashScreen from '../screens/SplashScreen';
import LegalScreen from '../screens/LegalScreen';

const Stack = createStackNavigator();

const AuthNavigator = () => {
    return (
        <Stack.Navigator
            initialRouteName="Splash"
            screenOptions={stackMotion}
        >
            <Stack.Screen name="Splash" component={SplashScreen} />
            <Stack.Screen name="Login" component={LoginScreen} />
            <Stack.Screen name="Register" component={RegisterScreen} />
            <Stack.Screen name="ForgotPassword" component={ForgotPasswordScreen} />
            <Stack.Screen name="OTPVerification" component={OTPVerificationScreen} />
            <Stack.Screen name="ResetPassword" component={ResetPasswordScreen} />
            <Stack.Screen name="AuthSuccess" component={AuthSuccessScreen} options={revealMotion} />
            <Stack.Screen name="Legal" component={LegalScreen} />
        </Stack.Navigator>
    );
};

export default AuthNavigator;
