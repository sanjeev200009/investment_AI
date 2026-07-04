import TouchableTick from '../components/TouchableTick';
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar, TextInput, ActivityIndicator, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useAuth } from '@clerk/clerk-expo';
import axios from 'axios';

const colors = {
  background: '#faf9fc',
  surface: '#faf9fc',
  surfaceLowest: '#ffffff',
  surfaceLow: '#f4f3f6',
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
  success: '#2E7D32',
  successBg: '#E8F5E9',
  successDot: '#4CAF50',
  cardShadow: 'rgba(28, 61, 90, 0.06)'
};

export default function StockBrowseScreen({ navigation }) {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeChip, setActiveChip] = useState('All Sectors');
  const [sortModalVisible, setSortModalVisible] = useState(false);
  const [sortOption, setSortOption] = useState('none');
  const { getToken } = useAuth();

  useEffect(() => {
    async function fetchStocks() {
      try {
        const token = await getToken();
        const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
        const res = await axios.get(`${baseUrl}/stocks/market?limit=100`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setStocks(res.data);
      } catch (e) {
        console.error("Stocks fetch error", e);
        // Fallback mock data if API fails
        setStocks([
          { symbol: 'SAMP.N0000', name: 'Sampath Bank PLC', price: 78.50, change_pct: 1.2 },
          { symbol: 'JKH.N0000', name: 'John Keells Holdings', price: 195.25, change_pct: -0.5 },
          { symbol: 'EXPO.N0000', name: 'Expolanka Holdings', price: 145.00, change_pct: 2.1 }
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetchStocks();
  }, []);

  const filteredStocks = React.useMemo(() => {
    let result = [...stocks];
    
    if (activeChip !== 'All Sectors') {
      if (activeChip === 'Finance') {
        const finance = ['SAMP', 'HNB', 'COMB', 'SEYB', 'NDB', 'NTB', 'PABC', 'DFCC'];
        result = result.filter(s => finance.some(f => s.symbol.startsWith(f)));
      } else if (activeChip === 'Manufacturing') {
        const mfg = ['EXPO', 'RCL', 'TKYO', 'ACL', 'LWL', 'GLAS', 'TJL'];
        result = result.filter(s => mfg.some(m => s.symbol.startsWith(m)));
      } else if (activeChip === 'Capital Goods') {
        const capital = ['JKH', 'HAYL', 'SPEN', 'AEL', 'RICH', 'HEMS'];
        result = result.filter(s => capital.some(c => s.symbol.startsWith(c)));
      } else if (activeChip === 'Energy') {
        const energy = ['LIOC', 'LAUG', 'LGL', 'WIND'];
        result = result.filter(s => energy.some(e => s.symbol.startsWith(e)));
      } else if (activeChip === 'Healthcare') {
        const health = ['ASIR', 'NHL', 'CHL', 'AMSL'];
        result = result.filter(s => health.some(h => s.symbol.startsWith(h)));
      }
    }

    if (searchQuery.trim().length > 0) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s => 
        s.symbol.toLowerCase().includes(q) || 
        (s.name && s.name.toLowerCase().includes(q))
      );
    }
    
    if (sortOption === 'gainers') {
      result.sort((a, b) => b.change_pct - a.change_pct);
    } else if (sortOption === 'losers') {
      result.sort((a, b) => a.change_pct - b.change_pct);
    } else if (sortOption === 'priceHigh') {
      result.sort((a, b) => b.price - a.price);
    } else if (sortOption === 'priceLow') {
      result.sort((a, b) => a.price - b.price);
    }
    
    return result;
  }, [stocks, searchQuery, activeChip, sortOption]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />
      
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.avatarContainer}>
            <Image
              source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBL5Xyg-nefmh91aQuWkk4k2Mtq-LNGJL3UktDsdY_yZymiUOSBH7aqNXm2C45zGuu_XL7exKqgVs33X3q-X0xNB_wuziAmcmrw-p_h34XPhtW-ZcUsfXpm_ZqAtfCA10DNDi0U7QVOvin5SZDnJafeB-t551h06qdYRAxZ2Rt7ajrdw8UK2ZVcUMB40J7-AtZLiD6_PmB-krEnfApjAynpFPeYitlpjBspZUth9Us8hwNWQL4LfA9N4H7Cjt5EpSHe4nR1zrsuxuI' }}
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
        
        {/* Market Discovery Header */}
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Market Discovery</Text>
          <View style={styles.marketOpenBadge}>
            <View style={styles.marketOpenDot} />
            <Text style={styles.marketOpenText}>Market Open</Text>
          </View>
        </View>

        {/* Search Bar */}
        <View style={styles.searchRow}>
          <View style={styles.searchContainer}>
            <MaterialIcons name="search" size={20} color={colors.onSurfaceVariant} style={styles.searchIcon} />
            <TextInput
              style={styles.searchInput}
              placeholder="Search stocks, ETFs, or sectors..."
              placeholderTextColor={colors.onSurfaceVariant}
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
          </View>
          <TouchableTick style={styles.tuneBtn} onPress={() => setSortModalVisible(true)}>
            <MaterialIcons name="tune" size={24} color={colors.onSurface} />
          </TouchableTick>
        </View>

        {/* Chips */}
        <ScrollView style={{ marginTop: 36 }} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsScroll}>
          {['All Sectors', 'Finance', 'Manufacturing', 'Capital Goods', 'Energy', 'Healthcare'].map(chip => (
            <TouchableTick 
              key={chip}
              style={[styles.chip, activeChip === chip ? styles.chipActive : styles.chipInactive]}
              onPress={() => setActiveChip(chip)}
            >
              <Text style={[styles.chipText, activeChip === chip ? styles.chipTextActive : styles.chipTextInactive]}>
                {chip}
              </Text>
            </TouchableTick>
          ))}
        </ScrollView>

        {/* AI Insight Card */}
        <View style={styles.aiCard}>
          <View style={styles.aiCardBlur} />
          <View style={styles.aiCardHeader}>
            <MaterialIcons name="psychology" size={24} color={colors.onPrimary} />
            <Text style={styles.aiCardTitle}>AI Insight</Text>
          </View>
          <Text style={styles.aiCardBody}>
            Semiconductor sector showing unusually high institutional accumulation. Consider reviewing positions in NVDA and TSM.
          </Text>
          <TouchableTick style={styles.aiCardBtn}>
            <Text style={styles.aiCardBtnText}>View Analysis</Text>
          </TouchableTick>
        </View>

        {/* Top Movers */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Top Movers</Text>
          <TouchableTick onPress={() => navigation.navigate('AllTopMovers')}>
            <Text style={styles.seeAllText}>See All</Text>
          </TouchableTick>
        </View>

        <View style={styles.listContainer}>
          {loading ? (
            <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 40 }} />
          ) : filteredStocks.length === 0 ? (
            <Text style={{ textAlign: 'center', marginTop: 20, color: colors.onSurfaceVariant }}>No stocks found.</Text>
          ) : filteredStocks.slice(0, 10).map((stock, idx) => (
            <TouchableTick 
              key={idx}
              style={styles.listItem}
              onPress={() => navigation.navigate('StockDetail', { stock: { symbol: stock.symbol, name: stock.name || stock.symbol, price: stock.price, change: `${stock.change_pct}%`, isPositive: stock.change_pct >= 0 }})}
            >
              <View style={styles.listItemLeft}>
                <View style={[styles.itemAvatar, { backgroundColor: stock.change_pct >= 0 ? '#E8F5E9' : '#FCE4EC' }]}>
                  <Text style={[styles.itemAvatarText, { color: stock.change_pct >= 0 ? '#2E7D32' : '#C2185B' }]}>
                    {stock.symbol.charAt(0)}
                  </Text>
                </View>
                <View>
                  <Text style={styles.itemSymbol}>{stock.symbol.split('.')[0]}</Text>
                  <Text style={styles.itemName}>{stock.name || stock.symbol}</Text>
                </View>
              </View>
              <View style={styles.listItemRight}>
                <Text style={styles.itemPrice}>Rs. {stock.price?.toFixed(2)}</Text>
                <View style={styles.itemChangeRow}>
                  <MaterialIcons name={stock.change_pct >= 0 ? "trending-up" : "trending-down"} size={16} color={stock.change_pct >= 0 ? colors.success : "#C62828"} />
                  <Text style={[styles.itemChangeText, { color: stock.change_pct >= 0 ? colors.success : "#C62828" }]}>
                    {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct}%
                  </Text>
                </View>
              </View>
            </TouchableTick>
          ))}
        </View>

      </ScrollView>

      {/* Sort Modal */}
      <Modal visible={sortModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Sort By</Text>
            
            <TouchableTick style={styles.sortOption} onPress={() => { setSortOption('none'); setSortModalVisible(false); }}>
              <Text style={[styles.sortOptionText, sortOption === 'none' && styles.sortOptionTextActive]}>Default (None)</Text>
              {sortOption === 'none' && <MaterialIcons name="check" size={20} color={colors.primary} />}
            </TouchableTick>
            
            <TouchableTick style={styles.sortOption} onPress={() => { setSortOption('gainers'); setSortModalVisible(false); }}>
              <Text style={[styles.sortOptionText, sortOption === 'gainers' && styles.sortOptionTextActive]}>Top Gainers</Text>
              {sortOption === 'gainers' && <MaterialIcons name="check" size={20} color={colors.primary} />}
            </TouchableTick>
            
            <TouchableTick style={styles.sortOption} onPress={() => { setSortOption('losers'); setSortModalVisible(false); }}>
              <Text style={[styles.sortOptionText, sortOption === 'losers' && styles.sortOptionTextActive]}>Top Losers</Text>
              {sortOption === 'losers' && <MaterialIcons name="check" size={20} color={colors.primary} />}
            </TouchableTick>
            
            <TouchableTick style={styles.sortOption} onPress={() => { setSortOption('priceHigh'); setSortModalVisible(false); }}>
              <Text style={[styles.sortOptionText, sortOption === 'priceHigh' && styles.sortOptionTextActive]}>Price (High to Low)</Text>
              {sortOption === 'priceHigh' && <MaterialIcons name="check" size={20} color={colors.primary} />}
            </TouchableTick>
            
            <TouchableTick style={styles.sortOption} onPress={() => { setSortOption('priceLow'); setSortModalVisible(false); }}>
              <Text style={[styles.sortOptionText, sortOption === 'priceLow' && styles.sortOptionTextActive]}>Price (Low to High)</Text>
              {sortOption === 'priceLow' && <MaterialIcons name="check" size={20} color={colors.primary} />}
            </TouchableTick>

            <TouchableTick style={styles.modalCloseBtn} onPress={() => setSortModalVisible(false)}>
              <Text style={styles.modalCloseBtnText}>Close</Text>
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
    alignItems: 'center',
    marginBottom: 16,
  },
  pageTitle: {
    fontSize: 20,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurface,
  },
  marketOpenBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.successBg,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 16,
    gap: 6,
  },
  marketOpenDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.successDot,
  },
  marketOpenText: {
    fontSize: 12,
    fontFamily: 'Satoshi-Bold',
    color: colors.success,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 20,
  },
  searchContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceLowest,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(195, 199, 206, 0.3)',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 10,
    elevation: 10,
    paddingHorizontal: 16,
    height: 48,
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurface,
  },
  tuneBtn: {
    width: 48,
    height: 48,
    backgroundColor: colors.surfaceLowest,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(195, 199, 206, 0.3)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 10,
    elevation: 10,
  },
  chipsScroll: {
    gap: 12,
    marginBottom: 24,
  },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  chipActive: {
    backgroundColor: colors.primaryContainer,
  },
  chipInactive: {
    backgroundColor: 'rgba(28, 61, 90, 0.1)',
  },
  chipText: {
    fontSize: 14,
  },
  chipTextActive: {
    fontFamily: 'Satoshi-Medium',
    color: colors.onPrimary,
  },
  chipTextInactive: {
    fontFamily: 'Satoshi-Medium',
    color: colors.primary,
  },
  aiCard: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    padding: 20,
    position: 'relative',
    overflow: 'hidden',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
    elevation: 10,
    marginBottom: 24,
  },
  aiCardBlur: {
    position: 'absolute',
    top: -40,
    right: -40,
    width: 128,
    height: 128,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 64,
  },
  aiCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  aiCardTitle: {
    fontSize: 20,
    fontFamily: 'Satoshi-Bold',
    color: colors.onPrimary,
  },
  aiCardBody: {
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: colors.onPrimaryContainer,
    marginBottom: 16,
    lineHeight: 24,
  },
  aiCardBtn: {
    alignSelf: 'flex-start',
    backgroundColor: colors.onPrimary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  aiCardBtnText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
  },
  seeAllText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  listContainer: {
    gap: 12,
  },
  listItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.surfaceLowest,
    padding: 16,
    borderRadius: 12,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 10,
    elevation: 10,
  },
  listItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  itemAvatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemAvatarText: {
    fontSize: 20,
    fontFamily: 'Satoshi-Bold',
  },
  itemSymbol: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    color: colors.onSurface,
  },
  itemName: {
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
    marginTop: 2,
  },
  listItemRight: {
    alignItems: 'flex-end',
  },
  itemPrice: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    color: colors.onSurface,
  },
  itemChangeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  itemChangeText: {
    fontSize: 14,
    fontWeight: '700',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.onSurface,
    marginBottom: 16,
  },
  sortOption: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surfaceHigh,
  },
  sortOptionText: {
    fontSize: 16,
    color: colors.onSurfaceVariant,
  },
  sortOptionTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  modalCloseBtn: {
    marginTop: 24,
    backgroundColor: colors.surfaceVariant,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  modalCloseBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.onSurface,
  },
});
