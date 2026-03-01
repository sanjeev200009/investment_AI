// src/components/MarketStatus.js
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';

const MarketStatus = ({ isOpen = true }) => {
    const theme = useAppTheme();

    return (
        <View style={styles.container}>
            <View style={[
                styles.badge,
                { backgroundColor: isOpen ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)' }
            ]}>
                <View style={[
                    styles.dot,
                    { backgroundColor: isOpen ? theme.colors.success : theme.colors.error }
                ]} />
                <Text style={[
                    styles.text,
                    { color: isOpen ? theme.colors.success : theme.colors.error }
                ]}>
                    {isOpen ? 'Market Open' : 'Market Closed'}
                </Text>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        paddingHorizontal: 16,
        paddingTop: 12,
        paddingBottom: 12,
    },
    badge: {
        flexDirection: 'row',
        alignItems: 'center',
        alignSelf: 'flex-start',
        paddingHorizontal: 12,
        paddingVertical: 4,
        borderRadius: 20,
        gap: 8,
    },
    dot: {
        width: 8,
        height: 8,
        borderRadius: 4,
    },
    text: {
        fontSize: 14,
        fontWeight: '600',
    },
});

export default MarketStatus;
