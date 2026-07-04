import TouchableTick from '../components/TouchableTick';
import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar, ActivityIndicator, Modal, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import { useAuth, useUser } from '@clerk/clerk-expo';
import axios from 'axios';

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
  const { getToken } = useAuth();
  const { user: clerkUser } = useUser();
  
  const [portfolios, setPortfolios] = useState([]);
  const [holdings, setHoldings] = useState([]);
  const [marketData, setMarketData] = useState({});
  const [loading, setLoading] = useState(true);

  // Modal State
  const [isAddModalVisible, setAddModalVisible] = useState(false);
  const [addSymbol, setAddSymbol] = useState('');
  const [addQuantity, setAddQuantity] = useState('');
  const [addPrice, setAddPrice] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const token = await getToken();
      const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
      
      const portRes = await axios.get(`${baseUrl}/portfolio`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const marketRes = await axios.get(`${baseUrl}/stocks/market?limit=200`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setPortfolios(portRes.data || []);
      let allHoldings = [];
      if (portRes.data && portRes.data.length > 0) {
        portRes.data.forEach(p => {
           allHoldings = [...allHoldings, ...p.holdings];
        });
      }
      setHoldings(allHoldings);
      
      const marketMap = {};
      marketRes.data.forEach(stock => {
         marketMap[stock.symbol] = stock;
      });
      setMarketData(marketMap);
    } catch (err) {
      console.error("Failed to fetch portfolio data", err);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAddSubmit = async () => {
    if(!addSymbol || !addQuantity || !addPrice) return;
    setIsSubmitting(true);
    try {
        const token = await getToken();
        const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
        let pId = portfolios?.[0]?.portfolio_id;
        
        if (!pId) {
            const createRes = await axios.post(`${baseUrl}/portfolio/`, { name: 'My Primary Portfolio' }, { headers: { Authorization: `Bearer ${token}` }});
            pId = createRes.data.portfolio_id;
        }
        
        await axios.post(`${baseUrl}/portfolio/${pId}/holdings`, {
            symbol: addSymbol.toUpperCase(),
            quantity: Number(addQuantity),
            avg_buy_price: Number(addPrice)
        }, { headers: { Authorization: `Bearer ${token}` }});
        
        setAddModalVisible(false);
        setAddSymbol('');
        setAddQuantity('');
        setAddPrice('');
        fetchData();
    } catch(err) {
        console.error("Failed to add holding", err);
    } finally {
        setIsSubmitting(false);
    }
  };

  const stats = useMemo(() => {
    let totalValue = 0;
    let totalCost = 0;
    
    const sectors = { 'Finance': 0, 'Manufacturing': 0, 'Capital Goods': 0, 'Energy': 0, 'Healthcare': 0, 'Other': 0 };
    const financeMap = ['SAMP', 'HNB', 'COMB', 'SEYB', 'NDB', 'NTB', 'PABC', 'DFCC'];
    const mfgMap = ['EXPO', 'RCL', 'TKYO', 'ACL', 'LWL', 'GLAS', 'TJL'];
    const capMap = ['JKH', 'HAYL', 'SPEN', 'AEL', 'RICH', 'HEMS'];
    const nrgMap = ['LIOC', 'LAUG', 'LGL', 'WIND'];
    const hltMap = ['ASIR', 'NHL', 'CHL', 'AMSL'];

    const getSector = (sym) => {
      if (financeMap.some(f => sym.startsWith(f))) return 'Finance';
      if (mfgMap.some(m => sym.startsWith(m))) return 'Manufacturing';
      if (capMap.some(c => sym.startsWith(c))) return 'Capital Goods';
      if (nrgMap.some(e => sym.startsWith(e))) return 'Energy';
      if (hltMap.some(h => sym.startsWith(h))) return 'Healthcare';
      return 'Other';
    };
    
    const enrichedHoldings = holdings.map(h => {
       const market = marketData[h.symbol] || { price: h.avg_buy_price, change_pct: 0, name: h.symbol };
       const currentPrice = market.price || h.avg_buy_price;
       const val = currentPrice * h.quantity;
       const cost = h.avg_buy_price * h.quantity;
       
       totalValue += val;
       totalCost += cost;
       
       const sector = getSector(h.symbol);
       sectors[sector] += val;
       
       return {
          ...h,
          currentPrice,
          marketChange: market.change_pct || 0,
          name: market.name || h.symbol,
          currentValue: val,
          pnl: val - cost,
          pnlPct: cost > 0 ? ((val - cost) / cost) * 100 : 0
       };
    });
    
    const totalPnl = totalValue - totalCost;
    const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
    
    enrichedHoldings.sort((a,b) => b.currentValue - a.currentValue);
    
    const sectorAllocations = [];
    Object.keys(sectors).forEach(sec => {
       if (sectors[sec] > 0) {
          sectorAllocations.push({
             name: sec,
             val: sectors[sec],
             pct: (sectors[sec] / totalValue) * 100
          });
       }
    });
    sectorAllocations.sort((a,b) => b.pct - a.pct);
    
    return {
       totalValue,
       totalPnl,
       totalPnlPct,
       enrichedHoldings,
       sectorAllocations
    };
  }, [holdings, marketData]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />
      
      {/* Header (Same as Dashboard) */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.avatarContainer}>
            <Image
              source={{ uri: clerkUser?.imageUrl || "https://ui-avatars.com/api/?name=User&background=random" }}
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
          <TouchableTick style={styles.depositBtn} onPress={() => setAddModalVisible(true)}>
            <MaterialIcons name="add" size={18} color={colors.onPrimary} />
            <Text style={styles.depositBtnText}>Add Asset</Text>
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
          
          <Text style={styles.portfolioValue}>{stats.totalValue.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</Text>
          
          <View style={styles.plRow}>
            <View style={[styles.plBadge, { backgroundColor: stats.totalPnl >= 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)' }]}>
              <MaterialIcons name={stats.totalPnl >= 0 ? "trending-up" : "trending-down"} size={16} color={stats.totalPnl >= 0 ? colors.success : colors.error} />
              <Text style={[styles.plBadgeText, { color: stats.totalPnl >= 0 ? colors.success : colors.error }]}>
                {stats.totalPnl >= 0 ? '+' : ''}{stats.totalPnlPct.toFixed(2)}%
              </Text>
            </View>
            <Text style={styles.plText}>
              All time P&L: {stats.totalPnl >= 0 ? '+' : ''}LKR {stats.totalPnl.toFixed(2)}
            </Text>
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
            {stats.enrichedHoldings.length > 3 && (
              <TouchableTick style={styles.seeAllBtn}>
                <Text style={styles.seeAllText}>See all</Text>
                <MaterialIcons name="chevron-right" size={18} color={colors.onSurfaceVariant} />
              </TouchableTick>
            )}
          </View>

          <View style={styles.holdingsList}>
            {loading ? (
               <ActivityIndicator size="small" color={colors.primary} />
            ) : stats.enrichedHoldings.length === 0 ? (
               <Text style={{color: colors.onSurfaceVariant, textAlign: 'center'}}>No holdings in your portfolio.</Text>
            ) : stats.enrichedHoldings.slice(0, 3).map((item, idx) => (
              <TouchableTick key={idx} style={styles.holdingItem}>
                <View style={styles.holdingItemLeft}>
                  <View style={[styles.holdingIconBox, { backgroundColor: item.marketChange >= 0 ? '#E8F5E9' : '#FCE4EC' }]}>
                    <Text style={[styles.holdingIconText, { color: item.marketChange >= 0 ? '#2E7D32' : '#C2185B' }]}>
                      {item.symbol.charAt(0)}
                    </Text>
                  </View>
                  <View>
                    <Text style={styles.holdingName}>{item.symbol}</Text>
                    <Text style={styles.holdingShares}>{item.quantity} Shares</Text>
                  </View>
                </View>
                <View style={styles.holdingItemRight}>
                  <Text style={styles.holdingPrice}>LKR {item.currentPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</Text>
                  <View style={styles.holdingChangeRow}>
                    <MaterialIcons name={item.pnlPct >= 0 ? "arrow-drop-up" : "arrow-drop-down"} size={18} color={item.pnlPct >= 0 ? colors.success : colors.error} />
                    <Text style={[styles.holdingChangeText, { color: item.pnlPct >= 0 ? colors.success : colors.error }]}>
                      {item.pnlPct > 0 ? '+' : ''}{item.pnlPct.toFixed(1)}%
                    </Text>
                  </View>
                </View>
              </TouchableTick>
            ))}
          </View>
        </View>

        {/* Sector Allocation Card */}
        {stats.sectorAllocations.length > 0 && (
          <View style={[styles.card, { marginBottom: 30 }]}>
            <Text style={styles.sectionTitle}>Sector Allocation</Text>
            
            <View style={styles.donutContainer}>
              <View style={[styles.donutRing, { borderTopColor: '#1c3d5a', borderRightColor: '#dae3f5', borderBottomColor: '#89a8ca', borderLeftColor: '#e1e2e4' }]}>
                 <View style={styles.donutInner}>
                    <Text style={styles.donutCenterLabel}>{stats.sectorAllocations[0].name}</Text>
                    <Text style={styles.donutCenterValue}>{stats.sectorAllocations[0].pct.toFixed(0)}%</Text>
                 </View>
              </View>
            </View>

            <View style={styles.legendContainer}>
              {stats.sectorAllocations.map((sec, idx) => (
                <View key={idx} style={styles.legendRow}>
                  <View style={styles.legendLeft}>
                    <View style={[styles.legendDot, { backgroundColor: ['#1c3d5a', '#dae3f5', '#89a8ca', '#e1e2e4', '#F5A623', '#ba1a1a'][idx % 6] }]} />
                    <Text style={styles.legendText}>{sec.name}</Text>
                  </View>
                  <Text style={styles.legendValue}>{sec.pct.toFixed(0)}%</Text>
                </View>
              ))}
            </View>
          </View>
        )}

      </ScrollView>

      <Modal visible={isAddModalVisible} animationType="slide" transparent={true}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: colors.surface }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add Holding</Text>
              <TouchableTick onPress={() => setAddModalVisible(false)}>
                <MaterialIcons name="close" size={24} color={colors.onSurfaceVariant} />
              </TouchableTick>
            </View>
            
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Symbol (e.g. JKH)</Text>
              <TextInput
                style={styles.textInput}
                value={addSymbol}
                onChangeText={setAddSymbol}
                placeholder="Enter stock symbol"
                autoCapitalize="characters"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Quantity</Text>
              <TextInput
                style={styles.textInput}
                value={addQuantity}
                onChangeText={setAddQuantity}
                placeholder="Number of shares"
                keyboardType="numeric"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Average Buy Price (LKR)</Text>
              <TextInput
                style={styles.textInput}
                value={addPrice}
                onChangeText={setAddPrice}
                placeholder="e.g. 150.00"
                keyboardType="numeric"
              />
            </View>

            <TouchableTick 
              style={[styles.saveBtn, { opacity: isSubmitting ? 0.7 : 1 }]} 
              onPress={handleAddSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.saveBtnText}>Save Holding</Text>
              )}
            </TouchableTick>
          </View>
        </View>
      </Modal>
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
    gap: 4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 20,
    fontFamily: 'Satoshi-Bold',
    color: colors.onSurface,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
    marginBottom: 8,
  },
  textInput: {
    borderWidth: 1,
    borderColor: colors.outlineVariant,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    backgroundColor: colors.surfaceLowest,
  },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
  },
  saveBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontFamily: 'Satoshi-Bold',
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
