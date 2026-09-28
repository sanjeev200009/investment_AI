// src/screens/WatchlistScreen.js
//
// The user's own watchlist (GET/POST/DELETE /watchlist), v2 "Soft pastel":
// a white card per stock with a yellow ticker and star, big light price and
// change pill, and a black "Add symbol" action opening a white sheet.
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, Modal, Alert } from 'react-native';
import {
  Screen, Header, CircleButton, PillButton, Chip, Card, BigNumber, ChangePill,
  Title, Heading, Label, Field, EmptyState, Loading,
} from '../components/ui';
import { watchlistApi } from '../api/api';
import { useT } from '../store/languageStore';
import { palette, fonts, radii } from '../theme/tokens';

export default function WatchlistScreen({ navigation }) {
  const { t } = useT();
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [symbolInput, setSymbolInput] = useState('');
  const [adding, setAdding] = useState(false);

  const fetchWatchlist = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const data = await watchlistApi.list();
      setWatchlist(Array.isArray(data) ? data : []);
      setLoadError(null);
    } catch (err) {
      setLoadError(err?.response?.data?.detail || err?.message || 'LOAD_ERROR');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchWatchlist(); }, [fetchWatchlist]);

  const handleAdd = async () => {
    const symbol = symbolInput.trim().toUpperCase();
    if (!symbol) return;
    setAdding(true);
    try {
      await watchlistApi.add(symbol);
      setSymbolInput('');
      setAddModalVisible(false);
      fetchWatchlist();
    } catch (err) {
      Alert.alert(
        t('watchlist_add_failed_title'),
        err?.response?.status === 404
          ? t('watchlist_not_listed').replace('{symbol}', symbol)
          : err?.response?.data?.detail || t('watchlist_try_again'));
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (symbol) => {
    const snapshot = watchlist;
    setWatchlist(watchlist.filter(w => w.symbol !== symbol));
    try {
      await watchlistApi.remove(symbol);
    } catch (err) {
      console.warn('[Watchlist] remove failed:', err?.message || err);
      setWatchlist(snapshot);
    }
  };

  return (
    <Screen refreshing={refreshing} onRefresh={() => fetchWatchlist(true)}>
      {navigation.canGoBack() ? (
        <Header onBack={() => navigation.goBack()} backLabel={t('movers_back')} />
      ) : null}

      <View style={{ gap: 6 }}>
        <Title>{t('watchlist_title')}</Title>
        <Label>{t('watchlist_subtitle')}</Label>
      </View>

      {loading ? (
        <Loading />
      ) : loadError ? (
        <EmptyState icon="cloud-off" tone="coral" message={loadError === 'LOAD_ERROR' ? t('watchlist_load_error') : loadError} />
      ) : watchlist.length === 0 ? (
        <EmptyState icon="star-border" tone="yellow" message={t('watchlist_empty')} />
      ) : (
        <View style={{ gap: 14 }}>
          {watchlist.map((stock) => {
            const pct = Number.isFinite(stock.change_pct) ? stock.change_pct : null;
            const isPositive = pct !== null && pct >= 0;
            return (
              <Card
                key={stock.symbol}
                style={{ gap: 16 }}
                label={stock.name || stock.symbol}
                onPress={() => navigation.navigate('StockDetail', { stock: {
                  symbol: stock.symbol,
                  name: stock.name || stock.symbol,
                  price: stock.price,
                  change: pct === null ? '—' : `${pct.toFixed(2)}%`,
                  isPositive,
                } })}
              >
                <View style={styles.cardTop}>
                  <View style={styles.ticker}>
                    <Text style={styles.tickerText}>{stock.symbol.split('.')[0].slice(0, 4)}</Text>
                  </View>
                  <View style={{ flex: 1, gap: 2, minWidth: 0 }}>
                    <Text style={styles.companyName} numberOfLines={1}>{stock.name || stock.symbol}</Text>
                    <Label numberOfLines={1}>{stock.sector || t('watchlist_cse_listed')}</Label>
                  </View>
                  {/* Unstar = remove. Keyed by symbol; the API is idempotent. */}
                  <CircleButton
                    icon="star"
                    tone="yellow"
                    size={48}
                    onPress={() => handleRemove(stock.symbol)}
                    label={t('watchlist_remove').replace('{symbol}', stock.symbol)}
                  />
                </View>
                <View style={{ gap: 10 }}>
                  {typeof stock.price === 'number'
                    ? <BigNumber value={stock.price} prefix="LKR" size={40} />
                    : <Heading style={{ color: palette.muted }}>{t('watchlist_no_quote')}</Heading>}
                  {pct === null
                    ? <Chip label={t('watchlist_no_prior_close')} />
                    : <ChangePill pct={pct} />}
                </View>
              </Card>
            );
          })}
        </View>
      )}

      <PillButton icon="add" title={t('watchlist_add')} onPress={() => setAddModalVisible(true)} />

      {/* Add-symbol sheet */}
      <Modal visible={addModalVisible} animationType="fade" transparent onRequestClose={() => setAddModalVisible(false)}>
        <View style={styles.overlay}>
          <View style={styles.sheet}>
            <View style={{ gap: 6 }}>
              <Heading>{t('watchlist_modal_title')}</Heading>
              <Label>{t('watchlist_modal_hint')}</Label>
            </View>
            <Field
              value={symbolInput}
              onChangeText={setSymbolInput}
              placeholder={t('watchlist_symbol_placeholder')}
              accessibilityLabel={t('watchlist_modal_title')}
              autoCapitalize="characters"
              autoCorrect={false}
              autoFocus
              onSubmitEditing={handleAdd}
              inputStyle={styles.sheetField}
            />
            <View style={styles.actions}>
              <PillButton
                variant="secondary"
                title={t('cancel')}
                onPress={() => setAddModalVisible(false)}
                style={[styles.action, styles.cancel]}
              />
              <PillButton
                title={t('watchlist_add_button')}
                onPress={handleAdd}
                loading={adding}
                style={styles.action}
              />
            </View>
          </View>
        </View>
      </Modal>
    </Screen>
  );
}

const styles = StyleSheet.create({
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  ticker: {
    width: 48, height: 48, borderRadius: radii.full, backgroundColor: palette.yellow,
    alignItems: 'center', justifyContent: 'center',
  },
  tickerText: { fontFamily: fonts.bold, fontSize: 11, letterSpacing: 0.3, color: palette.yellowInk },
  companyName: { color: palette.ink, fontFamily: fonts.medium, fontSize: 17 },
  overlay: { flex: 1, backgroundColor: 'rgba(15,17,21,0.45)', justifyContent: 'center', paddingHorizontal: 20 },
  sheet: { backgroundColor: '#FFFFFF', borderRadius: radii.xl, padding: 24, gap: 18 },
  sheetField: { backgroundColor: '#EEF0F5', textTransform: 'uppercase' },
  actions: { flexDirection: 'row', gap: 10 },
  action: { flex: 1, paddingHorizontal: 12 },
  cancel: { backgroundColor: '#EEF0F5' },
});
