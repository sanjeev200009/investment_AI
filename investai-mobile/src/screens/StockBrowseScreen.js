// src/screens/StockBrowseScreen.js
//
// Markets, v2 "Soft pastel": title, full-round search, sector and sort chips,
// and the market rows Home uses (round ticker tinted by the day's change).
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import TouchableTick from '../components/TouchableTick';
import {
  Screen, PillButton, Chip, Card, Title, Heading, Label, Field, EmptyState, Loading,
} from '../components/ui';
import { useT } from '../store/languageStore';
import api from '../api/axiosConfig';
import { palette, fonts, radii, changeTone } from '../theme/tokens';

const ALL_SECTORS = 'All Sectors'; // state value; displayed via t('browse_all_sectors')

// How many rows this screen renders. The server sends the whole sector (up to 400
// rows) so search and sort see every company, but hundreds of rows is a scroll the
// user cannot get to the bottom of. The heading states the cut explicitly —
// "20 of 291" — because a silently truncated list looks complete and is not.
const PAGE = 20;

// Sort state values, in display order, with their label keys.
const SORTS = [
  ['none', 'browse_sort_default'],
  ['gainers', 'browse_sort_gainers'],
  ['losers', 'browse_sort_losers'],
  ['priceHigh', 'browse_sort_price_high'],
  ['priceLow', 'browse_sort_price_low'],
];

// Used only to word the data-freshness line, never to assert the market is open:
// there is no market-status endpoint, only when the data was last recorded.
const shortTime = (iso) => {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime())
    ? null
    : parsed.toLocaleString('en-GB', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
      });
};

const fmt = (n) => Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// The StockDetail params every market list sends.
export const detailParams = (stock) => {
  const pct = Number.isFinite(stock.change_pct) ? stock.change_pct : null;
  return {
    stock: {
      symbol: stock.symbol,
      name: stock.name || stock.symbol,
      price: stock.price,
      change: pct === null ? '—' : `${pct.toFixed(2)}%`,
      isPositive: pct !== null && pct >= 0,
    },
  };
};

/** One market row, as on Home. Shared with AllTopMoversScreen. */
export function MarketRow({ stock, onPress, subtitle, noPriorLabel, a11yLabel }) {
  // change_pct is null when the symbol has no previous close; `null >= 0` is true
  // in JS, so it is checked explicitly rather than painted as a gain.
  const pct = Number.isFinite(stock.change_pct) ? stock.change_pct : null;
  const tone = changeTone(pct);
  return (
    <TouchableTick style={styles.row} onPress={onPress} accessibilityLabel={a11yLabel}>
      <View style={[styles.ticker, { backgroundColor: tone.background }]}>
        <Text style={[styles.tickerText, { color: tone.ink }]}>{stock.symbol.split('.')[0].slice(0, 4)}</Text>
      </View>
      <View style={{ flex: 1, gap: 2, minWidth: 0 }}>
        <Text style={styles.rowTitle} numberOfLines={1}>{stock.symbol.split('.')[0]}</Text>
        <Label numberOfLines={1}>{subtitle}</Label>
      </View>
      <View style={{ alignItems: 'flex-end', gap: 2 }}>
        <Text style={styles.rowFigure}>{Number.isFinite(stock.price) ? fmt(stock.price) : '—'}</Text>
        <Text style={[styles.rowChange, { color: tone.ink }]}>
          {pct === null ? noPriorLabel : `${tone.sign}${Math.abs(pct).toFixed(2)}%`}
        </Text>
      </View>
    </TouchableTick>
  );
}

export default function StockBrowseScreen({ navigation }) {
  const { t } = useT();
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  // Rows shown so far; "Show more" adds a page. Reset when the filter changes.
  const [visible, setVisible] = useState(PAGE);
  const [activeChip, setActiveChip] = useState(ALL_SECTORS);
  const [sortOption, setSortOption] = useState('none');

  // The real sector list from GET /stocks/sectors: the CSE's own industry-group
  // index names with a live count of companies in each.
  const [sectors, setSectors] = useState([]);

  useEffect(() => {
    let cancelled = false;
    api.get('/stocks/sectors')
      .then(({ data }) => { if (!cancelled) setSectors(data); })
      // A failure here costs the sector chips, not the stock list.
      .catch(() => { if (!cancelled) setSectors([]); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    // Refetches when the sector changes, because the filter belongs on the server.
    let cancelled = false;
    setLoading(true);
    setError(null);

    const params = { limit: 400 };
    if (activeChip !== ALL_SECTORS) params.sector = activeChip;

    api.get('/stocks/market', { params })
      .then(({ data }) => { if (!cancelled) setStocks(data); })
      .catch(err => {
        if (cancelled) return;
        // No mock fallback: an unreachable backend shows an error, never
        // invented prices.
        setStocks([]);
        setError(err.response?.data?.detail || err.message
          || 'NETWORK_ERROR');
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [activeChip]);

  // The freshest reading in the response, which is what "as of" has to mean.
  const asOf = React.useMemo(() => {
    const stamps = stocks.map(s => s.recorded_at).filter(Boolean).sort();
    return stamps.length ? shortTime(stamps[stamps.length - 1]) : null;
  }, [stocks]);

  const filteredStocks = React.useMemo(() => {
    // Sector filtering happens on the server; search and sort act on its answer.
    let result = [...stocks];

    if (searchQuery.trim().length > 0) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s =>
        s.symbol.toLowerCase().includes(q) ||
        (s.name && s.name.toLowerCase().includes(q))
      );
    }

    // change_pct is null for a symbol with no previous close; those rows are
    // pushed to the end explicitly rather than scattered by a null comparison.
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
    <Screen>
      {/* Title and data freshness. There is no market-status endpoint, so this
          says when the data was recorded rather than whether the market is open. */}
      <View style={{ gap: 10 }}>
        <Title>{t('browse_title')}</Title>
        {asOf ? <Chip icon="schedule" label={t('browse_as_of').replace('{time}', asOf)} /> : null}
      </View>

      {/* Search */}
      <View>
        <Field
          placeholder={t('browse_search_placeholder')}
          value={searchQuery}
          onChangeText={setSearchQuery}
          inputStyle={{ paddingLeft: 52 }}
          returnKeyType="search"
        />
        <MaterialIcons name="search" size={22} color={palette.muted} style={styles.searchIcon} pointerEvents="none" />
      </View>

      {/* Sector chips, from GET /stocks/sectors, each with its live company count.
          Symbols with no resolvable industry group appear under All Sectors only. */}
      <View style={{ gap: 12 }}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {[{ sector: ALL_SECTORS, count: null }, ...sectors].map(({ sector, count }) => (
            <Chip
              key={sector}
              label={count === null ? t('browse_all_sectors') : `${sector} ${count}`}
              selected={activeChip === sector}
              onPress={() => { setActiveChip(sector); setVisible(PAGE); }}
            />
          ))}
        </ScrollView>

        <Label style={{ paddingLeft: 4 }}>{t('browse_sort_by')}</Label>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {SORTS.map(([value, key]) => (
            <Chip
              key={value}
              label={t(key)}
              icon={sortOption === value ? 'check' : undefined}
              selected={sortOption === value}
              onPress={() => setSortOption(value)}
            />
          ))}
        </ScrollView>
      </View>

      {/* The list, headed by what it shows and how many of how many. */}
      <View style={{ gap: 12 }}>
        <View style={styles.rowBetween}>
          <Heading style={{ flex: 1 }} numberOfLines={2}>
            {activeChip === ALL_SECTORS ? t('browse_all_listed') : activeChip}
            {filteredStocks.length > 0 ? (
              <Text style={styles.count}>
                {` · ${t('browse_n_of_total').replace('{n}', Math.min(visible, filteredStocks.length)).replace('{total}', filteredStocks.length)}`}
              </Text>
            ) : null}
          </Heading>
          <TouchableTick
            onPress={() => navigation.navigate('AllTopMovers')}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            accessibilityRole="link"
          >
            <Text style={styles.link}>{t('browse_top_movers')}</Text>
          </TouchableTick>
        </View>

        {loading ? (
          <Loading />
        ) : error !== null ? (
          <EmptyState
            icon="cloud-off"
            tone="coral"
            message={error === 'NETWORK_ERROR' ? t('browse_network_error') : error}
          />
        ) : filteredStocks.length === 0 ? (
          <EmptyState
            icon="search-off"
            message={searchQuery.trim().length > 0
              ? (activeChip === ALL_SECTORS
                ? t('browse_no_match').replace('{query}', searchQuery.trim())
                : t('browse_no_match_in_sector').replace('{query}', searchQuery.trim()).replace('{sector}', activeChip))
              : t('browse_no_stocks')}
          />
        ) : (
          <Card style={{ padding: 8 }}>
            {filteredStocks.slice(0, visible).map((stock, i) => (
              // Keyed on the symbol: sorting and filtering reorder this list.
              <View key={stock.symbol}>
                {i > 0 && <View style={styles.divider} />}
                <MarketRow
                  stock={stock}
                  subtitle={[stock.name || stock.symbol, activeChip === ALL_SECTORS ? stock.sector : null].filter(Boolean).join(' · ')}
                  noPriorLabel={t('browse_no_prior_close')}
                  a11yLabel={t('home_open_symbol').replace('{symbol}', stock.symbol)}
                  onPress={() => navigation.navigate('StockDetail', detailParams(stock))}
                />
              </View>
            ))}
          </Card>
        )}

        {!loading && !error && filteredStocks.length > visible && (
          <PillButton
            variant="secondary"
            icon="expand-more"
            title={t('browse_show_more').replace('{n}', Math.min(PAGE, filteredStocks.length - visible))}
            onPress={() => setVisible(v => v + PAGE)}
          />
        )}
      </View>
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  searchIcon: { position: 'absolute', left: 20, top: 19 },
  chipRow: { gap: 8, paddingRight: 20 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  count: { fontSize: 15, color: palette.muted },
  link: { ...text, fontFamily: fonts.medium, fontSize: 15, textDecorationLine: 'underline' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 12, minHeight: 68 },
  divider: { height: 1, backgroundColor: palette.hairline, marginHorizontal: 12 },
  ticker: { width: 48, height: 48, borderRadius: radii.full, alignItems: 'center', justifyContent: 'center' },
  tickerText: { fontFamily: fonts.bold, fontSize: 11, letterSpacing: 0.3 },
  rowTitle: { ...text, fontFamily: fonts.medium, fontSize: 16 },
  rowFigure: { ...text, fontFamily: fonts.medium, fontSize: 16, fontVariant: ['tabular-nums'] },
  rowChange: { ...text, fontSize: 13, fontVariant: ['tabular-nums'] },
});
