import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  SafeAreaView,
  StatusBar,
  Image,
  Dimensions,
  Platform
} from 'react-native';
import { SafeAreaView as SafeAreaContextView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';
import AppHeader from '../components/AppHeader';
import AppCard from '../components/AppCard';
import { PieChart } from 'react-native-chart-kit';

const HOLDINGS = [
  {
    id: '1',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    shares: '10 shares',
    value: '$1,910.30',
    gain: '+$230.15',
    isPositive: true,
    logo: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBBT19kQaxWFQamxv0rDskBrL6SXLu793rftKFdeJVL6Q4NiqHfYH58CErkcwwClkVfcq0kQRp4gdSX4HZdLwf0jvooTKYakeTQ7alkO3h7bXEZNP79fY3Ut6_NnCMW-kQafHcHCNraHtNse77dscE9DRRy0S5zwqdsXZ3Xj1UhrMQxt41Wsh1ZZg6tPYkL9JzmwjlAEMJ0_EZWJBcqFko-FuyAXo6uO0mzhJF7WAe7LvmUwliPj2jFGkfAhSPpLD8fYLzsaV3YX0c'
  },
  {
    id: '2',
    symbol: 'MSFT',
    name: 'Microsoft Corp.',
    shares: '5 shares',
    value: '$2,145.75',
    gain: '+$188.50',
    isPositive: true,
    logo: 'https://lh3.googleusercontent.com/aida-public/AB6AXuA9DNckfeHKFGDHnwCMRCkYJ8LuRZrEVQ3G307sz_HwMDxUTDUohxyLtAg1ij9r76K1wWqNJRq7OC7bP5D_4FK8hFfjp-LzdVOVhLgoPmzPt0L1pgQSw4c56Pz54MDnVFlpYAPjOn-Mmo78gcJ3uv8NQBsTRQtqniuHrE35957jyj3LTzZR-n9S49yOwwXHOLPBBn6kaSdKqYKuc5f3HxwYvRbH34ecSvdGlk5zv1v-BxGZSKtPWzaJyU2rSu9NLfkryWl8y9CFZNJM'
  },
  {
    id: '3',
    symbol: 'AMZN',
    name: 'Amazon.com Inc.',
    shares: '8 shares',
    value: '$1,480.00',
    gain: '-$45.20',
    isPositive: false,
    logo: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDGP74uUD1aHcM5TORfU2HQfDfZUJZIf5bZQdb15jFEMqkqWUJYT9YEvcILqI7ufUAXyXpz-fEQro4c75t_kUV6e3B7zrjXcslL7G1XiNoO29LqaNwg0xfGdmdjBjmcK-ks572LzT2ITxIq4GETyjjcr3qZ_LGjfIRR2RnfbDa8MQ1u9F2AhCuvFK0N0gKyUqDmcAwzyJ6vpwmK2ChTYTHiQmys8muzaVyXrD9IeW2QyAIjdaIHQQ3Ufef5fg9l9FbuzLk1kJjmGU8'
  }
];

const SECTOR_DATA = [
  { name: 'Technology', population: 45, color: '#0052FF', legendFontColor: '#7F7F7F', legendFontSize: 12 },
  { name: 'Healthcare', population: 25, color: '#4CAF50', legendFontColor: '#7F7F7F', legendFontSize: 12 },
  { name: 'Finance', population: 20, color: '#9C27B0', legendFontColor: '#7F7F7F', legendFontSize: 12 },
  { name: 'Consumer', population: 10, color: '#FFC107', legendFontColor: '#7F7F7F', legendFontSize: 12 },
];

export default function PortfolioScreen({ navigation }) {
  const theme = useAppTheme();
  const [activeTab, setActiveTab] = useState('Holdings');

  const chartConfig = {
    color: (opacity = 1) => `rgba(255, 255, 255, ${opacity})`,
  };

  return (
    <SafeAreaContextView style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />
      <AppHeader
        title="My Portfolio"
        rightAction={
          <TouchableOpacity style={styles.headerBtn}>
            <MaterialIcons name="refresh" size={24} color={theme.colors.textPrimary} />
          </TouchableOpacity>
        }
      />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* Total Value Card */}
        <AppCard style={styles.valueCard}>
          <Text style={[styles.label, { color: theme.colors.textSecondary }]}>Total Value</Text>
          <Text style={[styles.totalValue, { color: theme.colors.textPrimary }]}>$12,480.50</Text>

          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>Total Gain/Loss</Text>
              <Text style={[styles.statValue, { color: theme.colors.success }]}>
                +$1,230.10 <Text style={styles.statPercent}>(+10.9%)</Text>
              </Text>
            </View>
            <View style={styles.statItem}>
              <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>Today's Change</Text>
              <Text style={[styles.statValue, { color: theme.colors.error }]}>
                -$52.18 <Text style={styles.statPercent}>(-0.42%)</Text>
              </Text>
            </View>
          </View>
        </AppCard>

        <Text style={styles.updateTime}>Updated 5 min ago</Text>

        {/* Sector Allocation */}
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: theme.colors.textPrimary }]}>Sector Allocation</Text>
        </View>
        <AppCard style={styles.chartCard}>
          <View style={styles.chartWrapper}>
            <PieChart
              data={SECTOR_DATA}
              width={Dimensions.get('window').width - 64}
              height={180}
              chartConfig={chartConfig}
              accessor="population"
              backgroundColor="transparent"
              paddingLeft="0"
              absolute
              hasLegend={false}
            />
            <View style={styles.chartCenter}>
              <Text style={[styles.chartCenterValue, { color: theme.colors.textPrimary }]}>100%</Text>
              <Text style={[styles.chartCenterLabel, { color: theme.colors.textSecondary }]}>Total</Text>
            </View>
          </View>

          <View style={styles.legendContainer}>
            {SECTOR_DATA.map((item, index) => (
              <View key={index} style={styles.legendItem}>
                <View style={styles.legendLeft}>
                  <View style={[styles.legendDot, { backgroundColor: item.color }]} />
                  <Text style={[styles.legendName, { color: theme.colors.textPrimary }]}>{item.name}</Text>
                </View>
                <Text style={[styles.legendValue, { color: theme.colors.textSecondary }]}>{item.population}%</Text>
              </View>
            ))}
          </View>
        </AppCard>

        {/* Tabs */}
        <View style={[styles.tabContainer, { borderBottomColor: theme.colors.divider }]}>
          {['Holdings', 'Transactions', 'Performance'].map(tab => (
            <TouchableOpacity
              key={tab}
              onPress={() => setActiveTab(tab)}
              style={[styles.tab, activeTab === tab && { borderBottomColor: theme.colors.primary }]}
            >
              <Text style={[
                styles.tabText,
                { color: activeTab === tab ? theme.colors.primary : theme.colors.textSecondary }
              ]}>
                {tab}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Holdings Header */}
        <View style={styles.listHeader}>
          <Text style={[styles.listHeaderLabel, { color: theme.colors.textSecondary, flex: 2 }]}>Symbol</Text>
          <Text style={[styles.listHeaderLabel, { color: theme.colors.textSecondary, textAlign: 'right', flex: 3 }]}>Value / Gain</Text>
        </View>

        {/* Holdings List */}
        <View style={styles.holdingsList}>
          {HOLDINGS.map(item => (
            <TouchableOpacity key={item.id} style={[styles.holdingItem, { backgroundColor: theme.colors.surface, borderColor: theme.colors.divider }]}>
              <View style={styles.holdingLeft}>
                <View style={[styles.logoWrapper, { backgroundColor: theme.isDark ? '#1F2937' : '#F3F4F6' }]}>
                  <Image source={{ uri: item.logo }} style={styles.logo} />
                </View>
                <View>
                  <Text style={[styles.symbolText, { color: theme.colors.textPrimary }]}>{item.symbol}</Text>
                  <Text style={[styles.sharesText, { color: theme.colors.textSecondary }]}>{item.shares}</Text>
                </View>
              </View>
              <View style={styles.holdingRight}>
                <Text style={[styles.valueText, { color: theme.colors.textPrimary }]}>{item.value}</Text>
                <Text style={[styles.gainText, { color: item.isPositive ? theme.colors.success : theme.colors.error }]}>
                  {item.gain}
                </Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Footer Button */}
      <View style={[styles.footer, { backgroundColor: theme.colors.background, borderTopColor: theme.colors.divider }]}>
        <TouchableOpacity style={[styles.settingsBtn, { backgroundColor: theme.colors.primary }]}>
          <MaterialIcons name="settings" size={20} color="#FFFFFF" />
          <Text style={styles.settingsBtnText}>Auto-Invest Settings</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaContextView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  headerBtn: {
    padding: 8,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingBottom: 100,
  },
  valueCard: {
    marginTop: 16,
    padding: 24,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
  },
  totalValue: {
    fontSize: 36,
    fontWeight: '800',
    marginTop: 4,
    letterSpacing: -1,
  },
  statsRow: {
    flexDirection: 'row',
    marginTop: 24,
    justifyContent: 'space-between',
  },
  statItem: {
    flex: 1,
  },
  statLabel: {
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 4,
  },
  statValue: {
    fontSize: 16,
    fontWeight: '700',
  },
  statPercent: {
    fontSize: 14,
    fontWeight: '500',
  },
  updateTime: {
    textAlign: 'center',
    fontSize: 12,
    color: '#6B7280',
    marginVertical: 12,
  },
  sectionHeader: {
    marginTop: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  chartCard: {
    padding: 16,
  },
  chartWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  chartCenter: {
    position: 'absolute',
    alignItems: 'center',
  },
  chartCenterValue: {
    fontSize: 24,
    fontWeight: '800',
  },
  chartCenterLabel: {
    fontSize: 12,
    fontWeight: '500',
  },
  legendContainer: {
    marginTop: 16,
    gap: 12,
  },
  legendItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  legendLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendName: {
    fontSize: 14,
    fontWeight: '500',
  },
  legendValue: {
    fontSize: 14,
    fontWeight: '700',
  },
  tabContainer: {
    flexDirection: 'row',
    marginTop: 24,
    borderBottomWidth: 1,
  },
  tab: {
    paddingBottom: 12,
    marginRight: 24,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
  },
  listHeader: {
    flexDirection: 'row',
    marginTop: 16,
    paddingHorizontal: 16,
  },
  listHeaderLabel: {
    fontSize: 12,
    fontWeight: '600',
  },
  holdingsList: {
    marginTop: 12,
    gap: 12,
  },
  holdingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  holdingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  logoWrapper: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logo: {
    width: 24,
    height: 24,
    resizeMode: 'contain',
  },
  symbolText: {
    fontSize: 15,
    fontWeight: '700',
  },
  sharesText: {
    fontSize: 13,
  },
  holdingRight: {
    alignItems: 'flex-end',
  },
  valueText: {
    fontSize: 15,
    fontWeight: '700',
  },
  gainText: {
    fontSize: 13,
    fontWeight: '600',
  },
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 16,
    paddingBottom: Platform.OS === 'ios' ? 32 : 16,
    borderTopWidth: 1,
  },
  settingsBtn: {
    flexDirection: 'row',
    height: 52,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    shadowColor: '#0052FF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  settingsBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
});
