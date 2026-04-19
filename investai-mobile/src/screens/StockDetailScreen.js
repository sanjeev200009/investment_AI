// src/screens/StockDetailScreen.js
import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    SafeAreaView,
    StatusBar,
    Dimensions,
    Platform
} from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';
import AppHeader from '../components/AppHeader';
import AppCard from '../components/AppCard';
import ActionFeedbackModal from '../components/ActionFeedbackModal';
import { LineChart } from 'react-native-chart-kit';

const { width } = Dimensions.get('window');

const MOCK_HISTORICAL_DATA = {
    labels: ["9AM", "11AM", "1PM", "3PM", "5PM"],
    datasets: [
        {
            data: [160, 162, 161, 164.5, 163.8],
            color: (opacity = 1) => `rgba(21, 101, 192, ${opacity})`,
            strokeWidth: 3
        }
    ]
};

export default function StockDetailScreen({ route, navigation }) {
    const theme = useAppTheme();
    const { stock } = route.params || { stock: { symbol: 'HNB', name: 'HNB Bank PLC', price: '164.50', change: '+2.45%', isPositive: true } };
    const [showFeedback, setShowFeedback] = useState(false);
    const [feedbackConfig, setFeedbackConfig] = useState({});

    const handleAction = (type) => {
        if (type === 'buy') {
            setFeedbackConfig({
                title: "Order Placed",
                message: `Successfully submitted buy order for ${stock.symbol} at Rs. ${stock.price}.`,
                type: "success"
            });
        } else {
            setFeedbackConfig({
                title: "Alert Set",
                message: `You will be notified when ${stock.symbol} hits your target price.`,
                type: "info"
            });
        }
        setShowFeedback(true);
    };

    const chartConfig = {
        backgroundColor: "transparent",
        backgroundGradientFrom: theme.colors.surface,
        backgroundGradientTo: theme.colors.surface,
        decimalPlaces: 1,
        color: (opacity = 1) => stock.isPositive ? '#10B981' : '#F43F5E',
        labelColor: (opacity = 1) => theme.colors.textSecondary,
        style: { borderRadius: 16 },
        propsForDots: { r: "4", strokeWidth: "2", stroke: theme.colors.surface }
    };

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]}>
            <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />
            <AppHeader 
                title={stock.symbol} 
                onBack={() => navigation.goBack()}
                rightAction={
                    <TouchableOpacity onPress={() => handleAction('alert')}>
                        <MaterialIcons name="notifications-none" size={24} color={theme.colors.textPrimary} />
                    </TouchableOpacity>
                }
            />

            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
                {/* Price Header */}
                <View style={styles.priceHeader}>
                    <View>
                        <Text style={[styles.stockName, { color: theme.colors.textSecondary }]}>{stock.name}</Text>
                        <Text style={[styles.priceText, { color: theme.colors.textPrimary }]}>Rs. {stock.price}</Text>
                    </View>
                    <View style={[styles.changeBadge, { backgroundColor: stock.isPositive ? '#DCFCE7' : '#FEE2E2' }]}>
                        <Text style={[styles.changeText, { color: stock.isPositive ? '#15803D' : '#B91C1C' }]}>{stock.change}</Text>
                    </View>
                </View>

                {/* Chart Section */}
                <AppCard style={styles.chartCard}>
                    <Text style={[styles.sectionLabel, { color: theme.colors.textSecondary }]}>PERFORMANCE (TODAY)</Text>
                    <LineChart
                        data={MOCK_HISTORICAL_DATA}
                        width={width - 56} 
                        height={200}
                        chartConfig={chartConfig}
                        bezier
                        style={styles.chart}
                        withHorizontalLines={false}
                        withVerticalLines={false}
                    />
                </AppCard>

                {/* Key Stats */}
                <View style={styles.statsGrid}>
                    <AppCard style={styles.statBox}>
                        <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>MARKET CAP</Text>
                        <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>24.5B</Text>
                    </AppCard>
                    <AppCard style={styles.statBox}>
                        <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>P/E RATIO</Text>
                        <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>12.4</Text>
                    </AppCard>
                    <AppCard style={styles.statBox}>
                        <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>52W HIGH</Text>
                        <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>185.00</Text>
                    </AppCard>
                    <AppCard style={styles.statBox}>
                        <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>52W LOW</Text>
                        <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>142.10</Text>
                    </AppCard>
                </View>

                {/* AI Insights Card */}
                <AppCard style={styles.aiCard}>
                    <LinearGradient
                        colors={['rgba(21, 101, 192, 0.05)', 'rgba(21, 101, 192, 0.1)']}
                        style={styles.aiGradient}
                    >
                        <View style={styles.aiHeader}>
                            <MaterialCommunityIcons name="sparkles" size={20} color="#1565C0" />
                            <Text style={styles.aiTitle}>AI Analysis</Text>
                        </View>
                        <Text style={[styles.aiText, { color: theme.colors.textPrimary }]}>
                            {stock.symbol} shows strong support at Rs. 160.00. RSI indicates neutral momentum. Consider averaging in if it dips towards the support level.
                        </Text>
                    </LinearGradient>
                </AppCard>
            </ScrollView>

            {/* Action Bar */}
            <View style={[styles.actionBar, { backgroundColor: theme.colors.surface, borderTopColor: theme.colors.divider }]}>
                <TouchableOpacity style={styles.watchlistBtn}>
                    <MaterialIcons name="star-border" size={24} color={theme.colors.primary} />
                </TouchableOpacity>
                <TouchableOpacity 
                    style={[styles.buyBtn, { backgroundColor: theme.colors.primary }]}
                    onPress={() => handleAction('buy')}
                >
                    <Text style={styles.buyBtnText}>Quick Buy</Text>
                </TouchableOpacity>
            </View>

            <ActionFeedbackModal 
                visible={showFeedback} 
                onClose={() => setShowFeedback(false)}
                title={feedbackConfig.title}
                message={feedbackConfig.message}
                type={feedbackConfig.type}
            />
        </SafeAreaView>
    );
}

// Minimal LinearGradient mock if not imported
const LinearGradient = ({ children, style }) => <View style={style}>{children}</View>;

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    scrollContent: {
        paddingHorizontal: 20,
        paddingBottom: 100,
    },
    priceHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: 20,
        marginBottom: 24,
    },
    stockName: {
        fontSize: 14,
        fontWeight: '600',
        marginBottom: 4,
    },
    priceText: {
        fontSize: 32,
        fontWeight: '800',
        letterSpacing: -1,
    },
    changeBadge: {
        paddingHorizontal: 12,
        paddingVertical: 6,
        borderRadius: 8,
    },
    changeText: {
        fontSize: 15,
        fontWeight: '700',
    },
    chartCard: {
        padding: 16,
        marginBottom: 20,
    },
    sectionLabel: {
        fontSize: 12,
        fontWeight: '700',
        letterSpacing: 1,
        marginBottom: 16,
    },
    chart: {
        marginVertical: 8,
        borderRadius: 16,
        marginLeft: -16,
    },
    statsGrid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 12,
        marginBottom: 20,
    },
    statBox: {
        width: (width - 56) / 2, // 2 columns with gap taken into account
        padding: 16,
    },
    statLabel: {
        fontSize: 10,
        fontWeight: '700',
        letterSpacing: 0.5,
        marginBottom: 4,
    },
    statValue: {
        fontSize: 16,
        fontWeight: '800',
    },
    aiCard: {
        padding: 0,
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: 'rgba(21, 101, 192, 0.2)',
    },
    aiGradient: {
        padding: 20,
    },
    aiHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
        marginBottom: 10,
    },
    aiTitle: {
        fontSize: 15,
        fontWeight: '800',
        color: '#1565C0',
    },
    aiText: {
        fontSize: 14,
        lineHeight: 22,
        opacity: 0.9,
    },
    actionBar: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: Platform.OS === 'ios' ? 90 : 70,
        flexDirection: 'row',
        paddingHorizontal: 20,
        paddingTop: 12,
        borderTopWidth: 1,
        gap: 12,
    },
    watchlistBtn: {
        width: 50,
        height: 50,
        borderRadius: 12,
        borderWidth: 1.5,
        borderColor: '#E2E8F0',
        justifyContent: 'center',
        alignItems: 'center',
    },
    buyBtn: {
        flex: 1,
        height: 50,
        borderRadius: 12,
        justifyContent: 'center',
        alignItems: 'center',
        shadowColor: '#0052FF',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.2,
        shadowRadius: 8,
        elevation: 4,
    },
    buyBtnText: {
        color: '#FFFFFF',
        fontSize: 16,
        fontWeight: '700',
    }
});
