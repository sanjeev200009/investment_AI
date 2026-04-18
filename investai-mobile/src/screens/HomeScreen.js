import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';
import AppHeader from '../components/AppHeader';
import MarketStatus from '../components/MarketStatus';
import StatCard from '../components/StatCard';
import QuickAction from '../components/QuickAction';
import InsightCard from '../components/InsightCard';
import AppCard from '../components/AppCard';

export default function HomeScreen({ navigation }) {
  const theme = useAppTheme();

  const insights = [
    { id: '1', title: 'Tech Sector Outlook', description: 'Growth trends for 2024', type: 'Analysis' },
    { id: '2', title: 'Market Volatility', description: 'How to navigate swings', type: 'Guide' },
  ];

  const watchlist = [
    { id: '1', symbol: 'AAPL', name: 'Apple Inc.', price: '$191.03', change: '+1.2%', isPositive: true },
    { id: '2', symbol: 'TSLA', name: 'Tesla Inc.', price: '$245.50', change: '-0.8%', isPositive: false },
  ];

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />
      <AppHeader
        title=""
        style={{ paddingBottom: 0 }}
        titleContainerStyle={{ flex: 4, alignItems: 'flex-start' }}
        rightAction={(
          <TouchableOpacity
            style={[styles.notifyBtn, { backgroundColor: theme.isDark ? theme.colors.surface : theme.colors.field }]}
            onPress={() => navigation.navigate('Notifications')}
          >
            <MaterialIcons name="notifications-none" size={24} color={theme.colors.textPrimary} />
          </TouchableOpacity>
        )}
      >
        <View style={styles.headerLeft}>
          <TouchableOpacity onPress={() => navigation.navigate('Auth')}>
            <Image
              source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDzcb4VwaI0hN68dK26osK6CXFM_SHkJuVrwUzMMSF9FS_N5Z9h5pGpeHrKAgrbmaOjYtKCX5r_7hfgPRnz_n8swoBtS2KsYCIbLSxCVID9OMPO1RZmjhbjf1YG7ikiBPl24_RLugElV1gfIZHmF5ejbSq3jWqiXL_VbqIdW-fJenXpWbGY5NYkO5hSYC89tkNlRa60LAcQunkeFHBDwejSV8nu0dlz757qky0iGcKRykKM6SSlAgIAvtYBjldDWiImPrcaIxbc4oE' }}
              style={styles.avatar}
            />
          </TouchableOpacity>
          <View>
            <View style={styles.greetingRow}>
              <Text style={[styles.greeting, { color: theme.colors.textPrimary }]}>Good morning, Sanjaya!</Text>
              <TouchableOpacity style={styles.loginTag} onPress={() => navigation.navigate('Auth')}>
                <Text style={[styles.loginText, { color: theme.colors.primary }]}>Login</Text>
              </TouchableOpacity>
            </View>
            <Text style={[styles.date, { color: theme.colors.textSecondary }]}>September 24, 2023</Text>
          </View>
        </View>
      </AppHeader>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        <MarketStatus isOpen={true} />

        <StatCard
          title="ASPI Index"
          value="12,450.78"
          change="1.25%"
          isPositive={true}
        >
          <View style={styles.statsGrid}>
            <View style={styles.miniStat}>
              <Text style={[styles.miniStatLabel, { color: theme.colors.textSecondary }]}>Top Gainers</Text>
              <Text style={[styles.miniStatValue, { color: theme.colors.textPrimary }]}>AAPL</Text>
              <Text style={[styles.miniStatChange, { color: theme.colors.success }]}>+2.5%</Text>
            </View>
            <View style={styles.miniStat}>
              <Text style={[styles.miniStatLabel, { color: theme.colors.textSecondary }]}>Top Losers</Text>
              <Text style={[styles.miniStatValue, { color: theme.colors.textPrimary }]}>GOOGL</Text>
              <Text style={[styles.miniStatChange, { color: theme.colors.error }]}>-1.8%</Text>
            </View>
          </View>
        </StatCard>

        <View style={styles.actionsGrid}>
          <QuickAction icon="smart-toy" label="Ask AI" color="#0052FF" />
          <QuickAction icon="trending-up" label="Browse" />
          <QuickAction icon="pie-chart" label="Portfolio" />
          <QuickAction icon="notifications-active" label="Alerts" onPress={() => navigation.navigate('Notifications')} />
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.insightsScroll}
        >
          {insights.map(item => (
            <InsightCard key={item.id} {...item} />
          ))}
        </ScrollView>

        <View style={styles.watchlistSection}>
          <View style={styles.sectionHeader}>
            <Text style={[styles.sectionTitle, { color: theme.colors.textPrimary }]}>My Watchlist</Text>
            <TouchableOpacity>
              <Text style={[styles.viewAll, { color: theme.colors.primary }]}>View All</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.watchlistItems}>
            {watchlist.map(item => (
              <AppCard key={item.id} variant="3d" style={styles.watchlistItemCard}>
                <View style={styles.watchlistItem}>
                  {/* Left: Symbol & Name */}
                  <View style={styles.itemLeft}>
                    <View style={[styles.symbolBadge, {
                      backgroundColor: theme.colors.field,
                      borderColor: theme.colors.divider
                    }]}>
                      <Text style={[styles.symbolText, { color: theme.colors.textPrimary }]}>{item.symbol}</Text>
                    </View>
                    <View>
                      <Text style={[styles.itemName, { color: theme.colors.textPrimary }]}>{item.name}</Text>
                      <Text style={[styles.itemMarket, { color: theme.colors.textSecondary }]}>NasdaqGS</Text>
                    </View>
                  </View>

                  {/* Middle: Price & Change */}
                  <View style={styles.itemMiddle}>
                    <Text style={[styles.itemPrice, { color: theme.colors.textPrimary }]}>{item.price}</Text>
                    <Text style={[styles.itemChange, { color: item.isPositive ? '#22C55E' : '#EF4444' }]}>
                      {item.isPositive ? '+' : ''}{item.change}
                    </Text>
                  </View>

                  {/* Right: Trend Indicator */}
                  <View style={styles.itemRight}>
                    <View style={[styles.trendBox, {
                      backgroundColor: item.isPositive ? 'rgba(34, 197, 94, 0.05)' : 'rgba(239, 68, 68, 0.05)',
                      borderColor: item.isPositive ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)'
                    }]}>
                      <MaterialIcons
                        name={item.isPositive ? "trending-up" : "trending-down"}
                        size={16}
                        color={item.isPositive ? '#22C55E' : '#EF4444'}
                      />
                    </View>
                  </View>
                </View>
              </AppCard>
            ))}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  notifyBtn: { padding: 8, borderRadius: 12 },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 44, height: 44, borderRadius: 22 },
  greetingRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  greeting: { fontSize: 16, fontWeight: '700' },
  loginTag: { backgroundColor: 'rgba(0, 82, 255, 0.08)', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  loginText: { fontSize: 11, fontWeight: '700' },
  date: { fontSize: 12, marginTop: 2 },
  scrollContent: { padding: 16, paddingBottom: 100 },
  statsGrid: { flexDirection: 'row', gap: 12, marginTop: 16 },
  miniStat: { flex: 1, padding: 12, borderRadius: 8, backgroundColor: 'rgba(0,0,0,0.02)' },
  miniStatLabel: { fontSize: 10, fontWeight: '600', marginBottom: 4 },
  miniStatValue: { fontSize: 14, fontWeight: '700' },
  miniStatChange: { fontSize: 12, fontWeight: '600' },
  actionsGrid: { flexDirection: 'row', gap: 12, marginTop: 20 },
  insightsScroll: { paddingVertical: 20, gap: 16 },
  watchlistSection: { marginTop: 8 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  sectionTitle: { fontSize: 20, fontWeight: '800', letterSpacing: -0.5 },
  viewAll: { fontSize: 14, fontWeight: '600' },
  watchlistItems: { gap: 16 },
  watchlistItemCard: { padding: 0 },
  watchlistItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16 },
  itemLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  symbolBadge: { width: 48, height: 48, borderRadius: 12, borderWidth: 1, justifyContent: 'center', alignItems: 'center' },
  symbolText: { fontSize: 14, fontWeight: '700' },
  itemName: { fontSize: 15, fontWeight: '700' },
  itemMarket: { fontSize: 11, fontWeight: '500', marginTop: 2 },
  itemMiddle: { alignItems: 'flex-end' },
  itemPrice: { fontSize: 15, fontWeight: '700' },
  itemChange: { fontSize: 13, fontWeight: '600', marginTop: 2 },
  itemRight: { marginLeft: 16 },
  trendBox: { width: 32, height: 32, borderRadius: 8, borderWidth: 1, justifyContent: 'center', alignItems: 'center' },
});

