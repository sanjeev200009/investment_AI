// src/components/AppButton.js
import React from 'react';
import {
    TouchableOpacity,
    Text,
    StyleSheet,
    ActivityIndicator,
    View
} from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

/**
 * Reusable Button component that implements the design system tokens.
 * Supports primary, secondary, disabled, and loading states.
 */
const AppButton = ({
    title,
    onPress,
    variant = 'primary',
    loading = false,
    disabled = false,
    style,
    textStyle,
    icon
}) => {
    const theme = useAppTheme();

    const isSecondary = variant === 'secondary';
    const isDisabled = disabled || loading;

    const containerStyle = [
        styles.button,
        {
            backgroundColor: isSecondary ? 'transparent' : theme.colors.primary,
            borderColor: isSecondary ? theme.colors.divider : 'transparent',
            borderWidth: isSecondary ? 1 : 0,
            opacity: isDisabled ? 0.6 : 1,
            borderRadius: theme.radii.xl,
            height: 64,
        },
        !isSecondary && !isDisabled && theme.shadows,
        style
    ];

    const labelStyle = [
        styles.text,
        {
            color: isSecondary ? theme.colors.textPrimary : '#FFFFFF',
            fontSize: theme.typography.sizes.button,
            fontWeight: theme.typography.weights.semiBold,
        },
        textStyle
    ];

    return (
        <TouchableOpacity
            activeOpacity={0.8}
            onPress={onPress}
            disabled={isDisabled}
            style={containerStyle}
        >
            {loading ? (
                <ActivityIndicator color={isSecondary ? theme.colors.primary : '#FFFFFF'} />
            ) : (
                <View style={styles.content}>
                    {icon && <View style={styles.icon}>{icon}</View>}
                    <Text style={labelStyle}>{title}</Text>
                </View>
            )}
        </TouchableOpacity>
    );
};

const styles = StyleSheet.create({
    button: {
        justifyContent: 'center',
        alignItems: 'center',
        width: '100%',
    },
    content: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    text: {
        textAlign: 'center',
    },
    icon: {
        marginRight: 10,
    }
});

export default AppButton;
