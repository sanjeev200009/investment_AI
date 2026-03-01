import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';
import { MaterialIcons } from '@expo/vector-icons';
import AppHeader from '../components/AppHeader';
import MarketStatus from '../components/MarketStatus';
import StatCard from '../components/StatCard';
import QuickAction from '../components/QuickAction';
import InsightCard from '../components/InsightCard';
import AppCard from '../components/AppCard';

export default function HomeScreen({ navigation }) {
  const theme = useAppTheme();

  const insights = [
    {
      id: '1',
      title: 'Educational Tip',
      subtitle: 'Understanding P/E Ratios',
      imageUri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC2f8V-lzTTw_BzF6lxrddQ8HXTfefX9eXJ63ZML0CqbeSauqC1SjTRImrPgYb6UkmmhtGY3mKUVuvqf3Z8RpWMT8fdIFulT683nMKLbcS9QFNclhHgJ7X22H_xO65H_4TcU6WiCDxw5PIYiU0lwXRfkVJ7OvMopUl8aXP4iz-aFqy1omy0RWrqK1dOuqxC3Tn2dF3FqH3nmX_Dz2SA5ZPFXe7wsTTutUzHoxImdOT2gD3SaBJ1X8ln9ukLy7FYD53-bHrb0kfgC6M'
    },
    {
      id: '2',
      title: 'Market Insight',
      subtitle: 'Market Trends to Watch',
      imageUri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDQqGQnLOlSpS4glYi4rEC65SQ1jzmCGNuwDtCs7yPNHEdDNkkJHYcNiP57bQdVm3yVjNuvS_GG9E3E-naJmpBdarEFp5bU67GHroGWgmbfkkU5NmKu3lL_cjhym6JPkeGWoDR7CVdYfrHyabh5Ha2AaTmE15_cuRsEaLB3KDrKwzZW3p5Q49GMSUQXGcvqVzCe6CI9c6OjoNsfYQUeLQ4fFkWO76XrPRby6a8HBzEROzxhpFSMfWGjoy9IVcntZlmsiTTTfk5NZMw'
    },
    {
      id: '3',
      title: 'Portfolio Strategy',
      subtitle: 'The Power of Diversification',
      imageUri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuA5LS7RlEKguTYI_w3pHToQFaHlR30yfpnPPp2BGFhDzXdWkWuVqvBOe86Xp9r9HZxmsUJ3elrLMKNUNfkOktA5MNa4NfrZovye54hcwGuPcYI_0WJaqPGj0U1ch0QY1JAsO_xUUJ6jkDTZcnlU49wyJEkV3zRJHBU2noTFuobi48RewgX-qvgoUsTPvTCuqsUHLVvajnx07IpNqYPFCMxBfkRND0n1tWGLEJqA2GajxOfYZDn-BpjF9Odm9YEOFZ31jZrubGeZH6w'
    }
  ];

  const watchlist = [
    { id: '1', symbol: 'TSLA', name: 'Tesla Inc.', price: '$177.48', change: '-1.20%', isPositive: false, icon: 'electric-car' },
    { id: '2', symbol: 'MSFT', name: 'Microsoft Corp.', price: '$427.56', change: '+0.85%', isPositive: true, icon: 'devices' },
    { id: '3', symbol: 'AMZN', name: 'Amazon.com, Inc.', price: '$184.70', change: '+0.55%', isPositive: true, icon: 'shopping-cart' }
  ];

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />
      <AppHeader
        title=""
        style={{ paddingBottom: 0 }}
        titleContainerStyle={{ flex: 4, alignItems: 'flex-start' }}
        rightAction={(
          <TouchableOpacity style={[styles.notifyBtn, { backgroundColor: theme.isDark ? theme.colors.surface : theme.colors.field }]}>
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
          <QuickAction icon="notifications-active" label="Alerts" />
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
                      backgroundColor: theme.isDark ? '#0F172A' : '#F1F5F9',
                      borderColor: theme.isDark ? '#1E293B' : '#E2E8F0'
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
  container: {
    flex: 1,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
  },
  greeting: {
    fontSize: 18,
    fontWeight: '700',
  },
  greetingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  loginTag: {
    backgroundColor: 'rgba(0, 82, 255, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  loginText: {
    fontSize: 12,
    fontWeight: '700',
  },
  date: {
    fontSize: 14,
  },
  notifyBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    paddingBottom: 24,
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  miniStat: {
    flex: 1,
    gap: 2,
  },
  miniStatLabel: {
    fontSize: 14,
    fontWeight: '500',
  },
  miniStatValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  miniStatChange: {
    fontSize: 14,
    fontWeight: '600',
  },
  actionsGrid: {
    flexDirection: 'row',
    padding: 16,
    justifyContent: 'space-between',
  },
  insightsScroll: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  watchlistSection: {
    paddingHorizontal: 16,
  },
  watchlistCard: {
    padding: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  viewAll: {
    fontSize: 14,
    fontWeight: '600',
  },
  watchlistItems: {
    gap: 12,
  },
  watchlistItemCard: {
    padding: 16,
  },
  watchlistItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  itemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 2,
  },
  symbolBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  symbolText: {
    fontSize: 10,
    fontWeight: '800',
  },
  itemName: {
    fontSize: 14,
    fontWeight: '700',
  },
  itemMarket: {
    fontSize: 11,
  },
  itemMiddle: {
    alignItems: 'flex-end',
    flex: 1,
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '700',
  },
  itemChange: {
    fontSize: 12,
    fontWeight: '700',
  },
  itemRight: {
    marginLeft: 12,
  },
  trendBox: {
    width: 48,
    height: 32,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
