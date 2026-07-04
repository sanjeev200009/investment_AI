// src/components/TouchableTick.js
import React from 'react';
import { TouchableOpacity, Platform } from 'react-native';
import * as Haptics from 'expo-haptics';

export default function TouchableTick(props) {
    const handlePress = (e) => {
        // Trigger a light, satisfying physical "tick" feeling
        if (Platform.OS !== 'web') {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        }
        
        // Execute original onPress if provided
        if (props.onPress) {
            props.onPress(e);
        }
    };

    return (
        <TouchableOpacity 
            {...props} 
            onPress={handlePress}
            activeOpacity={props.activeOpacity || 0.7}
        >
            {props.children}
        </TouchableOpacity>
    );
}
