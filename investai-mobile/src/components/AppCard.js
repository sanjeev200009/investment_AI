// src/components/AppCard.js
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

/**
 * Reusable card component that implements the design system tokens.
 * Handles the surface color, shadow, and border radius consistently.
 */
const AppCard = ({ children, style, ...props }) => {
    const theme = useAppTheme();

    return (
        <View
            style={[
                styles.card,
                {
                    backgroundColor: theme.colors.surface,
                    borderRadius: theme.radii.xxl,
                    ...theme.shadows
                },
                style
            ]}
            {...props}
        >
            {children}
        </View>
    );
};

const styles = StyleSheet.create({
    card: {
        padding: 24,
        // Base layout consistency
    },
});

export default AppCard;
