// src/components/AppCard.js
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

/**
 * Reusable card component that implements the design system tokens.
 * Handles the surface color, shadow, and border radius consistently.
 * Now supports a '3d' variant with depth.
 */
const AppCard = ({ children, style, variant = 'default', ...props }) => {
    const theme = useAppTheme();

    return (
        <View
            style={[
                styles.card,
                {
                    backgroundColor: theme.colors.surface,
                    borderRadius: theme.radii.xxl,
                    ...theme.shadows,
                    ...(variant === '3d' && {
                        borderWidth: 1,
                        borderColor: theme.colors.border,
                        borderBottomWidth: 4,
                        borderBottomColor: theme.isDark ? '#000' : 'rgba(0,0,0,0.1)',
                    })
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
