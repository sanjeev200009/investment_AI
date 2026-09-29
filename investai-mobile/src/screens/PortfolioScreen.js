// src/screens/PortfolioScreen.js
//
// Portfolio, v2 "Soft pastel": big light LKR total with a P&L pill, holdings
// as rows in a white glass card, sector split as a full-round segmented bar.
import TouchableTick from '../components/TouchableTick';
import React, { useState, useMemo, useCallback } from 'react';
import { View, Text, StyleSheet, Modal, Alert } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { toast } from '../components/Toast';
import {
  Screen, CircleButton, PillButton, Card, BigNumber, ChangePill, Title, Heading, Label, Body,
  Field, EmptyState, Loading,
} from '../components/ui';
import api from '../api/axiosConfig';
import { useT } from '../store/languageStore';
import { palette, fonts, radii, changeTone } from '../theme/tokens';

// Sector bucket for holdings with no sector; translated at render.
const UNCLASSIFIED = 'Unclassified';

const SECTOR_COLORS = [palette.lime, palette.yellow, palette.lavender, palette.coral, palette.mint];

const errorText = (err, fallback) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return fallback;
};

export default function PortfolioScreen({ navigation }) {
  const { t } = useT();

  const [portfolios, setPortfolios] = useState([]);
  const [holdings, setHoldings] = useState([]);
  const [marketData, setMarketData] = useState({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Modal State
  const [isAddModalVisible, setAddModalVisible] = useState(false);
  const [addSymbol, setAddSymbol] = useState('');
  const [addQuantity, setAddQuantity] = useState('');
  const [addPrice, setAddPrice] = useState('');
  const [addError, setAddError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    setLoadError(null);
    try {
      // Trailing slash matches the route exactly; without it every load cost a
      // 307 redirect. The market request covers the whole exchange (~291
      // symbols): at limit=200 any holding past row 200 alphabetically had no
      // quote and was silently valued at its buy price.
      const [portRes, marketRes] = await Promise.all([
        api.get('/portfolio/'),
        api.get('/stocks/market', { params: { limit: 500 } }),
      ]);

      const list = portRes.data || [];
      setPortfolios(list);
      setHoldings(list.flatMap(p => p.holdings || []));

      const marketMap = {};
      (marketRes.data || []).forEach(stock => { marketMap[stock.symbol] = stock; });
      setMarketData(marketMap);
    } catch (err) {
      // An error must not render as an empty portfolio worth 0.00 LKR.
      setLoadError(errorText(err, t('portfolio_load_error')));
    } finally {
      setLoading(false);
    }
  }, []);

  // Reload whenever the tab regains focus, so a holding added elsewhere or a
  // newer price shows without restarting the app.
  useFocusEffect(useCallback(() => { fetchData(); }, [fetchData]));

  const closeAddModal = () => {
    setAddModalVisible(false);
    setAddError(null);
  };

  const handleAddSubmit = async () => {
    const symbol = addSymbol.trim().toUpperCase();
    const quantity = Number(addQuantity);
    const price = Number(addPrice);
    if (!symbol) return setAddError(t('portfolio_err_symbol'));
    if (!Number.isFinite(quantity) || quantity <= 0) return setAddError(t('portfolio_err_quantity'));
    if (!Number.isFinite(price) || price <= 0) return setAddError(t('portfolio_err_price'));

    setAddError(null);
    setIsSubmitting(true);
    try {
      let pId = portfolios?.[0]?.portfolio_id;
      if (!pId) {
        const createRes = await api.post('/portfolio/', { name: 'My Primary Portfolio' });
        pId = createRes.data.portfolio_id;
      }
      await api.post(`/portfolio/${pId}/holdings`, { symbol, quantity, avg_buy_price: price });

      closeAddModal();
      toast(t('toast_holding_added').replace('{symbol}', symbol));
      setAddSymbol('');
      setAddQuantity('');
      setAddPrice('');
      fetchData();
    } catch (err) {
      setAddError(errorText(err, t('portfolio_save_error')));
    } finally {
      setIsSubmitting(false);
    }
  };

  const confirmRemove = (item) => {
    Alert.alert(
      t('portfolio_remove_title'),
      t('portfolio_remove_confirm').replace('{quantity}', item.quantity).replace('{symbol}', item.symbol),
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: t('portfolio_remove'),
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/portfolio/${item.portfolio_id}/holdings/${item.holding_id}`);
              toast(t('toast_holding_removed').replace('{symbol}', item.symbol), 'info');
              fetchData();
            } catch (err) {
              toast(errorText(err, t('portfolio_try_again_msg')), 'error');
            }
          },
        },
      ],
    );
  };

  const stats = useMemo(() => {
    let totalValue = 0;
    let totalCost = 0;
    let unpriced = 0;
    const sectors = {};

    const enrichedHoldings = holdings.map(h => {
      const market = marketData[h.symbol];
      const hasQuote = market && typeof market.price === 'number';
      const cost = h.avg_buy_price * h.quantity;
      // A holding with no quote keeps its cost basis in the totals (so the total
      // does not drop to zero) but shows no price and no P&L of its own.
      const val = hasQuote ? market.price * h.quantity : cost;
      if (!hasQuote) unpriced += 1;

      totalValue += val;
      totalCost += cost;

      // The backend's own industry group, not a guess from the ticker prefix.
      const sector = market?.sector || UNCLASSIFIED;
      sectors[sector] = (sectors[sector] || 0) + val;

      return {
        ...h,
        hasQuote,
        currentPrice: hasQuote ? market.price : null,
        marketChange: hasQuote && typeof market.change_pct === 'number' ? market.change_pct : null,
        name: market?.name || h.symbol,
        currentValue: val,
        pnlPct: hasQuote && cost > 0 ? ((val - cost) / cost) * 100 : null,
      };
    });

    const totalPnl = totalValue - totalCost;
    const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
    enrichedHoldings.sort((a, b) => b.currentValue - a.currentValue);

    const sectorAllocations = Object.entries(sectors)
      .map(([name, val]) => ({ name, val, pct: totalValue > 0 ? (val / totalValue) * 100 : 0 }))
      .sort((a, b) => b.pct - a.pct);

    return { totalValue, totalPnl, totalPnlPct, enrichedHoldings, sectorAllocations, unpriced };
  }, [holdings, marketData]);

  const fmt = (n) => n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <Screen refreshing={false} onRefresh={fetchData}>
      <View style={styles.headRow}>
        <View style={{ flex: 1, gap: 4 }}>
          <Title>{t('portfolio_my')}</Title>
          <Label>{t('portfolio_subtitle')}</Label>
        </View>
        <CircleButton icon="add" label={t('portfolio_add')} onPress={() => setAddModalVisible(true)} />
      </View>

      {loadError ? (
        <EmptyState
          icon="cloud-off"
          tone="coral"
          message={loadError}
          action={t('retry')}
          onAction={() => { setLoading(true); fetchData(); }}
        />
      ) : (
        <>
          {/* Total value */}
          <View style={{ gap: 10 }}>
            <Label>{t('portfolio_total_value')}</Label>
            <BigNumber value={loading ? null : stats.totalValue} prefix="LKR" size={56} />
            {!loading && stats.enrichedHoldings.length > 0 && (
              <View style={styles.pnlRow}>
                <ChangePill pct={stats.totalPnlPct} />
                <Label style={{ flexShrink: 1 }}>
                  {t('portfolio_all_time_pnl').replace('{amount}', `${stats.totalPnl >= 0 ? '+' : ''}LKR ${fmt(stats.totalPnl)}`)}
                </Label>
              </View>
            )}
            {stats.unpriced > 0 && (
              <Label style={{ color: palette.faint }}>
                {t(stats.unpriced > 1 ? 'portfolio_unpriced_other' : 'portfolio_unpriced_one').replace('{n}', stats.unpriced)}
              </Label>
            )}
          </View>

          {/* Holdings */}
          <View style={{ gap: 12 }}>
            <Heading>{t('portfolio_holdings')}</Heading>
            <Card style={{ padding: 8 }}>
              {loading ? (
                <Loading />
              ) : stats.enrichedHoldings.length === 0 ? (
                <Body style={{ color: palette.muted, padding: 12 }}>{t('portfolio_empty')}</Body>
              ) : stats.enrichedHoldings.map((item, i) => {
                const tone = changeTone(item.pnlPct);
                return (
                  <View key={item.holding_id}>
                    {i > 0 && <View style={styles.divider} />}
                    <TouchableTick
                      style={styles.row}
                      accessibilityRole="button"
                      accessibilityLabel={item.symbol}
                      onPress={() => navigation.navigate('StockDetail', { stock: {
                        symbol: item.symbol,
                        name: item.name,
                        price: item.currentPrice,
                        change: item.marketChange === null ? '—' : `${item.marketChange.toFixed(2)}%`,
                        isPositive: (item.marketChange ?? 0) >= 0,
                      } })}
                      onLongPress={() => confirmRemove(item)}
                    >
                      <View style={[styles.ticker, { backgroundColor: tone.background }]}>
                        <Text style={[styles.tickerText, { color: tone.ink }]}>{item.symbol.split('.')[0].slice(0, 4)}</Text>
                      </View>
                      <View style={{ flex: 1, gap: 2, minWidth: 0 }}>
                        <Text style={styles.rowTitle} numberOfLines={1}>{item.symbol}</Text>
                        <Label numberOfLines={1}>
                          {t('portfolio_shares_at').replace('{quantity}', item.quantity).replace('{price}', fmt(item.avg_buy_price))}
                        </Label>
                      </View>
                      <View style={{ alignItems: 'flex-end', gap: 2 }}>
                        <Text style={styles.rowFigure}>
                          {item.currentPrice === null ? t('portfolio_no_quote') : `LKR ${fmt(item.currentPrice)}`}
                        </Text>
                        {item.pnlPct !== null && (
                          <Text style={[styles.rowChange, { color: tone.ink }]}>
                            {tone.arrow ? `${tone.arrow} ` : ''}{tone.sign}{Math.abs(item.pnlPct).toFixed(1)}%
                          </Text>
                        )}
                      </View>
                      <CircleButton
                        icon="delete-outline"
                        size={44}
                        iconColor={palette.muted}
                        label={t('portfolio_remove_a11y').replace('{symbol}', item.symbol)}
                        onPress={() => confirmRemove(item)}
                      />
                    </TouchableTick>
                  </View>
                );
              })}
            </Card>
          </View>

          {/* Sector allocation: proportional bar drawn from the real split. */}
          {stats.sectorAllocations.length > 0 && (
            <Card style={{ gap: 14 }}>
              <Label>{t('portfolio_sector_allocation')}</Label>
              <View style={styles.stackBar}>
                {stats.sectorAllocations.map((sec, idx) => (
                  <View
                    key={sec.name}
                    style={{ flex: Math.max(sec.pct, 0.5), borderRadius: radii.full, backgroundColor: SECTOR_COLORS[idx % SECTOR_COLORS.length] }}
                  />
                ))}
              </View>
              <View style={{ gap: 10 }}>
                {stats.sectorAllocations.map((sec, idx) => (
                  <View key={sec.name} style={styles.legendRow}>
                    <View style={[styles.legendDot, { backgroundColor: SECTOR_COLORS[idx % SECTOR_COLORS.length] }]} />
                    <Text style={styles.legendName} numberOfLines={1}>
                      {sec.name === UNCLASSIFIED ? t('portfolio_unclassified') : sec.name}
                    </Text>
                    <Text style={styles.legendValue}>{sec.pct.toFixed(0)}%</Text>
                  </View>
                ))}
              </View>
            </Card>
          )}
        </>
      )}

      <Modal visible={isAddModalVisible} animationType="slide" transparent={true} onRequestClose={closeAddModal}>
        <View style={styles.modalOverlay}>
          <View style={styles.sheet}>
            <View style={styles.headRow}>
              <Heading style={{ flex: 1 }}>{t('portfolio_add')}</Heading>
              <CircleButton icon="close" label={t('portfolio_close')} onPress={closeAddModal} />
            </View>

            <Field
              label={t('portfolio_symbol_label')}
              value={addSymbol}
              onChangeText={setAddSymbol}
              placeholder={t('portfolio_symbol_placeholder')}
              autoCapitalize="characters"
            />
            <Field
              label={t('portfolio_quantity')}
              value={addQuantity}
              onChangeText={setAddQuantity}
              placeholder={t('portfolio_quantity_placeholder')}
              keyboardType="numeric"
            />
            <Field
              label={t('portfolio_avg_price')}
              value={addPrice}
              onChangeText={setAddPrice}
              placeholder={t('portfolio_price_placeholder')}
              keyboardType="numeric"
            />

            {addError ? <Body style={{ color: palette.error, paddingLeft: 18 }}>{addError}</Body> : null}

            <PillButton title={t('portfolio_save_holding')} onPress={handleAddSubmit} loading={isSubmitting} />
          </View>
        </View>
      </Modal>
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  pnlRow: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, minHeight: 68 },
  divider: { height: 1, backgroundColor: palette.hairline, marginHorizontal: 12 },
  ticker: { width: 48, height: 48, borderRadius: radii.full, alignItems: 'center', justifyContent: 'center' },
  tickerText: { fontFamily: fonts.bold, fontSize: 11, letterSpacing: 0.3 },
  rowTitle: { ...text, fontFamily: fonts.medium, fontSize: 16 },
  rowFigure: { ...text, fontFamily: fonts.medium, fontSize: 15, fontVariant: ['tabular-nums'] },
  rowChange: { ...text, fontSize: 13, fontVariant: ['tabular-nums'] },
  stackBar: { flexDirection: 'row', height: 14, gap: 4 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  legendDot: { width: 12, height: 12, borderRadius: radii.full },
  legendName: { ...text, flex: 1, fontSize: 15 },
  legendValue: { ...text, fontFamily: fonts.medium, fontSize: 15, fontVariant: ['tabular-nums'] },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15,17,21,0.45)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#F3F3FA', borderTopLeftRadius: radii.xxl, borderTopRightRadius: radii.xxl,
    padding: 20, paddingBottom: 40, gap: 16,
  },
});
