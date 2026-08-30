import TouchableTick from '../components/TouchableTick';
// src/screens/StockDetailScreen.js
import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    SafeAreaView,
    StatusBar,
    Dimensions,
    Platform,
    ActivityIndicator,
    Linking
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';
import AppHeader from '../components/AppHeader';
import AppCard from '../components/AppCard';
import ActionFeedbackModal from '../components/ActionFeedbackModal';
import { LineChart } from 'react-native-chart-kit';
import api from '../api/axiosConfig';

const { width } = Dimensions.get('window');

// The windows GET /stocks/history/{symbol} accepts, in the order the backend
// declares them. Listed here rather than free-typed so the screen cannot ask for a
// range the endpoint answers 422 for.
const RANGES = ['1W', '1M', '3M', '6M', '1Y', 'ALL'];

const shortDate = (iso) => {
    const parsed = new Date(`${iso}T00:00:00`);
    return Number.isNaN(parsed.getTime())
        ? String(iso ?? '')
        : parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
};

// Market cap in the units a Sri Lankan reader uses. The old tile printed
// `(10 + (price % 50) * 2.5).toFixed(1) + 'B'` — a number under 135 with a "B"
// glued on, so every company on the exchange appeared to be worth between 10 and
// 135 billion of an unnamed currency. Dialog Axiata is Rs. 428.7B and Ceylon Tea
// Brokers is Rs. 0.4B; that three-order-of-magnitude spread is the information the
// suffix has to carry.
const formatMarketCap = (value) => {
    if (!Number.isFinite(value) || value <= 0) return null;
    if (value >= 1e12) return `Rs. ${(value / 1e12).toFixed(2)}T`;
    if (value >= 1e9) return `Rs. ${(value / 1e9).toFixed(1)}B`;
    if (value >= 1e6) return `Rs. ${(value / 1e6).toFixed(1)}M`;
    return `Rs. ${value.toFixed(0)}`;
};

// Shares issued runs to 1.77e10 for JKH, which is why the backend column is a
// BigInteger. Grouped rather than abbreviated: a share count is a countable
// quantity and rounding it to "17.7B" loses the thing it is useful for.
const formatShares = (value) =>
    Number.isFinite(value) && value > 0 ? value.toLocaleString('en-US') : null;

// A tile renders only when there is something real to put in it. The alternative —
// an em dash, or the string "N/A" — was considered and rejected: 60 of 291 symbols
// have no website and three unit trusts have no sector or market cap, so a fixed
// grid would show a wall of placeholders and teach the reader to stop looking. An
// absent tile says "the exchange does not publish this" more clearly than a present
// one containing nothing.
const buildStats = (info) => {
    if (!info) return [];
    return [
        { label: 'MARKET CAP', value: formatMarketCap(info.market_cap) },
        {
            label: '52W LOW',
            // The exchange's own 12-month low. There is deliberately no matching
            // high: cse.lk's p12HiPrice is not restated after a forward split, so
            // 26 symbols publish a 12-month high more than 5x their current
            // price — MERC reads 10,999.00 while trading at 23.00. The low cannot
            // be inflated the same way, which is why one is shown and not the other.
            value: Number.isFinite(info.week52_low)
                ? `Rs. ${info.week52_low.toFixed(2)}` : null,
            // The bound is recomputed between sessions, not intraday, so a stock
            // printing a new low today sits just under it — 9 of 289 symbols did on
            // 2026-08-28, CDB by 6.4%. Without this line the tile looks like it
            // contradicts the price directly above it. Naming the as-of is the
            // honest fix; clamping the number to the live price would invent a
            // bound the exchange never published.
            hint: 'exchange figure, as of the previous close',
        },
        {
            label: 'BETA vs ASI',
            // Zero and negative are real readings here, so the guard is
            // Number.isFinite rather than a truthiness test — `beta_asi: 0` means
            // the security does not track the index, and `> 0` would hide it.
            value: Number.isFinite(info.beta_asi) ? info.beta_asi.toFixed(2) : null,
            hint: info.beta_period ? `CSE, ${info.beta_period}` : 'vs All Share Index',
        },
        { label: 'SHARES ISSUED', value: formatShares(info.shares_issued) },
        {
            label: 'MARKET WEIGHT',
            value: Number.isFinite(info.market_cap_pct)
                ? `${info.market_cap_pct.toFixed(2)}%` : null,
            hint: 'of total market cap',
        },
        { label: 'BOARD', value: info.board },
    ].filter(stat => stat.value !== null && stat.value !== undefined);
};

export default function StockDetailScreen({ route, navigation }) {
    const theme = useAppTheme();
    const { stock } = route.params || { stock: { symbol: 'HNB', name: 'HNB Bank PLC', price: '164.50', change: '+2.45%', isPositive: true } };
    const [showFeedback, setShowFeedback] = useState(false);
    const [feedbackConfig, setFeedbackConfig] = useState({});

    // The real daily-close series from GET /stocks/history/{symbol}. This replaces
    // generateMockChartData(), which walked six points away from the current price
    // with Math.random() and labelled the axis "9AM 11AM 1PM 3PM 5PM Now" — an
    // intraday chart the app never had the data to draw, regenerated on every mount
    // so the same stock showed a different past each time it was opened.
    const [range, setRange] = useState('1M');
    const [history, setHistory] = useState(null);      // null while in flight
    const [historyError, setHistoryError] = useState(null);

    // Fundamentals from GET /stocks/company/{symbol}, replacing four values that
    // were modulus arithmetic on the live price. `undefined` while in flight, `null`
    // when the exchange has no profile for this symbol — two states the render has
    // to tell apart, since one is temporary and the other is permanent.
    const [info, setInfo] = useState(undefined);

    useEffect(() => {
        // Guards against a slower earlier response landing after a newer one. Both
        // dependencies can change without the screen unmounting: the range on every
        // chip tap, and the symbol when navigating from one detail screen to
        // another.
        let cancelled = false;
        setHistory(null);
        setHistoryError(null);

        api.get(`/stocks/history/${encodeURIComponent(stock.symbol)}`, { params: { range } })
            .then(({ data }) => { if (!cancelled) setHistory(data); })
            .catch(err => {
                if (!cancelled) {
                    setHistoryError(err.response?.data?.detail
                        || err.message
                        || 'Could not load price history');
                }
            });

        return () => { cancelled = true; };
    }, [stock.symbol, range]);

    useEffect(() => {
        // Separate from the history effect because it does not depend on `range`.
        // Folding the two together would refetch a company profile that cannot have
        // changed every time the user taps 1W.
        let cancelled = false;
        setInfo(undefined);

        api.get(`/stocks/company/${encodeURIComponent(stock.symbol)}`)
            .then(({ data }) => { if (!cancelled) setInfo(data); })
            // A 404 is the documented answer for a symbol the exchange has no
            // profile for, and it is not an error worth showing. Anything else is
            // also treated as "no fundamentals" rather than blocking the price
            // chart, which is the part of the screen that still works.
            .catch(() => { if (!cancelled) setInfo(null); });

        return () => { cancelled = true; };
    }, [stock.symbol]);

    const points = history?.points ?? [];
    const closes = points.map(p => Number(p.close)).filter(Number.isFinite);

    // The 52-week high the old screen faked, computed from the closes the pipeline
    // actually recorded. Split-consistent by construction, unlike the exchange's
    // p12HiPrice, and honest about its window: the label says how many days it
    // covers rather than claiming a year the series may not yet span.
    const seriesHigh = closes.length ? Math.max(...closes) : null;

    const stats = buildStats(info);

    // react-native-chart-kit draws every label it is handed, so a month of daily
    // points would overlap into an unreadable smear. Roughly five are kept, always
    // including the last.
    const labelStep = Math.max(1, Math.ceil(points.length / 5));
    const chartData = {
        labels: points.map((p, i) =>
            (i % labelStep === 0 || i === points.length - 1) ? shortDate(p.trade_date) : ''),
        datasets: [{
            data: closes,
            color: (opacity = 1) => stock.isPositive
                ? `rgba(16, 185, 129, ${opacity})`
                : `rgba(244, 63, 94, ${opacity})`,
            strokeWidth: 3
        }]
    };

    const handleAction = (type) => {
        if (type === 'buy') {
            setFeedbackConfig({
                title: "Order Placed",
                message: `Successfully submitted buy order for ${stock.symbol} at Rs. ${stock.price}.`,
                type: "success"
            });
        } else {
            setFeedbackConfig({
                title: "Alert Set",
                message: `You will be notified when ${stock.symbol} hits your target price.`,
                type: "info"
            });
        }
        setShowFeedback(true);
    };

    const chartConfig = {
        backgroundColor: "transparent",
        backgroundGradientFrom: theme.colors.surface,
        backgroundGradientTo: theme.colors.surface,
        decimalPlaces: 1,
        color: (opacity = 1) => stock.isPositive ? '#10B981' : '#F43F5E',
        labelColor: (opacity = 1) => theme.colors.textSecondary,
        style: { borderRadius: 16 },
        // Dots only on short series. At 1Y a daily close series is ~250 points and
        // r=4 dots merge into a solid band that hides the line they mark.
        propsForDots: points.length > 40
            ? { r: "0" }
            : { r: "4", strokeWidth: "2", stroke: theme.colors.surface }
    };

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]}>
            <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />
            <AppHeader 
                title={stock.symbol} 
                onBack={() => navigation.goBack()}
                rightAction={
                    <TouchableTick onPress={() => handleAction('alert')}>
                        <MaterialIcons name="notifications-none" size={24} color={theme.colors.textPrimary} />
                    </TouchableTick>
                }
            />

            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
                {/* Price Header */}
                <View style={styles.priceHeader}>
                    <View>
                        <Text style={[styles.stockName, { color: theme.colors.textSecondary }]}>{stock.name}</Text>
                        <Text style={[styles.priceText, { color: theme.colors.textPrimary }]}>Rs. {stock.price}</Text>
                    </View>
                    <View style={[styles.changeBadge, { backgroundColor: stock.isPositive ? '#DCFCE7' : '#FEE2E2' }]}>
                        <Text style={[styles.changeText, { color: stock.isPositive ? '#15803D' : '#B91C1C' }]}>{stock.change}</Text>
                    </View>
                </View>

                {/* Chart Section */}
                <AppCard style={styles.chartCard}>
                    <View style={styles.chartHeader}>
                        <Text style={[styles.sectionLabel, { color: theme.colors.textSecondary }]}>CLOSING PRICE</Text>
                        {/* The point count, stated rather than left to be inferred
                            from the axis. This series begins on the day the pipeline
                            started recording, so a 1M request can legitimately
                            return four points — and four points stretched across an
                            axis the user reads as "a month" is the same misreading
                            the old chart invited, arrived at with real data. */}
                        {history !== null && (
                            <Text style={[styles.chartMeta, { color: theme.colors.textSecondary }]}>
                                {points.length === 0
                                    ? 'no data'
                                    : `${points.length} trading ${points.length === 1 ? 'day' : 'days'}`}
                            </Text>
                        )}
                    </View>

                    <View style={styles.rangeRow}>
                        {RANGES.map(option => (
                            <TouchableTick
                                key={option}
                                onPress={() => setRange(option)}
                                style={[
                                    styles.rangeChip,
                                    { borderColor: theme.colors.divider },
                                    option === range && { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary }
                                ]}
                            >
                                <Text style={[
                                    styles.rangeChipText,
                                    { color: option === range ? '#FFFFFF' : theme.colors.textSecondary }
                                ]}>{option}</Text>
                            </TouchableTick>
                        ))}
                    </View>

                    {historyError !== null ? (
                        <View style={styles.chartPlaceholder}>
                            <MaterialIcons name="cloud-off" size={26} color={theme.colors.textSecondary} />
                            <Text style={[styles.chartPlaceholderText, { color: theme.colors.textSecondary }]}>
                                {historyError}
                            </Text>
                        </View>
                    ) : history === null ? (
                        <View style={styles.chartPlaceholder}>
                            <ActivityIndicator color={theme.colors.primary} />
                        </View>
                    ) : closes.length >= 2 ? (
                        <>
                            {/* Not `bezier`. A spline through real closes overshoots
                                between them, so the curve dips below the session's
                                actual low and rises above its high — drawing prices
                                the exchange never printed, which is the whole thing
                                this screen stopped doing. Straight segments join
                                only points that happened. */}
                            <LineChart
                                data={chartData}
                                width={width - 56}
                                height={200}
                                chartConfig={chartConfig}
                                style={styles.chart}
                                withHorizontalLines={false}
                                withVerticalLines={false}
                            />
                            <Text style={[styles.chartFootnote, { color: theme.colors.textSecondary }]}>
                                {shortDate(history.first_date)} – {shortDate(history.last_date)} · daily closes from the CSE
                            </Text>
                        </>
                    ) : closes.length === 1 ? (
                        <View style={styles.chartPlaceholder}>
                            <Text style={[styles.singleClose, { color: theme.colors.textPrimary }]}>
                                Rs. {closes[0].toFixed(2)}
                            </Text>
                            <Text style={[styles.chartPlaceholderText, { color: theme.colors.textSecondary }]}>
                                One close recorded, on {shortDate(points[0].trade_date)}. A second
                                trading day is needed before a line means anything.
                            </Text>
                        </View>
                    ) : (
                        <View style={styles.chartPlaceholder}>
                            <MaterialIcons name="show-chart" size={26} color={theme.colors.textSecondary} />
                            <Text style={[styles.chartPlaceholderText, { color: theme.colors.textSecondary }]}>
                                No closes recorded for {stock.symbol} in this window yet.
                            </Text>
                        </View>
                    )}
                </AppCard>

                {/* Key Stats. Every value here comes from
                    GET /stocks/company/{symbol}, which reads cse.lk's
                    companyInfoSummery and companyProfile. Four of these tiles used
                    to be arithmetic on the live price:

                      peRatio   = 8 + (price % 15)
                      high52    = price * (1 + (price % 30) / 100)
                      low52     = price * (1 - (price % 25) / 100)
                      marketCap = 10 + (price % 50) * 2.5   rendered with a "B"

                    The modulus was the tell — two stocks at the same price had
                    identical fundamentals, and a price crossing a multiple of 15
                    made the "P/E" jump.

                    There is no P/E tile now. cse.lk publishes no EPS and no
                    earnings figure anywhere in either payload (all 94 keys were
                    walked), so a real P/E cannot be computed from this source at
                    all. An empty tile labelled "P/E RATIO" would still be a claim
                    that the app knows something about earnings, so the tile is
                    gone rather than blank. */}
                {info === undefined ? (
                    <View style={styles.statsLoading}>
                        <ActivityIndicator color={theme.colors.primary} />
                    </View>
                ) : stats.length > 0 ? (
                    <>
                        <View style={styles.statsGrid}>
                            {stats.map(stat => (
                                <AppCard key={stat.label} style={styles.statBox}>
                                    <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>
                                        {stat.label}
                                    </Text>
                                    <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>
                                        {stat.value}
                                    </Text>
                                    {stat.hint ? (
                                        <Text style={[styles.statHint, { color: theme.colors.textSecondary }]}>
                                            {stat.hint}
                                        </Text>
                                    ) : null}
                                </AppCard>
                            ))}
                            {/* The 52-week high, from the closes this app recorded
                                rather than from the exchange's p12HiPrice. Labelled
                                with its real span, because the series starts on the
                                day the pipeline started and calling four weeks of it
                                a "52W HIGH" would be the old screen's mistake made
                                with real numbers. */}
                            {seriesHigh !== null && closes.length >= 2 ? (
                                <AppCard style={styles.statBox}>
                                    <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>
                                        HIGH ({range})
                                    </Text>
                                    <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>
                                        Rs. {seriesHigh.toFixed(2)}
                                    </Text>
                                    <Text style={[styles.statHint, { color: theme.colors.textSecondary }]}>
                                        highest of {closes.length} closes
                                    </Text>
                                </AppCard>
                            ) : null}
                        </View>

                        {/* Sector, from the normalised `sector_group` rather than the
                            raw feed string. cse.lk files 39 distinct sector strings
                            for the exchange's own 20 industry-group indices — "Food
                            Beverage & Tobacco", "FOOD BEVERAGE & TOBACCO" and
                            "Food, Beverage & Tobacco" are one sector typed three
                            ways — so the raw string is not what a reader should see
                            or a filter should use. Null for six symbols, and absent
                            rather than guessed for them. */}
                        {(info.sector_group || info.website || info.business_summary) ? (
                            <AppCard style={styles.profileCard}>
                                {info.sector_group ? (
                                    <View style={styles.profileRow}>
                                        <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>SECTOR</Text>
                                        <Text style={[styles.profileValue, { color: theme.colors.textPrimary }]}>
                                            {info.sector_group}
                                        </Text>
                                    </View>
                                ) : null}
                                {info.established ? (
                                    <View style={styles.profileRow}>
                                        <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>ESTABLISHED</Text>
                                        <Text style={[styles.profileValue, { color: theme.colors.textPrimary }]}>
                                            {info.established}
                                        </Text>
                                    </View>
                                ) : null}
                                {info.isin ? (
                                    <View style={styles.profileRow}>
                                        <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>ISIN</Text>
                                        <Text style={[styles.profileValue, { color: theme.colors.textPrimary }]}>
                                            {info.isin}
                                        </Text>
                                    </View>
                                ) : null}
                                {info.business_summary ? (
                                    <Text style={[styles.summaryText, { color: theme.colors.textPrimary }]}>
                                        {info.business_summary}
                                    </Text>
                                ) : null}
                                {/* The backend guarantees a scheme on this value.
                                    Linking.openURL fails silently on Android for a
                                    scheme-less URL, and two of the three spellings
                                    cse.lk files ("www.keells.com", "cal.lk") are
                                    scheme-less — so the fix lives at the boundary
                                    rather than being repeated at each call site. */}
                                {info.website ? (
                                    <TouchableTick
                                        onPress={() => Linking.openURL(info.website)}
                                        style={styles.websiteRow}
                                    >
                                        <MaterialIcons name="language" size={16} color={theme.colors.primary} />
                                        <Text style={[styles.websiteText, { color: theme.colors.primary }]}>
                                            {info.website.replace(/^https?:\/\//, '')}
                                        </Text>
                                    </TouchableTick>
                                ) : null}
                            </AppCard>
                        ) : null}
                    </>
                ) : (
                    /* Reached when the symbol has a profile row but every field a
                       tile reads is null, and when there is no profile at all. Both
                       are real: the three CAL unit trusts have no sector, no market
                       cap and no beta. Saying so is the honest version of what the
                       old screen answered with six fabricated numbers. */
                    <AppCard style={styles.statsEmpty}>
                        <MaterialIcons name="info-outline" size={20} color={theme.colors.textSecondary} />
                        <Text style={[styles.chartPlaceholderText, { color: theme.colors.textSecondary }]}>
                            The CSE publishes no company fundamentals for {stock.symbol}.
                        </Text>
                    </AppCard>
                )}

                {/* Price range over the window on screen.

                    This replaces a card headed "AI Analysis" whose entire body was
                    one hardcoded sentence: "{symbol} shows strong support at
                    Rs. {price * 0.95}. RSI indicates neutral momentum. Consider
                    averaging in if it dips towards the support level." Nothing in
                    the app computes an RSI or a support level, so all three clauses
                    were assertions with no source — and the last one was investment
                    advice generated by multiplying the price by 0.95.

                    What replaces it is arithmetic over the closes already on the
                    chart, labelled with the window it covers. Less impressive and
                    entirely checkable: a reader can verify every number here against
                    the line above it. The screen's real AI surface is the chat
                    assistant, which answers from this same data rather than from a
                    template. */}
                {closes.length >= 2 ? (
                    <AppCard style={styles.rangeCard}>
                        <Text style={[styles.sectionLabel, { color: theme.colors.textSecondary }]}>
                            RANGE OVER {closes.length} TRADING {closes.length === 1 ? 'DAY' : 'DAYS'}
                        </Text>
                        <View style={styles.rangeStatsRow}>
                            <View>
                                <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>LOWEST CLOSE</Text>
                                <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>
                                    Rs. {Math.min(...closes).toFixed(2)}
                                </Text>
                            </View>
                            <View>
                                <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>HIGHEST CLOSE</Text>
                                <Text style={[styles.statValue, { color: theme.colors.textPrimary }]}>
                                    Rs. {Math.max(...closes).toFixed(2)}
                                </Text>
                            </View>
                            <View>
                                <Text style={[styles.statLabel, { color: theme.colors.textSecondary }]}>CHANGE</Text>
                                <Text style={[styles.statValue, {
                                    color: closes[closes.length - 1] >= closes[0] ? '#15803D' : '#B91C1C'
                                }]}>
                                    {closes[closes.length - 1] >= closes[0] ? '+' : ''}
                                    {(((closes[closes.length - 1] - closes[0]) / closes[0]) * 100).toFixed(2)}%
                                </Text>
                            </View>
                        </View>
                    </AppCard>
                ) : null}
            </ScrollView>

            {/* Action Bar */}
            <View style={[styles.actionBar, { backgroundColor: theme.colors.surface, borderTopColor: theme.colors.divider }]}>
                <TouchableTick style={styles.watchlistBtn}>
                    <MaterialIcons name="star-border" size={24} color={theme.colors.primary} />
                </TouchableTick>
                <TouchableTick 
                    style={[styles.buyBtn, { backgroundColor: theme.colors.primary }]}
                    onPress={() => handleAction('buy')}
                >
                    <Text style={styles.buyBtnText}>Quick Buy</Text>
                </TouchableTick>
            </View>

            <ActionFeedbackModal 
                visible={showFeedback} 
                onClose={() => setShowFeedback(false)}
                title={feedbackConfig.title}
                message={feedbackConfig.message}
                type={feedbackConfig.type}
            />
        </SafeAreaView>
    );
}

// The LinearGradient stand-in that used to live here went with the "AI Analysis"
// card that was its only caller. It was a plain View accepting and ignoring a
// `colors` prop, so the gradient never rendered on any platform.

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    scrollContent: {
        paddingHorizontal: 20,
        paddingBottom: 100,
    },
    priceHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: 20,
        marginBottom: 24,
    },
    stockName: {
        fontSize: 14,
        fontWeight: '600',
        marginBottom: 4,
    },
    priceText: {
        fontSize: 32,
        fontWeight: '800',
        letterSpacing: -1,
    },
    changeBadge: {
        paddingHorizontal: 12,
        paddingVertical: 6,
        borderRadius: 8,
    },
    changeText: {
        fontSize: 15,
        fontWeight: '700',
    },
    chartCard: {
        padding: 16,
        marginBottom: 20,
    },
    chartHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
    chartMeta: {
        fontSize: 11,
        fontWeight: '700',
        letterSpacing: 0.3,
    },
    rangeRow: {
        flexDirection: 'row',
        gap: 6,
        marginBottom: 8,
    },
    rangeChip: {
        flex: 1,
        paddingVertical: 6,
        borderRadius: 8,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    rangeChipText: {
        fontSize: 11,
        fontWeight: '700',
    },
    // Same height as the chart it stands in for, so switching range does not make
    // the page jump while the request is in flight.
    chartPlaceholder: {
        height: 200,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        paddingHorizontal: 16,
    },
    chartPlaceholderText: {
        fontSize: 12,
        lineHeight: 18,
        textAlign: 'center',
    },
    singleClose: {
        fontSize: 26,
        fontWeight: '800',
    },
    chartFootnote: {
        fontSize: 11,
        textAlign: 'center',
        marginTop: 4,
    },
    sectionLabel: {
        fontSize: 12,
        fontWeight: '700',
        letterSpacing: 1,
        marginBottom: 16,
    },
    chart: {
        marginVertical: 8,
        borderRadius: 16,
        marginLeft: -16,
    },
    statsGrid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 12,
        marginBottom: 20,
    },
    statBox: {
        width: (width - 56) / 2, // 2 columns with gap taken into account
        padding: 16,
    },
    statLabel: {
        fontSize: 10,
        fontWeight: '700',
        letterSpacing: 0.5,
        marginBottom: 4,
    },
    statValue: {
        fontSize: 16,
        fontWeight: '800',
    },
    // For the units a number is in ("vs All Share Index", "of total market cap").
    // The tile labels are abbreviations by necessity at this width, and an
    // unqualified "0.20" under "BETA vs ASI" is a number without a meaning.
    statHint: {
        fontSize: 10,
        marginTop: 2,
    },
    // Same height as the two-row grid it stands in for, so the page does not jump
    // when the profile request lands.
    statsLoading: {
        height: 96,
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 20,
    },
    statsEmpty: {
        padding: 20,
        alignItems: 'center',
        gap: 8,
        marginBottom: 20,
    },
    profileCard: {
        padding: 16,
        marginBottom: 20,
        gap: 12,
    },
    profileRow: {
        gap: 2,
    },
    profileValue: {
        fontSize: 14,
        fontWeight: '700',
    },
    summaryText: {
        fontSize: 13,
        lineHeight: 20,
        opacity: 0.9,
    },
    websiteRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
    },
    websiteText: {
        fontSize: 13,
        fontWeight: '700',
    },
    rangeCard: {
        padding: 16,
        marginBottom: 20,
    },
    rangeStatsRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
    },
    actionBar: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: Platform.OS === 'ios' ? 90 : 70,
        flexDirection: 'row',
        paddingHorizontal: 20,
        paddingTop: 12,
        borderTopWidth: 1,
        gap: 12,
    },
    watchlistBtn: {
        width: 50,
        height: 50,
        borderRadius: 12,
        borderWidth: 1.5,
        borderColor: '#E2E8F0',
        justifyContent: 'center',
        alignItems: 'center',
    },
    buyBtn: {
        flex: 1,
        height: 50,
        borderRadius: 12,
        justifyContent: 'center',
        alignItems: 'center',
        shadowColor: '#0052FF',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.2,
        shadowRadius: 8,
        elevation: 10,
    },
    buyBtnText: {
        color: '#FFFFFF',
        fontSize: 16,
        fontWeight: '700',
    }
});
