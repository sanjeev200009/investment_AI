// src/components/QuickAction.js
import React from 'react';
import { TouchableOpacity, Text, StyleSheet, View } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';

const QuickAction = ({ icon, label, onPress, color }) => {
    const theme = useAppTheme();

    return (
        <TouchableOpacity style={styles.container} onPress={onPress} activeOpacity={0.7}>
            <View style={[
                styles.iconWrapper,
                { backgroundColor: color ? `${color}20` : theme.isDark ? theme.colors.border : theme.colors.background }
            ]}>
                <MaterialIcons name={icon} size={24} color={color || theme.colors.textPrimary} />
            </View>
            <Text style={[styles.label, { color: theme.colors.textPrimary }]}>{label}</Text>
        </TouchableOpacity>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        alignItems: 'center',
        gap: 8,
        padding: 8,
    },
    iconWrapper: {
        width: 56,
        height: 56,
        borderRadius: 28,
        justifyContent: 'center',
        alignItems: 'center',
    },
    label: {
        fontSize: 13,
        fontWeight: '500',
        textAlign: 'center',
    },
});

export default QuickAction;
