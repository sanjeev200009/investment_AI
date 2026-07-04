import TouchableTick from '../components/TouchableTick';
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useAuth } from '@clerk/clerk-expo';
import axios from 'axios';

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
  const { getToken } = useAuth();

  useEffect(() => {
    async function fetchStocks() {
      try {
        const token = await getToken();
        const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
        const res = await axios.get(`${baseUrl}/stocks/market?limit=200`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        let sorted = res.data;
        sorted.sort((a, b) => b.change_pct - a.change_pct); // Default sort: gainers
        setStocks(sorted);
      } catch (e) {
        console.error("Top Movers fetch error", e);
      } finally {
        setLoading(false);
      }
    }
    fetchStocks();
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
      ) : (
        <FlatList
          data={stocks}
          keyExtractor={(item) => item.symbol}
          contentContainerStyle={{ padding: 16 }}
          renderItem={({ item: stock }) => (
            <TouchableTick 
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
          )}
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
  }
});
