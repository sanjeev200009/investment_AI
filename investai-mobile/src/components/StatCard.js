// src/components/StatCard.js
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import AppCard from './AppCard';
import { useAppTheme } from '../hooks/useAppTheme';

const StatCard = ({ title, value, change, isPositive = true, variant = '3d', children }) => {
    const theme = useAppTheme();

    return (
        <AppCard style={styles.card} variant={variant}>
            <View style={styles.mainInfo}>
                <Text style={[styles.title, { color: theme.colors.textSecondary }]}>{title}</Text>
                <Text style={[styles.value, { color: theme.colors.textPrimary }]}>{value}</Text>
                <Text style={[
                    styles.change,
                    { color: isPositive ? theme.colors.success : theme.colors.error }
                ]}>
                    {isPositive ? '+' : ''}{change}
                </Text>
            </View>

            {children && (
                <>
                    <View style={[styles.divider, { backgroundColor: theme.colors.divider }]} />
                    {children}
                </>
            )}
        </AppCard>
    );
};

const styles = StyleSheet.create({
    card: {
        marginHorizontal: 16,
        padding: 20,
    },
    mainInfo: {
        gap: 4,
    },
    title: {
        fontSize: 14,
        fontWeight: '500',
    },
    value: {
        fontSize: 28,
        fontWeight: '700',
        letterSpacing: -0.5,
    },
    change: {
        fontSize: 16,
        fontWeight: '600',
    },
    divider: {
        height: 1,
        marginVertical: 16,
    },
});

export default StatCard;
