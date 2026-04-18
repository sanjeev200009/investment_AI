// src/components/InsightCard.js
import React from 'react';
import { View, Text, StyleSheet, Image, TouchableOpacity } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';
import AppCard from './AppCard';

const InsightCard = ({ title, subtitle, imageUri }) => {
    const theme = useAppTheme();

    return (
        <AppCard
            variant="3d"
            style={styles.card}
            containerStyle={styles.container} // Passing container style if needed, but AppCard doesn't support it yet. I'll just use style.
        >
            <TouchableOpacity activeOpacity={0.9} style={styles.touchable}>
                <Image
                    source={{ uri: imageUri }}
                    style={[styles.image, { backgroundColor: theme.colors.border }]}
                />
                <View style={styles.content}>
                    <Text style={[styles.title, { color: theme.colors.textPrimary }]} numberOfLines={1}>
                        {title}
                    </Text>
                    <Text style={[styles.subtitle, { color: theme.colors.textSecondary }]} numberOfLines={1}>
                        {subtitle}
                    </Text>
                </View>
            </TouchableOpacity>
        </AppCard>
    );
};

const styles = StyleSheet.create({
    container: {
        width: 220,
        marginRight: 16,
    },
    card: {
        padding: 12,
        marginRight: 16,
        width: 220,
    },
    touchable: {
        gap: 12,
    },
    image: {
        width: '100%',
        aspectRatio: 16 / 9,
        borderRadius: 12,
    },
    content: {
        gap: 2,
    },
    title: {
        fontSize: 15,
        fontWeight: '600',
    },
    subtitle: {
        fontSize: 13,
    },
});

export default InsightCard;
