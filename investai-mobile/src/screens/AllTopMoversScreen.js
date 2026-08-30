import TouchableTick from '../components/TouchableTick';
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import api from '../api/axiosConfig';

const colors = {
  background: '#faf9fc',
  surface: '#faf9fc',
  onSurface: '#1a1c1e',
  onSurfaceVariant: '#43474d',
  primary: '#002743',
  success: '#2E7D32',
  error: '#ba1a1a',
  border: '#e3e2e5'
};

export default function AllTopMoversScreen({ navigation }) {
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

        // change_pct is null for a symbol with no previous close. `b - a` coerces
        // null to 0, so those rows sorted in among the flat stocks and rendered as
        // "+null%" with an upward arrow. Sorted to the end explicitly instead.
        const sorted = [...res.data].sort((a, b) => {
          const x = a.change_pct, y = b.change_pct;
          if (!Number.isFinite(x)) return Number.isFinite(y) ? 1 : 0;
          if (!Number.isFinite(y)) return -1;
          return y - x;
        });
        if (!cancelled) setStocks(sorted);
      } catch (e) {
        // Was console.error only, which left the screen showing an empty FlatList
        // with no explanation — indistinguishable from a market with no movers.
        if (!cancelled) {
          setStocks([]);
          setError(e.response?.data?.detail || e.message
            || 'Could not reach the market data service');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchStocks();
    return () => { cancelled = true; };
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />

      {/* Header */}
      <View style={styles.header}>
        <TouchableTick onPress={() => navigation.goBack()} style={styles.backBtn}>
          <MaterialIcons name="arrow-back" size={24} color={colors.onSurface} />
        </TouchableTick>
        <Text style={styles.headerTitle}>All Top Movers</Text>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 40 }} />
      ) : error !== null ? (
        <View style={styles.errorBox}>
          <MaterialIcons name="cloud-off" size={24} color={colors.onSurfaceVariant} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : (
        <FlatList
          data={stocks}
          keyExtractor={(item) => item.symbol}
          contentContainerStyle={{ padding: 16 }}
          ListEmptyComponent={
            <Text style={styles.errorText}>No market data recorded yet.</Text>
          }
          renderItem={({ item: stock }) => {
            const pct = Number.isFinite(stock.change_pct) ? stock.change_pct : null;
            const up = pct !== null && pct >= 0;
            return (
              <TouchableTick
                style={styles.listItem}
                onPress={() => navigation.navigate('StockDetail', { stock: { symbol: stock.symbol, name: stock.name || stock.symbol, price: stock.price, change: pct === null ? '—' : `${pct.toFixed(2)}%`, isPositive: up }})}
              >
                <View style={styles.listItemLeft}>
                  <View style={[styles.itemAvatar, { backgroundColor: pct === null ? colors.border : up ? '#E8F5E9' : '#FCE4EC' }]}>
                    <Text style={[styles.itemAvatarText, { color: pct === null ? colors.onSurfaceVariant : up ? '#2E7D32' : '#C2185B' }]}>
                      {stock.symbol.charAt(0)}
                    </Text>
                  </View>
                  <View style={styles.itemTextBlock}>
                    <Text style={styles.itemSymbol}>{stock.symbol.split('.')[0]}</Text>
                    <Text style={styles.itemName} numberOfLines={1}>{stock.name || stock.symbol}</Text>
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
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    height: 56,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: {
    padding: 12,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.onSurface,
    marginLeft: 8,
  },
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  listItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  itemAvatar: {
    width: 40,
    height: 40,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemAvatarText: {
    fontSize: 16,
    fontWeight: '700',
  },
  itemTextBlock: {
    flex: 1,
  },
  itemSymbol: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.onSurface,
  },
  itemName: {
    fontSize: 13,
    color: colors.onSurfaceVariant,
    marginTop: 2,
  },
  listItemRight: {
    alignItems: 'flex-end',
  },
  itemPrice: {
    fontSize: 16,
    fontWeight: '600',
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
  itemNoChange: {
    fontSize: 11,
    color: colors.onSurfaceVariant,
    marginTop: 4,
  },
  errorBox: {
    alignItems: 'center',
    gap: 8,
    marginTop: 48,
    paddingHorizontal: 32,
  },
  errorText: {
    fontSize: 13,
    color: colors.onSurfaceVariant,
    textAlign: 'center',
    lineHeight: 20,
  }
});
