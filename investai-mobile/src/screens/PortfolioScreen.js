import TouchableTick from '../components/TouchableTick';
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';

const colors = {
  background: '#faf9fc',
  surface: '#faf9fc',
  surfaceLowest: '#ffffff',
  surfaceHigh: '#e8e8ea',
  surfaceHighest: '#e3e2e5',
  surfaceVariant: '#e3e2e5',
  onSurface: '#1a1c1e',
  onSurfaceVariant: '#43474d',
  primary: '#002743',
  primaryFixed: '#cfe5ff',
  primaryContainer: '#1c3d5a',
  onPrimaryContainer: '#89a8ca',
  onPrimary: '#ffffff',
  secondaryContainer: '#dae3f5',
  outlineVariant: '#c3c7ce',
  error: '#ba1a1a',
  success: '#10B981', // green-600 approx
  cardShadow: 'rgba(28, 61, 90, 0.06)'
};

export default function PortfolioScreen({ navigation }) {
  const { user } = useAuthStore();
  
  const [portfolioValue, setPortfolioValue] = useState(11000);

  // Count up animation
  useEffect(() => {
    let finalValue = 12480.50;
    let startValue = finalValue * 0.9;
    const duration = 1000;
    let startTime = null;
    let animationFrame;

    const updateCount = (currentTime) => {
      if (!startTime) startTime = currentTime;
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const easeProgress = progress * (2 - progress); // ease out quad
      const currentVal = startValue + ((finalValue - startValue) * easeProgress);
      
      setPortfolioValue(currentVal);

      if (progress < 1) {
        animationFrame = requestAnimationFrame(updateCount);
      }
    };
    
    animationFrame = requestAnimationFrame(updateCount);
    return () => cancelAnimationFrame(animationFrame);
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />
      
      {/* Header (Same as Dashboard) */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.avatarContainer}>
            <Image
              source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBNFzfNPRrxUCxZZJXRl6ffGYJNVX9PuaZj-11SJfvMior8-ccm0w2YpZzni5gi9FLcP8razcqFuKpItl4C7V7RPNajZ4s4Z_MR6ZTii8bm0_Ysf5pR7308AdNtG78DaJFNeLulSabW2p1PaK1R3ctAtN9YPYMZYMlbV55WXy8wIFSZ3Pf2vjfYk3lVdwqJIriy5gtft6VN4xZkMfoUHaMlzTmbp9DCj2NmxDH7g_1NgxzJ5z6aQzkDWdBmSfP5Kg-ITOZtUEzrMhM' }}
              style={styles.avatar}
            />
          </View>
          <Text style={styles.headerTitle}>InvestAI</Text>
        </View>
        <TouchableTick style={styles.settingsBtn}>
          <MaterialIcons name="settings" size={24} color={colors.primary} />
        </TouchableTick>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        
        {/* Page Header */}
        <View style={styles.pageHeader}>
          <View>
            <Text style={styles.pageTitle}>My Portfolio</Text>
            <Text style={styles.pageSubtitle}>Real-time performance tracking</Text>
          </View>
          <TouchableTick style={styles.depositBtn}>
            <MaterialIcons name="add" size={18} color={colors.onPrimary} />
            <Text style={styles.depositBtnText}>Deposit</Text>
          </TouchableTick>
        </View>

        {/* Total Portfolio Value Card */}
        <View style={[styles.card, styles.valueCard]}>
          <View style={styles.valueCardHeader}>
            <Text style={styles.valueLabel}>Total Portfolio Value</Text>
            <View style={styles.currencyBadge}>
              <Text style={styles.currencyBadgeText}>LKR</Text>
            </View>
          </View>
          
          <Text style={styles.portfolioValue}>{portfolioValue.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</Text>
          
          <View style={styles.plRow}>
            <View style={styles.plBadge}>
              <MaterialIcons name="trending-up" size={16} color={colors.success} />
              <Text style={styles.plBadgeText}>+4.2%</Text>
            </View>
            <Text style={styles.plText}>Today's P&L: +LKR 524.18</Text>
          </View>
        </View>

        {/* AI Insight Banner */}
        <View style={styles.aiBanner}>
          <View style={styles.aiBannerBgBlur} />
          <MaterialIcons name="psychology" size={28} color={colors.secondaryContainer} />
          <View style={styles.aiBannerContent}>
            <Text style={styles.aiBannerTitle}>AI Insight</Text>
            <Text style={styles.aiBannerText}>
              Your tech allocation is up 12% this month. Consider rebalancing slightly towards Healthcare to maintain your target risk profile.
            </Text>
            <TouchableTick>
              <Text style={styles.aiBannerAction}>Review Allocation strategy</Text>
            </TouchableTick>
          </View>
        </View>

        {/* Top Holdings List */}
        <View style={styles.card}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Top Holdings</Text>
            <TouchableTick style={styles.seeAllBtn}>
              <Text style={styles.seeAllText}>See all</Text>
              <MaterialIcons name="chevron-right" size={18} color={colors.onSurfaceVariant} />
            </TouchableTick>
          </View>

          <View style={styles.holdingsList}>
            {/* Item 1 */}
            <TouchableTick style={styles.holdingItem}>
              <View style={styles.holdingItemLeft}>
                <View style={styles.holdingIconBox}>
                  <Text style={styles.holdingIconText}>AAPL</Text>
                </View>
                <View>
                  <Text style={styles.holdingName}>Apple Inc.</Text>
                  <Text style={styles.holdingShares}>14.5 Shares</Text>
                </View>
              </View>
              <View style={styles.holdingItemRight}>
                <Text style={styles.holdingPrice}>LKR 4,250.00</Text>
                <View style={styles.holdingChangeRow}>
                  <MaterialIcons name="arrow-drop-up" size={18} color={colors.success} />
                  <Text style={[styles.holdingChangeText, { color: colors.success }]}>+1.2%</Text>
                </View>
              </View>
            </TouchableTick>

            {/* Item 2 */}
            <TouchableTick style={styles.holdingItem}>
              <View style={styles.holdingItemLeft}>
                <View style={styles.holdingIconBox}>
                  <Text style={styles.holdingIconText}>MSFT</Text>
                </View>
                <View>
                  <Text style={styles.holdingName}>Microsoft Corp.</Text>
                  <Text style={styles.holdingShares}>8.2 Shares</Text>
                </View>
              </View>
              <View style={styles.holdingItemRight}>
                <Text style={styles.holdingPrice}>LKR 3,120.40</Text>
                <View style={styles.holdingChangeRow}>
                  <MaterialIcons name="arrow-drop-up" size={18} color={colors.success} />
                  <Text style={[styles.holdingChangeText, { color: colors.success }]}>+0.8%</Text>
                </View>
              </View>
            </TouchableTick>

            {/* Item 3 */}
            <TouchableTick style={styles.holdingItem}>
              <View style={styles.holdingItemLeft}>
                <View style={styles.holdingIconBox}>
                  <Text style={styles.holdingIconText}>JNJ</Text>
                </View>
                <View>
                  <Text style={styles.holdingName}>Johnson & Johnson</Text>
                  <Text style={styles.holdingShares}>22.0 Shares</Text>
                </View>
              </View>
              <View style={styles.holdingItemRight}>
                <Text style={styles.holdingPrice}>LKR 2,450.10</Text>
                <View style={styles.holdingChangeRow}>
                  <MaterialIcons name="arrow-drop-down" size={18} color={colors.error} />
                  <Text style={[styles.holdingChangeText, { color: colors.error }]}>-0.4%</Text>
                </View>
              </View>
            </TouchableTick>
          </View>
        </View>

        {/* Sector Allocation Card */}
        <View style={[styles.card, { marginBottom: 30 }]}>
          <Text style={styles.sectionTitle}>Sector Allocation</Text>
          
          <View style={styles.donutContainer}>
            {/* Minimal CSS representation of conic-gradient via borders */}
            <View style={[styles.donutRing, { borderTopColor: '#1c3d5a', borderRightColor: '#dae3f5', borderBottomColor: '#89a8ca', borderLeftColor: '#e1e2e4' }]}>
               <View style={styles.donutInner}>
                  <Text style={styles.donutCenterLabel}>Tech</Text>
                  <Text style={styles.donutCenterValue}>45%</Text>
               </View>
            </View>
          </View>

          <View style={styles.legendContainer}>
            <View style={styles.legendRow}>
              <View style={styles.legendLeft}>
                <View style={[styles.legendDot, { backgroundColor: '#1c3d5a' }]} />
                <Text style={styles.legendText}>Technology</Text>
              </View>
              <Text style={styles.legendValue}>45%</Text>
            </View>

            <View style={styles.legendRow}>
              <View style={styles.legendLeft}>
                <View style={[styles.legendDot, { backgroundColor: '#dae3f5' }]} />
                <Text style={styles.legendText}>Finance</Text>
              </View>
              <Text style={styles.legendValue}>30%</Text>
            </View>

            <View style={styles.legendRow}>
              <View style={styles.legendLeft}>
                <View style={[styles.legendDot, { backgroundColor: '#89a8ca' }]} />
                <Text style={styles.legendText}>Healthcare</Text>
              </View>
              <Text style={styles.legendValue}>15%</Text>
            </View>

            <View style={styles.legendRow}>
              <View style={styles.legendLeft}>
                <View style={[styles.legendDot, { backgroundColor: '#e1e2e4' }]} />
                <Text style={styles.legendText}>Consumer</Text>
              </View>
              <Text style={styles.legendValue}>10%</Text>
            </View>
          </View>

        </View>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    height: 64,
    backgroundColor: colors.surface,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatarContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surfaceHigh,
    overflow: 'hidden',
  },
  avatar: {
    width: '100%',
    height: '100%',
  },
  headerTitle: {
    fontSize: 24,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.primary,
  },
  settingsBtn: {
    padding: 8,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 120,
    gap: 20,
  },
  pageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: 8,
  },
  pageTitle: {
    fontSize: 20,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.onSurface,
  },
  pageSubtitle: {
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurfaceVariant,
    marginTop: 4,
  },
  depositBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primaryContainer,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 12,
    gap: 8,
  },
  depositBtnText: {
    color: colors.onPrimary,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    fontSize: 14,
  },
  card: {
    backgroundColor: colors.surfaceLowest,
    borderRadius: 12,
    padding: 24,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 30,
    elevation: 10,
  },
  valueCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  valueLabel: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.onSurfaceVariant,
  },
  currencyBadge: {
    backgroundColor: 'rgba(218, 227, 245, 0.3)', // secondary-container / 30
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  currencyBadgeText: {
    fontSize: 12,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.primaryContainer,
  },
  portfolioValue: {
    fontSize: 48,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.primaryContainer,
    letterSpacing: -1,
    marginBottom: 16,
  },
  plRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  plBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
  },
  plBadgeText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.success,
  },
  plText: {
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurfaceVariant,
  },
  aiBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.primaryContainer,
    padding: 20,
    borderRadius: 12,
    gap: 16,
    position: 'relative',
    overflow: 'hidden',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 30,
    elevation: 10,
  },
  aiBannerBgBlur: {
    position: 'absolute',
    top: -40,
    right: -40,
    width: 128,
    height: 128,
    backgroundColor: colors.secondaryContainer,
    opacity: 0.1,
    borderRadius: 64,
  },
  aiBannerContent: {
    flex: 1,
  },
  aiBannerTitle: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.secondaryContainer,
    marginBottom: 4,
  },
  aiBannerText: {
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: 'rgba(255, 255, 255, 0.9)',
    lineHeight: 24,
    marginBottom: 12,
  },
  aiBannerAction: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.onPrimary,
    textDecorationLine: 'underline',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 20,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.primaryContainer,
  },
  seeAllBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  seeAllText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.onSurfaceVariant,
  },
  holdingsList: {
    gap: 16,
  },
  holdingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  holdingItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  holdingIconBox: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: colors.surfaceHighest,
    alignItems: 'center',
    justifyContent: 'center',
  },
  holdingIconText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.primaryContainer,
  },
  holdingName: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.onSurface,
  },
  holdingShares: {
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.onSurfaceVariant,
  },
  holdingItemRight: {
    alignItems: 'flex-end',
  },
  holdingPrice: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.onSurface,
  },
  holdingChangeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 2,
  },
  holdingChangeText: {
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
  },
  donutContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 24,
  },
  donutRing: {
    width: 192,
    height: 192,
    borderRadius: 96,
    borderWidth: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  donutInner: {
    width: 144,
    height: 144,
    borderRadius: 72,
    backgroundColor: colors.surfaceLowest,
    alignItems: 'center',
    justifyContent: 'center',
  },
  donutCenterLabel: {
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurfaceVariant,
  },
  donutCenterValue: {
    fontSize: 20,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.primaryContainer,
  },
  legendContainer: {
    gap: 12,
  },
  legendRow: {
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
    width: 12,
    height: 12,
    borderRadius: 2,
  },
  legendText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    fontWeight: '500',
    color: colors.onSurface,
  },
  legendValue: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    fontWeight: '700',
    color: colors.onSurfaceVariant,
  }
});
