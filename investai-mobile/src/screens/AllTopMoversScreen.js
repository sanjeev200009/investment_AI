// src/screens/AllTopMoversScreen.js
//
// Every listed stock sorted by the day's change, v2 "Soft pastel": circle back
// header and Home-style market rows on one white glass surface.
import React, { useState, useEffect } from 'react';
import { View, FlatList, StyleSheet } from 'react-native';
import { Screen, Header, EmptyState, Loading } from '../components/ui';
import { MarketRow, detailParams } from './StockBrowseScreen';
import api from '../api/axiosConfig';
import { useT } from '../store/languageStore';
import { palette, radii } from '../theme/tokens';
import { Rise, SkeletonRows } from '../components/Motion';

export default function AllTopMoversScreen({ navigation }) {
  const { t } = useT();
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchStocks() {
      try {
        // 400 rather than 200: the market has 291 symbols, so a 200-row page was
        // dropping roughly a third of the exchange from a screen titled "All".
        const res = await api.get('/stocks/market', { params: { limit: 400 } });

        // change_pct is null for a symbol with no previous close; sorted to the
        // end explicitly instead of being coerced to 0.
        const sorted = [...res.data].sort((a, b) => {
          const x = a.change_pct, y = b.change_pct;
          if (!Number.isFinite(x)) return Number.isFinite(y) ? 1 : 0;
          if (!Number.isFinite(y)) return -1;
          return y - x;
        });
        if (!cancelled) setStocks(sorted);
      } catch (e) {
        // Shown as an error, never as an empty market.
        if (!cancelled) {
          setStocks([]);
          setError(e.response?.data?.detail || e.message
            || 'NETWORK_ERROR');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchStocks();
    return () => { cancelled = true; };
  }, []);

  const last = stocks.length - 1;

  return (
    <Screen scroll={false} contentStyle={{ paddingBottom: 0 }}>
      <Header title={t('movers_title')} onBack={() => navigation.goBack()} backLabel={t('movers_back')} />

      {loading ? (
        <SkeletonRows count={8} label={t('loading')} />
      ) : error !== null ? (
        <EmptyState icon="cloud-off" tone="coral" message={error === 'NETWORK_ERROR' ? t('movers_network_error') : error} />
      ) : (
        <FlatList
          data={stocks}
          keyExtractor={(item) => item.symbol}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: 120 }}
          ListEmptyComponent={<EmptyState icon="show-chart" message={t('movers_empty')} />}
          // One glass surface built from its rows: the first and last round the
          // corners, and each row below the first carries the hairline divider.
          renderItem={({ item: stock, index }) => (
            <Rise index={index} style={[styles.cell, index === 0 && styles.cellFirst, index === last && styles.cellLast]}>
              {index > 0 && <View style={styles.divider} />}
              <MarketRow
                stock={stock}
                subtitle={stock.name || stock.symbol}
                noPriorLabel={t('movers_no_prior_close')}
                a11yLabel={t('home_open_symbol').replace('{symbol}', stock.symbol)}
                onPress={() => navigation.navigate('StockDetail', detailParams(stock))}
              />
            </Rise>
          )}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  cell: { backgroundColor: 'rgba(255,255,255,0.88)', paddingHorizontal: 8 },
  cellFirst: { borderTopLeftRadius: radii.xl, borderTopRightRadius: radii.xl, paddingTop: 8 },
  cellLast: { borderBottomLeftRadius: radii.xl, borderBottomRightRadius: radii.xl, paddingBottom: 8 },
  divider: { height: 1, backgroundColor: palette.hairline, marginHorizontal: 12 },
});
