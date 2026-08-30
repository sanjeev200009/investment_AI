import TouchableTick from '../components/TouchableTick';
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar, TextInput, ActivityIndicator, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import api from '../api/axiosConfig';

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

const ALL_SECTORS = 'All Sectors';

// How many rows this screen renders. The server sends the whole sector (up to 400
// rows) so search and sort see every company, but 291 shadowed cards in a ScrollView
// is a scroll the user cannot get to the bottom of. The heading states the cut
// explicitly — "20 of 291" — because a silently truncated list is the same defect as
// the old sector chips: complete-looking and not complete.
const VISIBLE = 20;

// The market's own trading window, in Colombo time. Used only to word the
// data-freshness line, never to assert the market is open — the badge that used to
// sit in the header read "Market Open" from a hardcoded style with no data behind
// it, so it said the market was open at 3am on a Sunday.
const shortTime = (iso) => {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime())
    ? null
    : parsed.toLocaleString('en-GB', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
      });
};

export default function StockBrowseScreen({ navigation }) {
  const user = useAuthStore(state => state.user);
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeChip, setActiveChip] = useState(ALL_SECTORS);
  const [sortModalVisible, setSortModalVisible] = useState(false);
  const [sortOption, setSortOption] = useState('none');

  // The real sector list from GET /stocks/sectors: the CSE's own 20 industry-group
  // index names with a live count of companies in each. This replaces six chips
  // whose membership was decided by ticker-prefix arrays hardcoded in this file —
  // `['JKH', 'HAYL', 'SPEN', 'AEL', 'RICH', 'HEMS']` was "Capital Goods", so the
  // chip found 6 of that sector's 29 companies, and "Finance", "Manufacturing" and
  // "Healthcare" were not CSE sector names at all.
  const [sectors, setSectors] = useState([]);

  useEffect(() => {
    let cancelled = false;
    api.get('/stocks/sectors')
      .then(({ data }) => { if (!cancelled) setSectors(data); })
      // A failure here costs the sector chips, not the stock list. Leaving the
      // array empty renders just "All Sectors", which is a working screen.
      .catch(() => { if (!cancelled) setSectors([]); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    // Refetches when the sector changes, because the filter belongs on the server.
    // The old screen filtered a fixed first page of 100 rows client-side against
    // 291 symbols, so a sector's members outside that page were unreachable no
    // matter which chip was tapped.
    let cancelled = false;
    setLoading(true);
    setError(null);

    const params = { limit: 400 };
    if (activeChip !== ALL_SECTORS) params.sector = activeChip;

    api.get('/stocks/market', { params })
      .then(({ data }) => { if (!cancelled) setStocks(data); })
      .catch(err => {
        if (cancelled) return;
        // No mock fallback. This used to substitute three hardcoded stocks with
        // invented prices — Sampath at 78.50, JKH at 195.25, Expolanka at 145.00 —
        // so a backend that was down looked like a market with three companies in
        // it, and the prices shown were whatever they had been when the array was
        // typed. An error message is less useful and far more honest.
        setStocks([]);
        setError(err.response?.data?.detail || err.message
          || 'Could not reach the market data service');
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [activeChip]);

  // The freshest reading in the response, which is what "as of" has to mean: the
  // scraper stamps every row with the session it came from.
  const asOf = React.useMemo(() => {
    const stamps = stocks.map(s => s.recorded_at).filter(Boolean).sort();
    return stamps.length ? shortTime(stamps[stamps.length - 1]) : null;
  }, [stocks]);

  const filteredStocks = React.useMemo(() => {
    // Sector filtering is gone from here — it happens on the server now. What is
    // left is search and sort, both of which act on whatever the server returned.
    let result = [...stocks];

    if (searchQuery.trim().length > 0) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s =>
        s.symbol.toLowerCase().includes(q) ||
        (s.name && s.name.toLowerCase().includes(q))
      );
    }

    // change_pct is null for a symbol with no previous close — a new listing, or the
    // first session after the pipeline started. Sorting on null in JS silently
    // scatters those rows, so they are pushed to the end explicitly.
    const byNumber = (key, desc) => (a, b) => {
      const x = a[key], y = b[key];
      if (!Number.isFinite(x)) return Number.isFinite(y) ? 1 : 0;
      if (!Number.isFinite(y)) return -1;
      return desc ? y - x : x - y;
    };

    if (sortOption === 'gainers') result.sort(byNumber('change_pct', true));
    else if (sortOption === 'losers') result.sort(byNumber('change_pct', false));
    else if (sortOption === 'priceHigh') result.sort(byNumber('price', true));
    else if (sortOption === 'priceLow') result.sort(byNumber('price', false));

    return result;
  }, [stocks, searchQuery, sortOption]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />
      
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.avatarContainer}>
            <Image
              source={{ uri: `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.full_name || 'Investor')}&background=0052FF&color=fff` }}
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
        
        {/* Market Discovery Header. The badge here used to read "Market Open" from
            a hardcoded green pill with nothing behind it — it said the market was
            open at 3am on a Sunday, and there is no market-status endpoint to ask.
            What the data does support is when it was last recorded, which is the
            question the badge was standing in for. */}
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Market Discovery</Text>
          {asOf ? (
            <View style={styles.asOfBadge}>
              <MaterialIcons name="schedule" size={12} color={colors.onSurfaceVariant} />
              <Text style={styles.asOfText}>as of {asOf}</Text>
            </View>
          ) : null}
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

        {/* Sector chips, from GET /stocks/sectors. Each carries its live company
            count, which is the thing that makes the chip honest: "Capital Goods 29"
            is checkable against the list it produces, where the old chip silently
            showed 6 of 29 and looked complete.

            The counts do not sum to 291 and are not meant to. Six symbols have no
            resolvable industry group — three CAL unit trusts that have no sector at
            all, CHRISSWORLD filed under "Industrials" (a GICS sector spanning three
            groups), and TESS AGRO x2 filed under "Trading" (which reads as Capital
            Goods but belongs to a seafood processor). An "Other (6)" chip would
            imply a sector that does not exist, so they appear under All Sectors
            only. */}
        <ScrollView style={{ marginTop: 36 }} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsScroll}>
          {[{ sector: ALL_SECTORS, count: null }, ...sectors].map(({ sector, count }) => (
            <TouchableTick
              key={sector}
              style={[styles.chip, activeChip === sector ? styles.chipActive : styles.chipInactive]}
              onPress={() => setActiveChip(sector)}
            >
              <Text style={[styles.chipText, activeChip === sector ? styles.chipTextActive : styles.chipTextInactive]}>
                {count === null ? sector : `${sector} ${count}`}
              </Text>
            </TouchableTick>
          ))}
        </ScrollView>

        {/* The card that sat here was headed "AI Insight" and its body was one
            hardcoded string: "Semiconductor sector showing unusually high
            institutional accumulation. Consider reviewing positions in NVDA and
            TSM." Three separate problems, and the third is the one that mattered:
            nothing in the app computes institutional accumulation; the CSE has no
            semiconductor sector; and NVDA and TSM are NASDAQ tickers that do not
            trade on the exchange this app covers, so the "View Analysis" button led
            to a position the user could not hold in a sector that does not exist.
            The chat assistant is the app's real AI surface and it answers from the
            stored market data, so there is nothing for a static card to add. */}

        {/* The heading was "Top Movers" over the first 10 rows of an unsorted list,
            which is a claim about the rows rather than a description of them — the
            list is only movers when the sort is set to gainers or losers. It now
            says what it is showing, including how many of how many. */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>
            {activeChip === ALL_SECTORS ? 'All listed companies' : activeChip}
            {filteredStocks.length > 0
              ? ` · ${Math.min(VISIBLE, filteredStocks.length)} of ${filteredStocks.length}`
              : ''}
          </Text>
          {/* Was "See All", which after the heading changed no longer described
              where it goes. The destination is the movers list, so it says so. */}
          <TouchableTick onPress={() => navigation.navigate('AllTopMovers')}>
            <Text style={styles.seeAllText}>Top movers</Text>
          </TouchableTick>
        </View>

        <View style={styles.listContainer}>
          {loading ? (
            <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 40 }} />
          ) : error !== null ? (
            <View style={styles.listEmpty}>
              <MaterialIcons name="cloud-off" size={24} color={colors.onSurfaceVariant} />
              <Text style={styles.listEmptyText}>{error}</Text>
            </View>
          ) : filteredStocks.length === 0 ? (
            <View style={styles.listEmpty}>
              <Text style={styles.listEmptyText}>
                {searchQuery.trim().length > 0
                  ? `Nothing matching "${searchQuery.trim()}"${activeChip === ALL_SECTORS ? '' : ` in ${activeChip}`}.`
                  : 'No stocks found.'}
              </Text>
            </View>
          ) : filteredStocks.slice(0, VISIBLE).map((stock) => {
            // change_pct is null when the symbol has no previous close to compare
            // against. `null >= 0` is true in JS, so the old code painted those rows
            // green with a "+null%" label and an upward arrow — a stock reported as
            // rising by an amount that does not exist.
            const pct = Number.isFinite(stock.change_pct) ? stock.change_pct : null;
            const up = pct !== null && pct >= 0;
            return (
              <TouchableTick
                // Keyed on the symbol, not the array index. Sorting and filtering
                // reorder this list, and an index key makes React reuse a row's
                // state for a different company.
                key={stock.symbol}
                style={styles.listItem}
                onPress={() => navigation.navigate('StockDetail', { stock: { symbol: stock.symbol, name: stock.name || stock.symbol, price: stock.price, change: pct === null ? '—' : `${pct.toFixed(2)}%`, isPositive: up }})}
              >
                <View style={styles.listItemLeft}>
                  <View style={[styles.itemAvatar, { backgroundColor: pct === null ? colors.surfaceHigh : up ? '#E8F5E9' : '#FCE4EC' }]}>
                    <Text style={[styles.itemAvatarText, { color: pct === null ? colors.onSurfaceVariant : up ? '#2E7D32' : '#C2185B' }]}>
                      {stock.symbol.charAt(0)}
                    </Text>
                  </View>
                  <View style={styles.itemTextBlock}>
                    <Text style={styles.itemSymbol}>{stock.symbol.split('.')[0]}</Text>
                    {/* The real company name from company_info, joined into the
                        market response. `stock.name` was already read here and was
                        always undefined, so every row fell back to its own ticker. */}
                    <Text style={styles.itemName} numberOfLines={1}>
                      {stock.name || stock.symbol}
                    </Text>
                    {stock.sector && activeChip === ALL_SECTORS ? (
                      <Text style={styles.itemSector} numberOfLines={1}>{stock.sector}</Text>
                    ) : null}
                  </View>
                </View>
                <View style={styles.listItemRight}>
                  <Text style={styles.itemPrice}>Rs. {stock.price?.toFixed(2)}</Text>
                  {pct === null ? (
                    <Text style={styles.itemNoChange}>no prior close</Text>
                  ) : (
                    <View style={styles.itemChangeRow}>
                      <MaterialIcons name={up ? 'trending-up' : 'trending-down'} size={16} color={up ? colors.success : '#C62828'} />
                      <Text style={[styles.itemChangeText, { color: up ? colors.success : '#C62828' }]}>
                        {up ? '+' : ''}{pct.toFixed(2)}%
                      </Text>
                    </View>
                  )}
                </View>
              </TouchableTick>
            );
          })}
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
  // Replaces marketOpenBadge/marketOpenDot/marketOpenText. Deliberately neutral
  // rather than green-on-green: this states when the data was recorded, which is not
  // good news or bad news, and the old pill's success colouring was half of why it
  // read as "the market is open and all is well".
  asOfBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceLow,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 16,
    gap: 5,
  },
  asOfText: {
    fontSize: 11,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
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
  // aiCard, aiCardBlur, aiCardHeader, aiCardTitle, aiCardBody, aiCardBtn and
  // aiCardBtnText are gone with the card they styled.
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
  // The empty and error states used to be one centred line of text with no
  // container. Both now sit in a card so a failed fetch looks like a deliberate
  // state rather than a list that finished rendering early.
  listEmpty: {
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.surfaceLowest,
    borderRadius: 12,
    paddingVertical: 32,
    paddingHorizontal: 24,
    marginTop: 8,
  },
  listEmptyText: {
    fontSize: 13,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
    textAlign: 'center',
    lineHeight: 20,
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
  // flex: 1 with the avatar's fixed 48px is what lets numberOfLines actually clip.
  // Without it the text block sizes to its content and long company names —
  // "C T HOLDINGS PLC" is short, "LANKA VENTURES PLC" is not the worst — push the
  // price off the right edge instead of ellipsising.
  itemTextBlock: {
    flex: 1,
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
  itemSector: {
    fontSize: 11,
    fontFamily: 'Satoshi-Regular',
    color: colors.outlineVariant,
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
  // Shown instead of a percentage when change_pct is null. Grey and lower-case so
  // it does not compete with the real readings around it.
  itemNoChange: {
    fontSize: 11,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurfaceVariant,
    marginTop: 4,
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
