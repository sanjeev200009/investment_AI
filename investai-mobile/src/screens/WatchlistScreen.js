import TouchableTick from '../components/TouchableTick';
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import Svg, { Path, Defs, LinearGradient, Stop } from 'react-native-svg';

const colors = {
  background: '#faf9fc',
  surface: '#faf9fc',
  surfaceLowest: '#ffffff',
  surfaceHigh: '#e8e8ea',
  surfaceHighest: '#e3e2e5',
  surfaceLow: '#f4f3f6',
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
  errorContainer: '#ffdad6',
  cardShadow: 'rgba(28, 61, 90, 0.06)'
};

const Sparkline = ({ type }) => {
  const isPositive = type === 'positive';
  const color = isPositive ? colors.primary : colors.error;
  
  // Custom paths based on the HTML mockup
  const pathDataPositive = isPositive ? "M0,35 Q20,30 40,20 T60,10 T80,15 T100,0" : "";
  const areaDataPositive = isPositive ? "M0,40 L0,35 Q20,30 40,20 T60,10 T80,15 T100,0 L100,40 Z" : "";
  
  const pathDataNegative = !isPositive ? "M0,5 Q20,10 40,25 T60,20 T80,35 T100,30" : "";
  const areaDataNegative = !isPositive ? "M0,40 L0,5 Q20,10 40,25 T60,20 T80,35 T100,30 L100,40 Z" : "";

  return (
    <Svg width="100%" height="100%" viewBox="0 0 100 40" style={{ overflow: 'visible' }}>
      <Defs>
        <LinearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <Stop offset="100%" stopColor={color} stopOpacity="0" />
        </LinearGradient>
      </Defs>
      <Path 
        d={isPositive ? areaDataPositive : areaDataNegative} 
        fill="url(#grad)" 
      />
      <Path 
        d={isPositive ? pathDataPositive : pathDataNegative} 
        fill="none" 
        stroke={color} 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
      />
    </Svg>
  );
};

export default function WatchlistScreen({ navigation }) {
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />
      
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.avatarContainer}>
            <Image
              source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDDa3cQcIjXoyP021tAFMl_zjrDDmaIz3C9LAsqV4mR4TGV84xro9ZduAuJhnlH_H4WAWF_6BGvig8MwPu-t4WbULnUAjST-Aov3H32h5pqwEPzleEcsMp8GeXIQqomlQ-mOZvhItUsUZp4GFv1KYC33NMmA_HfqBAeHAgGdNC8PXXGTTWo95RX5TpPch0HD7xy4gg_WVGy3gi_yb3UcByzSspdVF1Dm6n3lcu7nwPiZlM-LZOCv1rO8AHrOOuhG1h4u2-hvVNqAXA' }}
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
            <Text style={styles.pageTitle}>Watchlist</Text>
            <Text style={styles.pageSubtitle}>AI-monitored assets</Text>
          </View>
          <TouchableTick style={styles.sortBtn}>
            <MaterialIcons name="sort" size={18} color={colors.primary} />
            <Text style={styles.sortBtnText}>Sort</Text>
          </TouchableTick>
        </View>

        <View style={styles.cardsGrid}>
          {/* AAPL Card */}
          <TouchableTick style={styles.card}>
            <View style={styles.cardTop}>
              <View style={styles.cardHeaderLeft}>
                <View style={styles.tickerBox}>
                  <Text style={styles.tickerBoxText}>AAPL</Text>
                </View>
                <View>
                  <Text style={styles.companyName}>Apple Inc.</Text>
                  <Text style={styles.sectorText}>Technology</Text>
                </View>
              </View>
              <MaterialIcons name="star" size={20} color={colors.primary} />
            </View>
            <View style={styles.cardBottom}>
              <View>
                <Text style={styles.priceText}>$189.43</Text>
                <View style={styles.changeBadgePos}>
                  <MaterialIcons name="trending-up" size={16} color={colors.primary} />
                  <Text style={styles.changeTextPos}>+1.24%</Text>
                </View>
              </View>
              <View style={styles.sparklineContainer}>
                <Sparkline type="positive" />
              </View>
            </View>
          </TouchableTick>

          {/* MSFT Card */}
          <TouchableTick style={styles.card}>
            <View style={styles.cardTop}>
              <View style={styles.cardHeaderLeft}>
                <View style={styles.tickerBox}>
                  <Text style={styles.tickerBoxText}>MSFT</Text>
                </View>
                <View>
                  <Text style={styles.companyName}>Microsoft Corp.</Text>
                  <Text style={styles.sectorText}>Technology</Text>
                </View>
              </View>
              <MaterialIcons name="star" size={20} color={colors.primary} />
            </View>
            <View style={styles.cardBottom}>
              <View>
                <Text style={styles.priceText}>$415.20</Text>
                <View style={styles.changeBadgePos}>
                  <MaterialIcons name="trending-up" size={16} color={colors.primary} />
                  <Text style={styles.changeTextPos}>+0.85%</Text>
                </View>
              </View>
              <View style={styles.sparklineContainer}>
                <Sparkline type="positive" />
              </View>
            </View>
          </TouchableTick>

          {/* TSLA Card */}
          <TouchableTick style={styles.card}>
            <View style={styles.cardTop}>
              <View style={styles.cardHeaderLeft}>
                <View style={styles.tickerBox}>
                  <Text style={styles.tickerBoxText}>TSLA</Text>
                </View>
                <View>
                  <Text style={styles.companyName}>Tesla Inc.</Text>
                  <Text style={styles.sectorText}>Automotive</Text>
                </View>
              </View>
              <MaterialIcons name="star" size={20} color={colors.primary} />
            </View>
            <View style={styles.cardBottom}>
              <View>
                <Text style={styles.priceText}>$175.34</Text>
                <View style={styles.changeBadgeNeg}>
                  <MaterialIcons name="trending-down" size={16} color={colors.error} />
                  <Text style={styles.changeTextNeg}>-2.14%</Text>
                </View>
              </View>
              <View style={styles.sparklineContainer}>
                <Sparkline type="negative" />
              </View>
            </View>
            <View style={styles.aiAlertChip}>
              <MaterialIcons name="psychology" size={12} color={colors.onPrimary} />
              <Text style={styles.aiAlertText}>Volatility Alert</Text>
            </View>
          </TouchableTick>

          {/* NVDA Card */}
          <TouchableTick style={styles.card}>
            <View style={styles.cardTop}>
              <View style={styles.cardHeaderLeft}>
                <View style={styles.tickerBox}>
                  <Text style={styles.tickerBoxText}>NVDA</Text>
                </View>
                <View>
                  <Text style={styles.companyName}>NVIDIA Corp.</Text>
                  <Text style={styles.sectorText}>Technology</Text>
                </View>
              </View>
              <MaterialIcons name="star" size={20} color={colors.primary} />
            </View>
            <View style={styles.cardBottom}>
              <View>
                <Text style={styles.priceText}>$885.12</Text>
                <View style={styles.changeBadgePos}>
                  <MaterialIcons name="trending-up" size={16} color={colors.primary} />
                  <Text style={styles.changeTextPos}>+3.45%</Text>
                </View>
              </View>
              <View style={styles.sparklineContainer}>
                <Sparkline type="positive" />
              </View>
            </View>
          </TouchableTick>
        </View>

        {/* Quick Add */}
        <View style={styles.quickAddContainer}>
          <TouchableTick style={styles.quickAddBtn}>
            <MaterialIcons name="add" size={20} color={colors.onPrimary} />
            <Text style={styles.quickAddText}>Add Asset</Text>
          </TouchableTick>
        </View>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
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
    backgroundColor: colors.surfaceHighest,
    overflow: 'hidden',
  },
  avatar: {
    width: '100%',
    height: '100%',
  },
  headerTitle: {
    fontSize: 24,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  settingsBtn: {
    padding: 8,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 120,
  },
  pageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: 24,
  },
  pageTitle: {
    fontSize: 32,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
    letterSpacing: -0.5,
  },
  pageSubtitle: {
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurfaceVariant,
    marginTop: 4,
  },
  sortBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  sortBtnText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    color: colors.primary,
  },
  cardsGrid: {
    gap: 20,
  },
  card: {
    backgroundColor: colors.surfaceLowest,
    borderRadius: 12,
    padding: 20,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 30,
    elevation: 10,
    position: 'relative',
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  cardHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  tickerBox: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: colors.surfaceLow,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tickerBoxText: {
    fontSize: 18,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  companyName: {
    fontSize: 18,
    fontFamily: 'Satoshi-Bold',
    color: colors.onSurface,
  },
  sectorText: {
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
  },
  cardBottom: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  priceText: {
    fontSize: 36,
    fontFamily: 'Satoshi-Bold',
    color: colors.onSurface,
    letterSpacing: -1,
    lineHeight: 40,
  },
  changeBadgePos: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(218, 227, 245, 0.3)', // secondary-container / 30
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    marginTop: 8,
    alignSelf: 'flex-start',
    gap: 4,
  },
  changeTextPos: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    color: colors.primary,
  },
  changeBadgeNeg: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 218, 214, 0.3)', // error-container / 30
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    marginTop: 8,
    alignSelf: 'flex-start',
    gap: 4,
  },
  changeTextNeg: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    color: colors.error,
  },
  sparklineContainer: {
    width: 96,
    height: 48,
  },
  aiAlertChip: {
    position: 'absolute',
    bottom: -12,
    right: 20,
    backgroundColor: colors.primary,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 16,
    gap: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 4,
    elevation: 10,
  },
  aiAlertText: {
    color: colors.onPrimary,
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
  },
  quickAddContainer: {
    marginTop: 32,
    alignItems: 'center',
  },
  quickAddBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 8,
    elevation: 10,
  },
  quickAddText: {
    color: colors.onPrimary,
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
  }
});
