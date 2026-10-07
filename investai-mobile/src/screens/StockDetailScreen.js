// src/screens/StockDetailScreen.js
//
// Stock detail, v2 "Soft pastel" (see V2Stock): circle header with watchlist and
// alert, big light price, change pill, key-stat grid, the recorded close series,
// range track, news on lavender, and one black action to ask the assistant.
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Dimensions, ActivityIndicator, Linking } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { LineChart } from 'react-native-chart-kit';
import TouchableTick from '../components/TouchableTick';
import { toast } from '../components/Toast';
import {
    Screen, Header, CircleButton, PillButton, Chip, Card, BigNumber, ChangePill,
    Label, Body, EmptyState,
} from '../components/ui';
import api from '../api/axiosConfig';
import { watchlistApi } from '../api/api';
import { palette, fonts, radii } from '../theme/tokens';
import { useT } from '../store/languageStore';
import { CoinStar } from '../components/Motion';
import { afterTransition } from '../theme/motion';

const { width } = Dimensions.get('window');

// The windows GET /stocks/history/{symbol} accepts, in the order the backend
// declares them, so the screen cannot ask for a range the endpoint answers 422 for.
const RANGES = ['1W', '1M', '3M', '6M', '1Y', 'ALL'];

const shortDate = (iso) => {
    const parsed = new Date(`${iso}T00:00:00`);
    return Number.isNaN(parsed.getTime())
        ? String(iso ?? '')
        : parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
};

// Market cap in the units a Sri Lankan reader uses; the suffix carries the
// three-order-of-magnitude spread between listed companies.
const formatMarketCap = (value) => {
    if (!Number.isFinite(value) || value <= 0) return null;
    if (value >= 1e12) return `Rs. ${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `Rs. ${(value / 1e9).toFixed(1)}B`;
    if (value >= 1e6) return `Rs. ${(value / 1e6).toFixed(1)}M`;
    return `Rs. ${value.toFixed(0)}`;
};

// Grouped rather than abbreviated: a share count is a countable quantity.
const formatShares = (value) =>
    Number.isFinite(value) && value > 0 ? value.toLocaleString('en-US') : null;

// A tile renders only when there is something real to put in it; an absent tile
// says "the exchange does not publish this" more clearly than a placeholder.
// `t` is the translator from useT(); passed in because this lives outside the component.
const buildStats = (info, t) => {
    if (!info) return [];
    return [
        { label: t('detail_market_cap'), value: formatMarketCap(info.market_cap) },
        {
            label: t('detail_52w_low'),
            // The exchange's own 12-month low. No matching high: cse.lk's
            // p12HiPrice is not restated after a forward split.
            value: Number.isFinite(info.week52_low)
                ? `Rs. ${info.week52_low.toFixed(2)}` : null,
            // Recomputed between sessions, not intraday, so the as-of is named.
            hint: t('detail_52w_low_hint'),
        },
        {
            label: t('detail_beta'),
            // Zero and negative are real readings, hence Number.isFinite.
            value: Number.isFinite(info.beta_asi) ? info.beta_asi.toFixed(2) : null,
            hint: info.beta_period ? `CSE, ${info.beta_period}` : t('detail_beta_hint'),
        },
        { label: t('detail_shares_issued'), value: formatShares(info.shares_issued) },
        {
            label: t('detail_market_weight'),
            value: Number.isFinite(info.market_cap_pct)
                ? `${info.market_cap_pct.toFixed(2)}%` : null,
            hint: t('detail_market_weight_hint'),
        },
        { label: t('detail_board'), value: info.board },
    ].filter(stat => stat.value !== null && stat.value !== undefined);
};

const sentimentTone = (score) => (score > 0 ? 'lime' : score < 0 ? 'coral' : 'white');
const capitalise = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

export default function StockDetailScreen({ route, navigation }) {
    const { t } = useT();
    // Always opened with a stock; there is no invented fallback quote.
    const stock = route.params?.stock || { symbol: '' };
    const [watchState, setWatchState] = useState('idle'); // idle | saving | added

    // The real daily-close series from GET /stocks/history/{symbol}.
    const [range, setRange] = useState('1M');
    const [history, setHistory] = useState(null);      // null while in flight
    // The chart is drawn only once the page has finished opening: computing a
    // year of points mid-transition is what made the opening stutter.
    const [settled, setSettled] = useState(false);
    useEffect(() => afterTransition(() => setSettled(true)), []);
    const [historyError, setHistoryError] = useState(null);

    // Fundamentals from GET /stocks/company/{symbol}. `undefined` while in flight,
    // `null` when the exchange has no profile for this symbol.
    const [info, setInfo] = useState(undefined);

    useEffect(() => {
        // Guards against a slower earlier response landing after a newer one.
        let cancelled = false;
        setHistory(null);
        setHistoryError(null);

        api.get(`/stocks/history/${encodeURIComponent(stock.symbol)}`, { params: { range } })
            .then(({ data }) => { if (!cancelled) setHistory(data); })
            .catch(err => {
                if (!cancelled) {
                    setHistoryError(err.response?.data?.detail
                        || err.message
                        || 'HISTORY_ERROR');
                }
            });

        return () => { cancelled = true; };
    }, [stock.symbol, range]);

    useEffect(() => {
        // Separate from the history effect because it does not depend on `range`.
        let cancelled = false;
        setInfo(undefined);

        api.get(`/stocks/company/${encodeURIComponent(stock.symbol)}`)
            .then(({ data }) => { if (!cancelled) setInfo(data); })
            // A 404 is the documented answer for a symbol with no profile; any
            // failure is treated as "no fundamentals" rather than blocking the chart.
            .catch(() => { if (!cancelled) setInfo(null); });

        return () => { cancelled = true; };
    }, [stock.symbol]);

    // News about this company and its average sentiment.
    const [news, setNews] = useState(null);         // null while in flight
    const [sentiment, setSentiment] = useState(null);
    useEffect(() => {
        let cancelled = false;
        setNews(null);
        setSentiment(null);
        const sym = encodeURIComponent(stock.symbol);
        Promise.allSettled([
            api.get(`/stocks/news/${sym}`, { params: { limit: 5 } }),
            api.get(`/stocks/sentiment/${sym}`),
        ]).then(([n, snt]) => {
            if (cancelled) return;
            setNews(n.status === 'fulfilled' ? n.value.data : []);
            setSentiment(snt.status === 'fulfilled' ? snt.value.data : null);
        });
        return () => { cancelled = true; };
    }, [stock.symbol]);

    const askAssistant = () => navigation.navigate('AIChat', {
        prompt: t('detail_ask_prompt').replace('{symbol}', stock.symbol.split('.')[0]),
    });

    const points = history?.points ?? [];
    const closes = points.map(p => Number(p.close)).filter(Number.isFinite);

    // The high over the recorded closes, labelled with its real span.
    const seriesHigh = closes.length ? Math.max(...closes) : null;

    const stats = buildStats(info, t);

    // react-native-chart-kit draws every label it is handed, so roughly five are
    // kept, always including the last.
    const labelStep = Math.max(1, Math.ceil(points.length / 5));
    const chartData = {
        labels: points.map((p, i) =>
            (i % labelStep === 0 || i === points.length - 1) ? shortDate(p.trade_date) : ''),
        datasets: [{
            data: closes,
            color: (opacity = 1) => `rgba(15, 17, 21, ${opacity})`,
            strokeWidth: 2.5,
        }],
    };

    // The bell opens the real rule form for this symbol.
    const openAlertForm = () => navigation.navigate('Rules', { symbol: stock.symbol });

    // Start from the real watchlist, so a starred stock opens starred.
    useEffect(() => {
        let cancelled = false;
        watchlistApi.list()
            .then(items => {
                if (!cancelled && (items || []).some(i => i.symbol === stock.symbol)) setWatchState('added');
            })
            .catch(() => {});
        return () => { cancelled = true; };
    }, [stock.symbol]);

    const addToWatchlist = async () => {
        if (watchState === 'saving') return;
        if (watchState === 'added') {
            // The star is a toggle: tapping it again un-stars the symbol.
            setWatchState('saving');
            try {
                await watchlistApi.remove(stock.symbol);
                setWatchState('idle');
                toast(t('toast_watch_removed').replace('{symbol}', stock.symbol), 'info');
            } catch (err) {
                setWatchState('added');
                toast(t('detail_check_connection'), 'error');
            }
            return;
        }
        setWatchState('saving');
        try {
            await watchlistApi.add(stock.symbol);
            setWatchState('added');
            toast(t('toast_watch_added').replace('{symbol}', stock.symbol));
        } catch (err) {
            setWatchState('idle');
            const detail = err?.response?.data?.detail;
            toast(typeof detail === 'string' ? detail : t('detail_check_connection'), 'error');
        }
    };

    const chartConfig = {
        backgroundColor: 'transparent',
        backgroundGradientFrom: '#FFFFFF',
        backgroundGradientFromOpacity: 0,
        backgroundGradientTo: '#FFFFFF',
        backgroundGradientToOpacity: 0,
        decimalPlaces: 1,
        color: (opacity = 1) => `rgba(15, 17, 21, ${opacity})`,
        labelColor: () => palette.muted,
        propsForLabels: { fontFamily: fonts.regular, fontSize: 11 },
        // Dots only on short series; at 1Y they merge into a solid band.
        propsForDots: points.length > 40
            ? { r: '0' }
            : { r: '3.5', strokeWidth: '2', stroke: '#FFFFFF' },
    };

    // The price and change arrive as navigation params; the change is a
    // formatted string ("1.23%" or "—"), so it is read back as a number.
    const pct = parseFloat(stock.change);

    const low = closes.length ? Math.min(...closes) : null;
    const lastClose = closes.length ? closes[closes.length - 1] : null;
    const knob = closes.length >= 2 && seriesHigh > low ? (lastClose - low) / (seriesHigh - low) : 0.5;

    return (
        <Screen>
            <Header
                title={stock.symbol}
                onBack={() => navigation.goBack()}
                backLabel={t('movers_back')}
                right={(
                    <>
                        <CoinStar
                            on={watchState === 'added'}
                            onPress={addToWatchlist}
                            disabled={watchState === 'saving'}
                            label={t(watchState === 'added' ? 'watchlist_remove' : 'detail_add_to_watchlist').replace('{symbol}', stock.symbol)}
                        />
                        <CircleButton
                            icon="notifications-none"
                            onPress={openAlertForm}
                            label={t('detail_create_alert').replace('{symbol}', stock.symbol)}
                        />
                    </>
                )}
            />

            {/* Price */}
            <View style={{ gap: 10 }}>
                <Label numberOfLines={2}>{stock.name}</Label>
                <BigNumber value={stock.price} prefix="Rs" size={64} />
                <ChangePill pct={Number.isFinite(pct) ? pct : null} />
            </View>

            {/* Key stats. Every value comes from GET /stocks/company/{symbol}; there
                is no P/E because cse.lk publishes no earnings figure. */}
            {info === undefined ? (
                <View style={styles.statsLoading}>
                    <ActivityIndicator color={palette.ink} />
                </View>
            ) : stats.length > 0 ? (
                <>
                    <Card style={styles.statsGrid}>
                        {stats.map(stat => (
                            <View key={stat.label} style={styles.statTile}>
                                <Text style={styles.statLabel}>{stat.label}</Text>
                                <Text style={styles.statValue}>{stat.value}</Text>
                                {stat.hint ? <Text style={styles.statHint}>{stat.hint}</Text> : null}
                            </View>
                        ))}
                        {/* The high over the closes this app recorded, labelled with
                            its real span rather than claiming 52 weeks. */}
                        {seriesHigh !== null && closes.length >= 2 ? (
                            <View style={styles.statTile}>
                                <Text style={styles.statLabel}>{t('detail_high_range').replace('{range}', range)}</Text>
                                <Text style={styles.statValue}>Rs. {seriesHigh.toFixed(2)}</Text>
                                <Text style={styles.statHint}>{t('detail_highest_of').replace('{n}', closes.length)}</Text>
                            </View>
                        ) : null}
                    </Card>

                    {/* Sector from the normalised `sector_group`, not the raw feed string. */}
                    {(info.sector_group || info.website || info.business_summary) ? (
                        <Card style={{ gap: 14 }}>
                            {info.sector_group ? (
                                <View style={styles.profileRow}>
                                    <Text style={styles.statLabel}>{t('detail_sector')}</Text>
                                    <Text style={styles.profileValue}>{info.sector_group}</Text>
                                </View>
                            ) : null}
                            {info.established ? (
                                <View style={styles.profileRow}>
                                    <Text style={styles.statLabel}>{t('detail_established')}</Text>
                                    <Text style={styles.profileValue}>{info.established}</Text>
                                </View>
                            ) : null}
                            {info.isin ? (
                                <View style={styles.profileRow}>
                                    <Text style={styles.statLabel}>ISIN</Text>
                                    <Text style={styles.profileValue}>{info.isin}</Text>
                                </View>
                            ) : null}
                            {info.business_summary ? <Body style={styles.summary}>{info.business_summary}</Body> : null}
                            {/* The backend guarantees a scheme on this value. */}
                            {info.website ? (
                                <TouchableTick
                                    onPress={() => Linking.openURL(info.website)}
                                    style={styles.websiteRow}
                                    accessibilityRole="link"
                                    accessibilityLabel={t('detail_open_website')}
                                >
                                    <MaterialIcons name="language" size={18} color={palette.ink} />
                                    <Text style={styles.websiteText} numberOfLines={1}>
                                        {info.website.replace(/^https?:\/\//, '')}
                                    </Text>
                                </TouchableTick>
                            ) : null}
                        </Card>
                    ) : null}
                </>
            ) : (
                // A profile with every field null, or no profile at all: said plainly.
                <EmptyState icon="info-outline" message={t('detail_no_fundamentals').replace('{symbol}', stock.symbol)} />
            )}

            {/* Closing-price chart */}
            <Card style={{ gap: 14 }}>
                <View style={styles.rowBetween}>
                    <Label>{t('detail_closing_price')}</Label>
                    {/* The point count, stated rather than inferred from the axis:
                        a 1M request can legitimately return four points. */}
                    {history !== null && (
                        <Label>
                            {points.length === 0
                                ? t('detail_no_data')
                                : t(points.length === 1 ? 'detail_trading_day' : 'detail_trading_days').replace('{n}', points.length)}
                        </Label>
                    )}
                </View>

                <View style={styles.rangeRow}>
                    {RANGES.map(option => (
                        <Chip key={option} label={option} selected={option === range} onPress={() => setRange(option)} />
                    ))}
                </View>

                {historyError !== null ? (
                    <View style={styles.chartPlaceholder}>
                        <MaterialIcons name="cloud-off" size={26} color={palette.muted} />
                        <Label style={styles.centred}>
                            {historyError === 'HISTORY_ERROR' ? t('detail_history_error') : historyError}
                        </Label>
                    </View>
                ) : history === null || !settled ? (
                    <View style={styles.chartPlaceholder}>
                        <ActivityIndicator color={palette.ink} />
                    </View>
                ) : closes.length >= 2 ? (
                    <>
                        {/* Not `bezier`: a spline overshoots between real closes and
                            draws prices the exchange never printed. */}
                        {/* pointerEvents none: chart-kit makes every point a touch
                            target, which on Android grabs the finger and stops the page
                            scrolling over the chart. The chart has no tap action. */}
                        <View pointerEvents="none">
                            <LineChart
                                data={chartData}
                                width={width - 80}
                                height={200}
                                chartConfig={chartConfig}
                                style={styles.chart}
                                withDots={points.length <= 40}
                                withHorizontalLines={false}
                                withVerticalLines={false}
                                withShadow={false}
                            />
                        </View>
                        <Label style={styles.centred}>
                            {shortDate(history.first_date)} – {shortDate(history.last_date)} · {t('detail_daily_closes')}
                        </Label>
                    </>
                ) : closes.length === 1 ? (
                    <View style={styles.chartPlaceholder}>
                        <BigNumber value={closes[0]} prefix="Rs" size={36} />
                        <Label style={styles.centred}>
                            {t('detail_one_close').replace('{date}', shortDate(points[0].trade_date))}
                        </Label>
                    </View>
                ) : (
                    <View style={styles.chartPlaceholder}>
                        <MaterialIcons name="show-chart" size={26} color={palette.muted} />
                        <Label style={styles.centred}>{t('detail_no_closes').replace('{symbol}', stock.symbol)}</Label>
                    </View>
                )}
            </Card>

            {/* Range over the window on screen: arithmetic over the closes on the
                chart, each number checkable against the line above. The knob marks
                the latest close between the lowest and highest. */}
            {closes.length >= 2 ? (
                <Card style={{ gap: 14 }}>
                    <View style={styles.rowBetween}>
                        <Label style={{ flex: 1 }}>
                            {t(closes.length === 1 ? 'detail_range_over_day' : 'detail_range_over_days').replace('{n}', closes.length)}
                        </Label>
                        <ChangePill pct={((lastClose - closes[0]) / closes[0]) * 100} />
                    </View>
                    <View style={styles.track} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
                        <View style={[styles.knob, { left: `${Math.min(Math.max(knob, 0), 1) * 100}%` }]} />
                    </View>
                    <View style={styles.rowBetween}>
                        <View>
                            <Text style={styles.statLabel}>{t('detail_lowest_close')}</Text>
                            <Text style={styles.statValue}>Rs. {low.toFixed(2)}</Text>
                        </View>
                        <View style={{ alignItems: 'flex-end' }}>
                            <Text style={styles.statLabel}>{t('detail_highest_close')}</Text>
                            <Text style={styles.statValue}>Rs. {seriesHigh.toFixed(2)}</Text>
                        </View>
                    </View>
                </Card>
            ) : null}

            {/* News */}
            <Card tone="lavender" style={{ gap: 6 }}>
                <View style={[styles.rowBetween, { marginBottom: 6 }]}>
                    <Text style={[styles.statLabel, styles.onLavender]}>{t('detail_recent_news')}</Text>
                    {sentiment && sentiment.label !== 'none' ? (
                        <Chip
                            tone={sentimentTone(sentiment.avg_score)}
                            label={`${capitalise(sentiment.label)} ${t('detail_tone')} · ${t(sentiment.count === 1 ? 'detail_article' : 'detail_articles').replace('{n}', sentiment.count)}`}
                        />
                    ) : null}
                </View>
                {news === null ? (
                    <ActivityIndicator size="small" color={palette.lavenderInk} />
                ) : news.length === 0 ? (
                    <Body style={styles.onLavender}>{t('detail_no_news')}</Body>
                ) : news.map((item, i) => (
                    <TouchableTick
                        key={item.news_id}
                        onPress={() => item.url && Linking.openURL(item.url).catch(() => {})}
                        style={[styles.newsRow, i > 0 && styles.newsDivider]}
                        accessibilityLabel={t('detail_read_headline').replace('{headline}', item.headline)}
                    >
                        <Text style={styles.newsHeadline} numberOfLines={2}>{item.headline}</Text>
                        {item.summary ? (
                            <Text style={[styles.newsSummary, styles.onLavender]} numberOfLines={3}>{item.summary}</Text>
                        ) : null}
                        <Text style={[styles.newsMeta, styles.onLavender]}>
                            {[item.source,
                              item.published_at ? new Date(item.published_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : null,
                              item.sentiment_label]
                              .filter(Boolean).join(' · ')}
                        </Text>
                    </TouchableTick>
                ))}
            </Card>

            {/* The one primary action, inside the scroll so the floating tab bar
                never covers it. */}
            <PillButton
                icon="auto-awesome"
                title={t('detail_ask_assistant')}
                label={t('detail_ask_about').replace('{symbol}', stock.symbol)}
                onPress={askAssistant}
            />

        </Screen>
    );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
    rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
    rangeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
    // Same height as the chart it stands in for, so switching range does not jump.
    chartPlaceholder: { height: 200, alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 16 },
    centred: { textAlign: 'center' },
    chart: { marginLeft: -12 },
    statsGrid: { flexDirection: 'row', flexWrap: 'wrap', rowGap: 18, columnGap: 12 },
    statTile: { width: (width - 40 - 40 - 12) / 2, gap: 3 },
    statLabel: { ...text, fontFamily: fonts.medium, fontSize: 11, letterSpacing: 0.6, color: palette.muted },
    statValue: { ...text, fontFamily: fonts.medium, fontSize: 17, fontVariant: ['tabular-nums'] },
    // The units a number is in ("vs All Share Index", "of total market cap").
    statHint: { ...text, fontSize: 11, color: palette.faint },
    // Same height as the grid it stands in for, so the page does not jump.
    statsLoading: { height: 96, alignItems: 'center', justifyContent: 'center' },
    profileRow: { gap: 3 },
    profileValue: { ...text, fontFamily: fonts.medium, fontSize: 15 },
    summary: { fontSize: 14, lineHeight: 21, color: palette.muted },
    websiteRow: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 44 },
    websiteText: { ...text, fontFamily: fonts.medium, fontSize: 14, textDecorationLine: 'underline', flexShrink: 1 },
    track: { height: 10, borderRadius: radii.full, backgroundColor: '#EEF0F5', justifyContent: 'center', marginHorizontal: 9 },
    knob: {
        position: 'absolute', width: 18, height: 18, marginLeft: -9,
        borderRadius: radii.full, backgroundColor: palette.ink,
    },
    onLavender: { color: palette.lavenderInk },
    newsRow: { paddingVertical: 12, gap: 4, minHeight: 44 },
    newsDivider: { borderTopWidth: 1, borderTopColor: 'rgba(59,44,87,0.15)' },
    newsHeadline: { ...text, fontFamily: fonts.medium, fontSize: 15, lineHeight: 20, color: palette.lavenderInk },
    newsSummary: { ...text, fontSize: 14, lineHeight: 20 },
    newsMeta: { ...text, fontSize: 12, textTransform: 'capitalize' },
});
