// src/screens/HomeScreen.js
//
// Home, v2 "Soft pastel" (see the design canvas): big light index figure,
// circle-icon stats, pastel pill shortcuts, white glass cards.
// Every number here is measured or absent: the ASPI and its as-of date, the
// sector turnover split, AI insights, ranked picks with their factors, the
// market list and the portfolio's recorded valuations. Where a value does not
// exist the screen says so instead of substituting one.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import {
  Screen, CircleButton, IconCircle, PillButton, Chip, Card, StackCard, BigNumber, ChangePill,
  Heading, Label, Body, Loading, accent, ACCENT_CYCLE,
} from '../components/ui';
import TouchableTick from '../components/TouchableTick';
import InitialsAvatar from '../components/InitialsAvatar';
import { useAuthStore } from '../store/authStore';
import { useT } from '../store/languageStore';
import { recommendationsApi } from '../api/api';
import api from '../api/axiosConfig';
import { palette, fonts, radii, changeTone } from '../theme/tokens';

// The two chips that are not sectors. Values are state keys; labels come from CHIP_LABEL_KEYS.
const ALL_MARKETS = 'Most traded';
const TOP_MOVERS = 'Top movers';
const CHIP_LABEL_KEYS = { [ALL_MARKETS]: 'home_chip_most_traded', [TOP_MOVERS]: 'home_chip_top_movers' };

// Sector turnover slices, largest first; the last is the "Other sectors" rollup.
const SECTOR_COLOURS = [palette.lime, palette.yellow, palette.lavender, palette.coral];

const fmt = (n, digits = 2) =>
  Number(n).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });

// `t` is the translator from useT(); constants outside the component cannot call the hook.
const pctText = (pct, t) => {
  if (pct === null || pct === undefined || !Number.isFinite(Number(pct))) return t('home_no_prior_close');
  const tone = changeTone(pct);
  return `${tone.sign}${Math.abs(Number(pct)).toFixed(2)}%`;
};

const dayLabel = (iso) => {
  const parsed = new Date(`${iso}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? String(iso ?? '')
    : parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
};

export default function HomeScreen({ navigation }) {
  const user = useAuthStore(state => state.user);
  const { t } = useT();
  const firstName = (user?.full_name || '').trim().split(/\s+/)[0] || t('home_investor');

  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState(false);
  // The proposal tracks ASPI *and* S&P SL20 (6.2); the dashboard payload has
  // only ASPI, so the second headline index comes from /stocks/indices.
  const [sl20, setSl20] = useState(null);
  const [banks, setBanks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [picks, setPicks] = useState([]);
  const [picksWeights, setPicksWeights] = useState({});
  const [riskCategory, setRiskCategory] = useState(null);
  const [expandedPick, setExpandedPick] = useState(null);

  const [sectorChips, setSectorChips] = useState([]);
  const [activeChip, setActiveChip] = useState(ALL_MARKETS);
  const [stocks, setStocks] = useState([]);
  const [stocksError, setStocksError] = useState(null);

  const loadDashboard = useCallback(async () => {
    const [dash, recs, sectors, indices] = await Promise.allSettled([
      api.get('/dashboard/'),
      recommendationsApi.top(5),
      api.get('/stocks/sectors'),
      api.get('/stocks/indices'),
    ]);
    const indexRows = indices.status === 'fulfilled' ? indices.value.data || [] : [];
    setSl20(indexRows.find(i => i.index_code === 'SPSL20') || null);
    setBanks(indexRows.find(i => i.index_code === 'BNK') || null);
    // No substitute payloads on failure: an unavailable figure is shown as
    // unavailable, never replaced with an invented one.
    setDashboard(dash.status === 'fulfilled' ? dash.value.data : null);
    setDashboardError(dash.status === 'rejected');
    setPicks(recs.status === 'fulfilled' ? recs.value.items || [] : []);
    setPicksWeights(recs.status === 'fulfilled' ? recs.value.weights || {} : {});
    setRiskCategory(recs.status === 'fulfilled' ? recs.value.risk_category || null : null);
    setSectorChips(sectors.status === 'fulfilled' ? sectors.value.data || [] : []);
  }, []);

  const loadStocks = useCallback(async (chip) => {
    setStocksError(null);
    const params = { limit: 50 };
    if (chip !== ALL_MARKETS && chip !== TOP_MOVERS) {
      // The whole sector, so the preview shows its real leaders.
      params.sector = chip;
      params.limit = 400;
    }
    try {
      const { data } = await api.get('/stocks/market', { params });
      setStocks(data || []);
    } catch (err) {
      setStocks([]);
      setStocksError(err?.response?.data?.detail || 'MARKET_UNAVAILABLE');
    }
  }, []);

  useEffect(() => {
    loadDashboard().finally(() => setLoading(false));
  }, [loadDashboard]);

  useEffect(() => { loadStocks(activeChip); }, [activeChip, loadStocks]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([loadDashboard(), loadStocks(activeChip)]);
    setRefreshing(false);
  }, [loadDashboard, loadStocks, activeChip]);

  // Six rows. Nulls sort last: an untraded stock must not outrank real movers.
  const marketRows = useMemo(() => {
    const key = activeChip === TOP_MOVERS ? 'change_pct' : 'volume';
    return [...stocks]
      .sort((a, b) => {
        const x = a[key], y = b[key];
        if (!Number.isFinite(x)) return Number.isFinite(y) ? 1 : 0;
        if (!Number.isFinite(y)) return -1;
        return y - x;
      })
      .slice(0, 6);
  }, [stocks, activeChip]);

  const aspi = dashboard?.aspi || null;
  // cse.lk serves the last session while the market is shut; say which one.
  const aspiAsOf = useMemo(() => {
    if (!aspi?.recorded_at) return null;
    const at = new Date(aspi.recorded_at);
    if (Number.isNaN(at.getTime())) return null;
    const label = at.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    return at.toDateString() === new Date().toDateString() ? t('home_today') : t('home_close_on').replace('{date}', label);
  }, [aspi, t]);

  const sectors = (dashboard?.sectors || []).map((s, i) => ({
    ...s,
    share: Math.max(Number(s.share_pct) || 0, 0),
    colour: SECTOR_COLOURS[i] || SECTOR_COLOURS[SECTOR_COLOURS.length - 1],
  }));

  const insights = dashboard?.insights || [];

  const portfolioValue = Number(dashboard?.portfolio?.current_value);
  const hasPortfolio = Number.isFinite(portfolioValue) && portfolioValue > 0;
  const history = (Array.isArray(dashboard?.portfolio?.history) ? dashboard.portfolio.history : [])
    .filter(p => p && Number.isFinite(Number(p.value)));
  const historyMax = Math.max(...history.map(p => Number(p.value)), 1);
  const firstValue = history.length ? Number(history[0].value) : 0;
  const lastValue = history.length ? Number(history[history.length - 1].value) : 0;
  const windowChange = history.length >= 2 && firstValue !== 0
    ? ((lastValue - firstValue) / firstValue) * 100
    : null;

  const openStock = (s) => navigation.navigate('StockDetail', {
    stock: {
      symbol: s.symbol,
      name: s.name || s.symbol,
      price: s.price,
      change: Number.isFinite(s.change_pct) ? `${s.change_pct.toFixed(2)}%` : '—',
      isPositive: (s.change_pct ?? 0) >= 0,
    },
  });

  if (loading) {
    return <Screen scroll={false}><Loading /></Screen>;
  }

  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
  const topPick = picks[0] || null;
  const topSector = sectors[0] || null;

  return (
    <Screen refreshing={refreshing} onRefresh={onRefresh}>
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={styles.caption}>{today}</Text>
          <Text style={styles.greeting} numberOfLines={1}>{t('home_greeting')}, {firstName}</Text>
        </View>
        <TouchableTick onPress={() => navigation.navigate('ProfileMain')} accessibilityLabel={t('home_profile_settings')}>
          <InitialsAvatar name={user?.full_name} size={56} background={palette.coral} />
        </TouchableTick>
        <CircleButton icon="notifications-none" label={t('tab_alerts')} onPress={() => navigation.navigate('Alerts')} />
      </View>

      {/* ASPI hero */}
      <View style={{ gap: 10 }}>
        <Label>{t('home_aspi')}{aspiAsOf ? ` · ${aspiAsOf}` : ''}</Label>
        {aspi ? (
          <>
            <BigNumber value={aspi.value} size={64} />
            <ChangePill change={aspi.change} pct={aspi.change_pct} />
          </>
        ) : (
          <Body style={{ color: palette.muted }}>
            {dashboardError ? t('home_market_unavailable_retry') : t('home_no_index')}
          </Body>
        )}
      </View>

      {/* Three headline stats */}
      <View style={styles.stats}>
        <View style={styles.stat}>
          <IconCircle icon="bar-chart" />
          <Label>S&P SL20</Label>
          <Text style={styles.statValue}>{sl20 ? fmt(sl20.value) : '—'}</Text>
          {sl20 ? <Text style={[styles.statSub, { color: changeTone(sl20.change_pct).ink }]}>{pctText(sl20.change_pct, t)}</Text> : null}
        </View>
        <View style={styles.stat}>
          <IconCircle icon="account-balance" />
          <Label>{t('home_banks')}</Label>
          <Text style={styles.statValue}>{banks ? fmt(banks.value) : '—'}</Text>
          {banks ? <Text style={[styles.statSub, { color: changeTone(banks.change_pct).ink }]}>{pctText(banks.change_pct, t)}</Text> : null}
        </View>
        <View style={styles.stat}>
          <IconCircle icon="donut-large" />
          <Label>{t('home_top_turnover')}</Label>
          <Text style={styles.statValue} numberOfLines={1}>{topSector ? `${topSector.share.toFixed(0)}%` : '—'}</Text>
          {topSector ? <Text style={styles.statSub} numberOfLines={1}>{topSector.name}</Text> : null}
        </View>
      </View>

      {/* Pastel pill row: Portfolio · Watchlist · Stocks to study */}
      <View style={styles.pillRow}>
        <TouchableTick style={[styles.tallPill, { backgroundColor: palette.lime }]} onPress={() => navigation.navigate('Portfolio')} accessibilityLabel={t('home_open_portfolio')}>
          <IconCircle icon="pie-chart-outline" color={palette.limeInk} borderColor="rgba(0,0,0,0.15)" size={52} />
          <Text style={[styles.pillLabel, { color: palette.limeInk }]}>{t('home_your_portfolio')}</Text>
        </TouchableTick>
        <TouchableTick style={[styles.tallPill, { backgroundColor: palette.yellow }]} onPress={() => navigation.navigate('Watchlist')} accessibilityLabel={t('home_your_watchlist')}>
          <IconCircle icon="star-border" color={palette.yellowInk} borderColor="rgba(0,0,0,0.15)" size={52} />
          <Text style={[styles.pillLabel, { color: palette.yellowInk }]}>{t('home_your_watchlist')}</Text>
        </TouchableTick>
        <View style={styles.striped}>
          <View style={styles.stripes} pointerEvents="none">
            {Array.from({ length: 26 }).map((_, i) => <View key={i} style={styles.stripe} />)}
          </View>
          <View style={{ gap: 8 }}>
            <Chip label={t('home_stocks_to_study')} icon="auto-awesome" tone="white" />
            <View style={styles.pickBox}>
              <Label>{topPick ? t('home_top_score') : t('home_balanced_weighting')}</Label>
              <Text style={styles.pickSymbol} numberOfLines={1}>
                {topPick ? topPick.symbol.split('.')[0] : '—'}
                {topPick && Number.isFinite(Number(topPick.price))
                  ? <Text style={styles.pickPrice}>  {fmt(topPick.price)}</Text> : null}
              </Text>
            </View>
          </View>
          <PillButton title={t('home_ask_investai')} onPress={() => navigation.navigate('AIChat')} />
        </View>
      </View>

      {/* Portfolio value + recorded history */}
      <Card onPress={() => navigation.navigate('Portfolio')} label={t('home_open_portfolio')} style={{ gap: 12 }}>
        <View style={styles.rowBetween}>
          <Label>{t('home_your_portfolio')}</Label>
          <MaterialIcons name="arrow-forward" size={20} color={palette.ink} />
        </View>
        {hasPortfolio ? (
          <>
            <BigNumber value={portfolioValue} prefix="LKR" size={40} />
            <Label>
              {windowChange === null
                ? t('home_valued_latest')
                : t('home_change_over_days')
                  .replace('{pct}', `${changeTone(windowChange).sign}${Math.abs(windowChange).toFixed(1)}%`)
                  .replace('{days}', history.length)}
            </Label>
            {history.length >= 2 && (
              <View style={{ gap: 6 }}>
                <View style={styles.bars}>
                  {history.map((p, i) => (
                    <View
                      key={p.date ?? i}
                      style={[styles.bar, {
                        height: Math.max(6, (Number(p.value) / historyMax) * 64),
                        backgroundColor: i === history.length - 1 ? palette.lime : '#E3E6EE',
                      }]}
                    />
                  ))}
                </View>
                <View style={styles.rowBetween}>
                  <Label>{dayLabel(history[0].date)}</Label>
                  <Label>{dayLabel(history[history.length - 1].date)}</Label>
                </View>
              </View>
            )}
          </>
        ) : (
          <Body style={{ color: palette.muted }}>{t('home_no_holdings')}</Body>
        )}
      </Card>

      {/* Turnover by sector */}
      {sectors.length > 0 && (
        <Card style={{ gap: 14 }}>
          <Label>{t('home_turnover_by_sector')}</Label>
          <View style={styles.stackBar}>
            {sectors.map(s => <View key={s.code} style={{ flex: Math.max(s.share, 0.5), backgroundColor: s.colour, borderRadius: radii.full }} />)}
          </View>
          <View style={{ gap: 10 }}>
            {sectors.map(s => (
              <View key={s.code} style={styles.legendRow}>
                <View style={[styles.legendDot, { backgroundColor: s.colour }]} />
                <Text style={styles.legendName} numberOfLines={1}>{s.name}</Text>
                <Text style={styles.legendValue}>{s.share.toFixed(0)}%</Text>
              </View>
            ))}
          </View>
        </Card>
      )}

      {/* AI market notes */}
      {insights.length > 0 && (
        <View style={{ gap: 12 }}>
          <Heading>{t('home_market_notes')}</Heading>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingRight: 20 }}>
            {insights.map((item, i) => {
              const tone = ACCENT_CYCLE[(i + 2) % ACCENT_CYCLE.length];
              const a = accent(tone);
              return (
                <Card key={item.id ?? i} tone={tone} style={{ width: 280, gap: 10 }}>
                  <Chip label={item.label} icon="auto-awesome" tone="white" />
                  <Body style={{ color: a.ink }}>{item.body}</Body>
                </Card>
              );
            })}
          </ScrollView>
          <Label style={{ color: palette.faint }}>{t('home_ai_disclaimer')}</Label>
        </View>
      )}

      {/* Stocks to study, with the factors behind each score */}
      {picks.length > 0 && (
        <View style={{ gap: 12 }}>
          <View style={styles.rowBetween}>
            <Heading>{t('home_stocks_to_study')}</Heading>
            <Label style={{ flexShrink: 1, textAlign: 'right' }}>
              {riskCategory ? t('home_weighted_for_risk').replace('{risk}', riskCategory.toLowerCase()) : t('home_balanced_weighting')}
            </Label>
          </View>
          <Card style={{ padding: 8 }}>
            {picks.map((pick, i) => {
              const open = expandedPick === pick.symbol;
              return (
                <View key={pick.symbol}>
                  {i > 0 && <View style={styles.divider} />}
                  <TouchableTick
                    style={styles.row}
                    onPress={() => setExpandedPick(open ? null : pick.symbol)}
                    accessibilityLabel={t(open ? 'home_pick_a11y_hide' : 'home_pick_a11y_show').replace('{symbol}', pick.symbol).replace('{score}', pick.score)}
                  >
                    <View style={[styles.ticker, { backgroundColor: palette.lime }]}>
                      <Text style={[styles.tickerText, { color: palette.limeInk }]}>{Math.round(pick.score)}</Text>
                    </View>
                    <View style={{ flex: 1, gap: 2 }}>
                      <Text style={styles.rowTitle}>{pick.symbol.split('.')[0]}</Text>
                      <Label numberOfLines={1}>{pick.name || pick.sector || ''}</Label>
                    </View>
                    <MaterialIcons name={open ? 'expand-less' : 'expand-more'} size={24} color={palette.muted} />
                  </TouchableTick>
                  {open && (
                    <View style={styles.factors}>
                      {Object.entries(pick.factors || {}).map(([key, f]) => {
                        const tone = changeTone(f.contribution);
                        return (
                          <View key={key} style={styles.rowBetween}>
                            <Body style={{ flex: 1 }}>{f.label || key}</Body>
                            <View style={[styles.factorPill, { backgroundColor: tone.background }]}>
                              <Text style={[styles.factorText, { color: tone.ink }]}>
                                {tone.sign}{Math.abs(f.contribution).toFixed(1)} {t('home_pts')}
                              </Text>
                            </View>
                          </View>
                        );
                      })}
                      <Label style={{ color: palette.faint }}>
                        {t('home_weights')} {Object.entries(picksWeights).map(([k, w]) => `${k.replace('_', ' ')} ${(w * 100).toFixed(0)}%`).join(' · ')}.
                        {' '}{t('home_score_disclaimer')}
                      </Label>
                    </View>
                  )}
                </View>
              );
            })}
          </Card>
        </View>
      )}

      {/* Market */}
      <View style={{ gap: 12 }}>
        <View style={styles.rowBetween}>
          <Heading>{t('home_market')}</Heading>
          <TouchableTick onPress={() => navigation.navigate('Markets')} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
            <Text style={styles.link}>{t('home_see_all')}</Text>
          </TouchableTick>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingRight: 20 }}>
          {[ALL_MARKETS, TOP_MOVERS, ...sectorChips.map(s => s.sector)].map(label => (
            <Chip
              key={label}
              label={CHIP_LABEL_KEYS[label] ? t(CHIP_LABEL_KEYS[label]) : label}
              selected={label === activeChip}
              onPress={() => setActiveChip(label)}
            />
          ))}
        </ScrollView>
        <Card style={{ padding: 8 }}>
          {stocksError ? (
            <Body style={{ color: palette.muted, padding: 12 }}>{stocksError === 'MARKET_UNAVAILABLE' ? t('home_market_unavailable') : stocksError}</Body>
          ) : marketRows.length === 0 ? (
            <Body style={{ color: palette.muted, padding: 12 }}>{t('home_no_quotes')}</Body>
          ) : marketRows.map((s, i) => {
            const tone = changeTone(s.change_pct);
            return (
              <View key={s.symbol}>
                {i > 0 && <View style={styles.divider} />}
                <TouchableTick style={styles.row} onPress={() => openStock(s)} accessibilityLabel={t('home_open_symbol').replace('{symbol}', s.symbol)}>
                  <View style={[styles.ticker, { backgroundColor: tone.background }]}>
                    <Text style={[styles.tickerText, { color: tone.ink }]}>{s.symbol.split('.')[0].slice(0, 4)}</Text>
                  </View>
                  <View style={{ flex: 1, gap: 2, minWidth: 0 }}>
                    <Text style={styles.rowTitle} numberOfLines={1}>{s.name || s.symbol}</Text>
                    <Label numberOfLines={1}>{s.sector || t('home_cse_listed')}</Label>
                  </View>
                  <View style={{ alignItems: 'flex-end', gap: 2 }}>
                    <Text style={styles.rowFigure}>{Number.isFinite(s.price) ? fmt(s.price) : '—'}</Text>
                    <Text style={[styles.rowChange, { color: tone.ink }]}>{pctText(s.change_pct, t)}</Text>
                  </View>
                </TouchableTick>
              </View>
            );
          })}
        </Card>
      </View>

      {/* Learn */}
      <StackCard tone="lavender" first last onPress={() => navigation.navigate('Learn')} label={t('home_learn_basics')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
          <IconCircle icon="menu-book" color={palette.lavenderInk} borderColor="rgba(0,0,0,0.15)" size={52} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={[styles.rowTitle, { color: palette.lavenderInk, fontSize: 18 }]}>{t('home_learn_basics')}</Text>
            <Label style={{ color: palette.lavenderInk }}>{t('home_learn_sub')}</Label>
          </View>
          <MaterialIcons name="arrow-forward" size={22} color={palette.lavenderInk} />
        </View>
      </StackCard>
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  greeting: { ...text, fontSize: 22, letterSpacing: -0.4 },
  caption: { ...text, fontSize: 13, color: palette.muted },
  stats: { flexDirection: 'row', gap: 10 },
  stat: { flex: 1, gap: 6 },
  statValue: { ...text, fontFamily: fonts.medium, fontSize: 17, fontVariant: ['tabular-nums'] },
  statSub: { ...text, fontSize: 12, color: palette.muted },
  pillRow: { flexDirection: 'row', gap: 10, height: 260 },
  tallPill: {
    width: 78, borderRadius: radii.full, paddingTop: 12, paddingBottom: 20,
    alignItems: 'center', justifyContent: 'space-between', overflow: 'hidden',
  },
  pillLabel: {
    fontFamily: fonts.medium, fontSize: 15, width: 150, textAlign: 'center',
    transform: [{ rotate: '-90deg' }], marginBottom: 60,
  },
  striped: {
    flex: 1, borderRadius: 40, padding: 12, justifyContent: 'space-between',
    backgroundColor: 'rgba(255,255,255,0.55)', overflow: 'hidden',
  },
  stripes: { ...StyleSheet.absoluteFillObject, flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 4 },
  stripe: { width: 2, backgroundColor: 'rgba(15,17,21,0.07)' },
  pickBox: { backgroundColor: 'rgba(255,255,255,0.92)', borderRadius: 22, padding: 14, gap: 2 },
  pickSymbol: { ...text, fontFamily: fonts.medium, fontSize: 24, letterSpacing: -0.5 },
  pickPrice: { fontFamily: fonts.regular, fontSize: 15, color: palette.muted },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  bars: { flexDirection: 'row', alignItems: 'flex-end', gap: 4, height: 64 },
  bar: { flex: 1, borderRadius: radii.full },
  stackBar: { flexDirection: 'row', height: 14, gap: 4 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  legendDot: { width: 12, height: 12, borderRadius: radii.full },
  legendName: { ...text, flex: 1, fontSize: 15 },
  legendValue: { ...text, fontFamily: fonts.medium, fontSize: 15, fontVariant: ['tabular-nums'] },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 12, minHeight: 68 },
  divider: { height: 1, backgroundColor: palette.hairline, marginHorizontal: 12 },
  ticker: { width: 48, height: 48, borderRadius: radii.full, alignItems: 'center', justifyContent: 'center' },
  tickerText: { fontFamily: fonts.bold, fontSize: 11, letterSpacing: 0.3 },
  rowTitle: { ...text, fontFamily: fonts.medium, fontSize: 16 },
  rowFigure: { ...text, fontFamily: fonts.medium, fontSize: 16, fontVariant: ['tabular-nums'] },
  rowChange: { ...text, fontSize: 13, fontVariant: ['tabular-nums'] },
  factors: { paddingHorizontal: 12, paddingBottom: 14, gap: 10 },
  factorPill: { borderRadius: radii.full, paddingHorizontal: 10, paddingVertical: 4 },
  factorText: { fontFamily: fonts.medium, fontSize: 13 },
  link: { ...text, fontFamily: fonts.medium, fontSize: 15, textDecorationLine: 'underline' },
});
