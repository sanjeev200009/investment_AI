// src/components/AppInput.js
import React from 'react';
import {
    View,
    TextInput,
    Text,
    StyleSheet
} from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

/**
 * Reusable input component that implements the design system tokens.
 * Automatically handles dark mode, errors, and standardized spacing.
 */
const AppInput = ({
    label,
    error,
    icon,
    style,
    ...props
}) => {
    const theme = useAppTheme();

    return (
        <View style={[styles.container, style]}>
            {label && (
                <Text style={[styles.label, { color: theme.colors.textSecondary, marginBottom: theme.spacing.sm }]}>
                    {label}
                </Text>
            )}

            <View style={[
                styles.inputWrapper,
                {
                    backgroundColor: theme.colors.field,
                    borderColor: error ? theme.colors.error : theme.colors.border,
                    borderWidth: theme.isDark ? 0 : 1,
                    borderRadius: theme.radii.lg,
                    paddingHorizontal: theme.spacing.lg,
                    height: 64,
                }
            ]}>
                {icon && <View style={styles.icon}>{icon}</View>}
                <TextInput
                    placeholderTextColor={theme.colors.textSecondary}
                    style={[
                        styles.input,
                        {
                            color: theme.colors.textPrimary,
                            fontSize: theme.typography.sizes.body1,
                        }
                    ]}
                    {...props}
                />
            </View>

            {error && (
                <Text style={[styles.error, { color: theme.colors.error, marginTop: theme.spacing.xs }]}>
                    {error}
                </Text>
            )}
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        width: '100%',
    },
    inputWrapper: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    input: {
        flex: 1,
    },
    icon: {
        marginRight: 12,
    },
    label: {
        fontSize: 14,
        fontWeight: '500',
    },
    error: {
        fontSize: 12,
    }
});

export default AppInput;
