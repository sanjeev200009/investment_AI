import ActionFeedbackModal from '../components/ActionFeedbackModal';
import TouchableTick from '../components/TouchableTick';
import React, { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar, Dimensions, Animated, PanResponder, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import Svg, { Circle, G } from 'react-native-svg';
import { BlurView } from 'expo-blur';
import { useAuthStore } from '../store/authStore';
import api from '../api/axiosConfig';

const { width } = Dimensions.get('window');

// Tailwind config colors mapping
const colors = {
  background: '#faf9fc',
  onBackground: '#1a1c1e',
  surface: '#faf9fc',
  surfaceVariant: '#e3e2e5',
  onSurfaceVariant: '#43474d',
  primary: '#002743',
  primaryFixed: '#cfe5ff',
  onPrimary: '#ffffff',
  primaryContainer: '#1c3d5a',
  onPrimaryContainer: '#89a8ca',
  error: '#ba1a1a',
  // The stock preview rows already read `colors.success` for a gain; the key was
  // never defined, so every positive change rendered `color: undefined` — the
  // default near-black — while losses were red. Gains were the only readings on the
  // screen with no colour of their own.
  success: '#2E7D32',
  warning: '#F5A623',
  cardShadow: 'rgba(28, 61, 90, 0.06)'
};

// The two chips that are not sectors. Named rather than repeated as string literals
// because the fetch effect, the sort and the banner title all have to agree on them.
const ALL_MARKETS = 'All Markets';
const TOP_MOVERS = 'Top Movers';

// Circumference of the r=45 donut on the ASPI card, for turning a percentage
// share into a strokeDasharray length: 2 * PI * 45.
const DONUT_CIRCUMFERENCE = 2 * Math.PI * 45;

// One colour per sector slice, in the order the backend ranks them by turnover.
// The last is for the "Other sectors" remainder and is deliberately muted — it is
// a rollup of everything unnamed, not a sector in its own right.
const SECTOR_COLOURS = [
  colors.primaryFixed,
  colors.onPrimaryContainer,
  colors.warning,
  'rgba(255, 255, 255, 0.25)',
];

// Flat is its own case, not a default. Colouring a 0.00% move teal would read as
// a gain, and the badge used to be a hardcoded "+1.2%" in teal with an upward
// arrow regardless of which way the index had actually gone.
const TREND_STYLES = {
  up: { icon: 'trending-up', colour: '#2dd4bf', tint: 'rgba(45, 212, 191, 0.15)' },
  down: { icon: 'trending-down', colour: '#f87171', tint: 'rgba(248, 113, 113, 0.15)' },
  flat: { icon: 'trending-flat', colour: 'rgba(255, 255, 255, 0.7)', tint: 'rgba(255, 255, 255, 0.1)' },
};

export default function HomeScreen({ navigation }) {
  const { user, isAuthenticated } = useAuthStore();

  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Derived from the backend's own users row. The old chain ended in a
  // hardcoded 'Sanjeev' / 'PERERA', which is what every user saw once the
  // missing Authorization header made /auth/me fail.
  const nameParts = (user?.full_name || '').trim().split(/\s+/).filter(Boolean);
  const userName = nameParts[0] || 'Investor';
  const lastName = nameParts.slice(1).join(' ');

  // null until a real reading arrives. Was 12000, which the tile rendered as
  // "12,000.00" whenever the index was unavailable — indistinguishable from a
  // genuine quote.
  const [aspiCount, setAspiCount] = useState(null);
  const [showTrendModal, setShowTrendModal] = useState(false);

  const animValues = useRef([...Array(4)].map(() => new Animated.Value(0))).current;
  const floatAnims = useRef([...Array(4)].map(() => new Animated.Value(0))).current;
  const chartAnim = useRef(new Animated.Value(0)).current;

  // AI Insights Swipeable Stack State
  const [insightIndex, setInsightIndex] = useState(0);
  const swipePosition = useRef(new Animated.ValueXY()).current;
  const [activeChip, setActiveChip] = useState(ALL_MARKETS);
  const [allStocks, setAllStocks] = useState([]);
  const [stocksError, setStocksError] = useState(null);

  // The CSE's own 20 industry-group names with live company counts, from
  // GET /stocks/sectors. These replace three chips whose membership was decided by
  // ticker-prefix arrays hardcoded in this file — `['JKH','HAYL','SPEN','AEL',
  // 'RICH','HEMS']` stood in for Capital Goods (6 of its 29 companies), and
  // "Banking" and "Manufacturing" are not CSE sector names at all.
  //
  // Named sectorChips, not sectors: `sectors` further down is the dashboard's
  // turnover breakdown for the donut, which is a different list (top three by
  // turnover plus a remainder) from a different endpoint.
  const [sectorChips, setSectorChips] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const fetchDashboard = async () => {
      try {
        // The Authorization header and ngrok bypass now come from the shared
        // axios instance's request interceptor, so there is no getToken() call
        // and no per-request header block here.
        const res = await api.get('/dashboard/');
        if (!cancelled) setDashboardData(res.data);
      } catch (e) {
        // No substitute payload. This used to install a whole fake dashboard on
        // failure: a Rs. 145,000 portfolio against a Rs. 200,000 target, three
        // invented "AI insights" (one of them announcing WindForce up 12% "following
        // the new policy announcements"), and a three-stock watchlist with prices
        // frozen at whatever they were when the array was typed. A user whose
        // backend was down saw a complete, confident, entirely fictional screen.
        //
        // `aspi` and `sectors` stay empty for the same reason they already did: the
        // hardcoded 12450.80 / +1.2% was out by 71% against the real 21279.65 /
        // -0.31% and pointed the wrong way.
        if (!cancelled) setDashboardData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchDashboard();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.get('/stocks/sectors')
      // A failure here costs the sector chips, not the screen: "All Markets" and
      // "Top Movers" need no sector list.
      .then(({ data }) => { if (!cancelled) setSectorChips(data); })
      .catch(() => { if (!cancelled) setSectorChips([]); })
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    // Refetched per chip, because a sector filter belongs on the server. Filtering
    // a fixed 50-row page client-side meant a sector's members outside that page
    // were unreachable — Insurance has 11 companies and the top-50-by-volume page
    // contained two of them.
    let cancelled = false;
    setStocksError(null);

    const params = { limit: 50 };
    if (activeChip !== ALL_MARKETS && activeChip !== TOP_MOVERS) {
      params.sector = activeChip;
      // The whole sector, not the top 50 by volume, so the preview's six rows are
      // the sector's real leaders.
      params.limit = 400;
    }

    api.get('/stocks/market', { params })
      .then(({ data }) => { if (!cancelled) setAllStocks(data); })
      .catch(err => {
        if (cancelled) return;
        setAllStocks([]);
        setStocksError(err.response?.data?.detail || err.message
          || 'Could not reach the market data service');
      });

    return () => { cancelled = true; };
  }, [activeChip]);

  const AI_INSIGHTS = dashboardData?.insights || [];

  const filteredStocks = React.useMemo(() => {
    // No fallback to watchlist_preview. The two lists answer different questions —
    // this one follows the chip — and blending them meant that whenever the market
    // request came back empty the chip silently stopped applying.
    const sorted = [...allStocks];

    // change_pct and volume are both null for a symbol with no previous close or no
    // trades. `(b.change_pct || 0) - (a.change_pct || 0)` treated those as 0.00%, so
    // an untraded stock outranked every real faller on the "Top Movers" chip.
    const byNumberDesc = (key) => (a, b) => {
      const x = a[key], y = b[key];
      if (!Number.isFinite(x)) return Number.isFinite(y) ? 1 : 0;
      if (!Number.isFinite(y)) return -1;
      return y - x;
    };

    // The "AI Picks" chip is gone. It sorted by `() => 0.5 - Math.random()` and
    // presented the result as a recommendation, which is the most direct form of the
    // fabrication this pass exists to remove: six random tickers under an AI label.
    // Real recommendations come from the assessment-driven engine, which has its own
    // screen and its own stored rationale.
    sorted.sort(byNumberDesc(activeChip === TOP_MOVERS ? 'change_pct' : 'volume'));
    return sorted.slice(0, Math.min(6, sorted.length));
  }, [allStocks, activeChip]);

  const insightsLengthRef = useRef(AI_INSIGHTS.length);
  useEffect(() => {
    insightsLengthRef.current = AI_INSIGHTS.length;
  }, [AI_INSIGHTS]);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,
      onMoveShouldSetPanResponder: (evt, gestureState) => Math.abs(gestureState.dx) > 5,
      onPanResponderMove: (evt, gestureState) => {
        swipePosition.setValue({ x: gestureState.dx, y: 0 });
      },
      onPanResponderRelease: (evt, gestureState) => {
        if (gestureState.dx > 120) {
          Animated.timing(swipePosition, {
            toValue: { x: width + 100, y: 0 },
            duration: 200,
            useNativeDriver: false
          }).start(() => {
            setInsightIndex((prev) => (prev + 1) % (insightsLengthRef.current || 1));
            swipePosition.setValue({ x: 0, y: 0 });
          });
        } else if (gestureState.dx < -120) {
          Animated.timing(swipePosition, {
            toValue: { x: -width - 100, y: 0 },
            duration: 200,
            useNativeDriver: false
          }).start(() => {
            setInsightIndex((prev) => (prev + 1) % (insightsLengthRef.current || 1));
            swipePosition.setValue({ x: 0, y: 0 });
          });
        } else {
          Animated.spring(swipePosition, {
            toValue: { x: 0, y: 0 },
            useNativeDriver: false
          }).start();
        }
      }
    })
  ).current;

  const renderInsightsStack = () => {
    if (!AI_INSIGHTS || AI_INSIGHTS.length === 0) return null;

    // Ensure we always have a positive, valid index
    const safeIndex = Math.abs(insightIndex) % AI_INSIGHTS.length;
    const topItem = AI_INSIGHTS[safeIndex];
    const nextItem = AI_INSIGHTS[(safeIndex + 1) % AI_INSIGHTS.length];

    if (!topItem) return null; // Failsafe

    return (
      <>
        {/* NEXT CARD (Bottom) */}
        {AI_INSIGHTS.length > 1 && nextItem && (
          <Animated.View
            style={[
              styles.aiCard, 
              { position: 'absolute', width: '100%', top: 0 },
              {
                transform: [
                  { translateX: 0 },
                  { translateY: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: [0, 15, 0], extrapolate: 'clamp' }) },
                  { scale: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: [1, 0.95, 1], extrapolate: 'clamp' }) },
                  { rotate: '0deg' }
                ],
                zIndex: 1,
                opacity: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: [1, 0.5, 1], extrapolate: 'clamp' })
              }
            ]}
          >
            <View style={styles.aiHeader}>
              <MaterialIcons name="auto-awesome" size={20} color={colors.primaryFixed} />
              <Text style={styles.aiLabel}>{nextItem?.label || 'INSIGHT'}</Text>
            </View>
            <Text style={styles.aiBody}>{nextItem?.body || 'Loading...'}</Text>
            <TouchableTick style={[styles.aiButton, styles.glassButtonDark]}>
              <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFillObject} />
              <Text style={styles.aiButtonText}>{nextItem?.buttonText || 'View'}</Text>
            </TouchableTick>
          </Animated.View>
        )}

        {/* TOP CARD */}
        <Animated.View
          style={[
            styles.aiCard, 
            { position: 'absolute', width: '100%', top: 0 },
            {
              transform: [
                { translateX: swipePosition.x },
                { translateY: 0 },
                { scale: 1 },
                { rotate: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: ['-5deg', '0deg', '5deg'] }) }
              ],
              zIndex: 99,
              opacity: 1
            }
          ]}
          {...panResponder.panHandlers}
        >
          <View style={styles.aiHeader}>
            <MaterialIcons name="auto-awesome" size={20} color={colors.primaryFixed} />
            <Text style={styles.aiLabel}>{topItem?.label || 'INSIGHT'}</Text>
          </View>
          <Text style={styles.aiBody}>{topItem?.body || 'Loading...'}</Text>
          <TouchableTick style={[styles.aiButton, styles.glassButtonDark]}>
            <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFillObject} />
            <Text style={styles.aiButtonText}>{topItem?.buttonText || 'View'}</Text>
          </TouchableTick>
        </Animated.View>
      </>
    );
  };

  useEffect(() => {
    Animated.spring(chartAnim, {
      toValue: 1,
      friction: 7,
      tension: 40,
      useNativeDriver: false
    }).start();

    Animated.stagger(150, 
      animValues.map(anim => 
        Animated.spring(anim, {
          toValue: 1,
          useNativeDriver: true,
          tension: 50,
          friction: 4,
        })
      )
    ).start();

    floatAnims.forEach((anim, i) => {
      Animated.loop(
        Animated.sequence([
          Animated.timing(anim, {
            toValue: 1,
            duration: 1200,
            delay: i * 200,
            useNativeDriver: true,
          }),
          Animated.timing(anim, {
            toValue: 0,
            duration: 1200,
            useNativeDriver: true,
          })
        ])
      ).start();
    });
  }, []);

  // Counting animation for the ASPI tile.
  //
  // Runs up from a fraction of the target rather than a literal 12000. With the
  // literal the tile counted *down* as soon as the backend started serving the
  // real index (21279 vs the hardcoded 12450), and it would show a wrong order of
  // magnitude on the first frame for any index that is not near 12000 — the
  // industry groups run from 513 to 94679.
  //
  // Also guards on `aspi` being absent, which is what the backend returns before
  // the first index scrape or when it has no reading. The old version read
  // `dashboardData.aspi.value` unconditionally and threw on null.
  useEffect(() => {
    const end = dashboardData?.aspi?.value;
    if (typeof end !== 'number' || !isFinite(end)) {
      setAspiCount(null);
      return;
    }

    const start = end * 0.97;
    const duration = 1500;
    let startTime = null;
    let animationFrame;

    const updateCount = (currentTime) => {
      if (!startTime) startTime = currentTime;
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      const easeOut = 1 - Math.pow(1 - progress, 3);
      const currentVal = start + (end - start) * easeOut;

      setAspiCount(currentVal);

      if (progress < 1) {
        animationFrame = requestAnimationFrame(updateCount);
      }
    };

    animationFrame = requestAnimationFrame(updateCount);
    return () => cancelAnimationFrame(animationFrame);
  }, [dashboardData]);

  // The goal tile's two figures, straight from the payload.
  //
  // These were `dashboardData?.portfolio?.current_value || 145000` and
  // `|| 200000`. `current_value` is 0 for a user who holds nothing, and `0 || x` is
  // x in JavaScript, so the fallback fired on the *success* path for every new user:
  // the bar filled to 72.5% of a Rs. 200,000 goal while the line above it correctly
  // read "Rs. 0 / Rs. 100,000". The tile disagreed with itself.
  const currentVal = Number(dashboardData?.portfolio?.current_value);
  const targetVal = Number(dashboardData?.portfolio?.target_value);
  const hasGoal = Number.isFinite(currentVal) && Number.isFinite(targetVal)
    && targetVal > 0 && currentVal > 0;
  const progressPct = hasGoal
    ? Math.min((currentVal / targetVal) * 100, 100).toFixed(1) + '%'
    : '0%';

  // ASPI tile. `aspi` is null before the first index scrape and whenever the
  // dashboard request fails, so every field below has to tolerate its absence
  // instead of substituting a number.
  const aspi = dashboardData?.aspi || null;
  const aspiChangePct = typeof aspi?.change_pct === 'number' ? aspi.change_pct : null;
  const aspiTrend = TREND_STYLES[
    aspiChangePct === null ? 'flat' : aspiChangePct > 0 ? 'up' : aspiChangePct < 0 ? 'down' : 'flat'
  ];

  // cse.lk keeps serving the last session's close while the market is shut, so
  // the reading can be days old — it was 50 hours old when this was written. The
  // backend sends the exchange's own timestamp for exactly this reason; without
  // surfacing it, a stale close is indistinguishable from a live quote. Shown only
  // when the reading is not from today, so it stays out of the way intraday.
  const aspiAsOf = React.useMemo(() => {
    if (!aspi?.recorded_at) return null;
    const at = new Date(aspi.recorded_at);
    if (isNaN(at.getTime())) return null;
    if (at.toDateString() === new Date().toDateString()) return null;
    return at.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  }, [aspi]);

  // Donut arcs from real turnover shares. These were three fixed strokeDasharray
  // values ("109 282.74", "95 282.74", "66 282.74") matching a hardcoded
  // "Banking 40% / Cap Goods 35% / Food 25%" legend — three slices summing to
  // exactly 100 when the CSE has 20 industry groups. The backend now sends the
  // top three by turnover plus one "Other sectors" remainder, so the shares still
  // add up without any of them being invented.
  const sectors = dashboardData?.sectors || [];
  const sectorArcs = React.useMemo(() => {
    let offset = 0;
    return sectors.map((s, i) => {
      const share = Math.max(Number(s.share_pct) || 0, 0);
      const length = (share / 100) * DONUT_CIRCUMFERENCE;
      const arc = {
        code: s.code,
        name: s.name,
        share,
        colour: SECTOR_COLOURS[i] || SECTOR_COLOURS[SECTOR_COLOURS.length - 1],
        dashArray: `${length} ${DONUT_CIRCUMFERENCE}`,
        dashOffset: -offset,
      };
      offset += length;
      return arc;
    });
  }, [sectors]);
  
  // The real valuation series from GET /dashboard/ — one point per day the
  // snapshot task has run, oldest first, each carrying its own date. This was
  // `weekly_history`, which the backend computed as
  // `current_value × [0.85, 0.82, 0.94, 1.0]`: four numbers derived from the
  // present value, so the tile drew the same 15% dip recovering to exactly today's
  // figure for every user, every day, whatever the portfolio had actually done.
  //
  // There is deliberately no fallback series. The old code substituted
  // [110000, 125000, 130000, 145000] whenever the backend returned zeros — which
  // is the state a new user is permanently in — so the first thing a new user saw
  // was a rising Rs. 145k portfolio they did not own. An empty series now renders
  // an empty state that says so.
  const history = Array.isArray(dashboardData?.portfolio?.history)
    ? dashboardData.portfolio.history.filter(
        p => p && Number.isFinite(Number(p.value)))
    : [];
  const historyDays = dashboardData?.portfolio?.history_days ?? 30;

  // Scaled to the series' own maximum with 10% headroom, so the tallest bar never
  // touches the top gridline.
  const maxValue = Math.max(...history.map(p => Number(p.value)), 1) * 1.1;
  const getH = (val) => (Number(val) / maxValue) * 150;

  // Change across the whole stored window, not a fixed "vs last week" — the window
  // is however many days have been recorded. Null rather than 0 when there is only
  // one point, because "0.0%" would assert the portfolio held steady over a period
  // we have not observed; and null when the first value is zero, which would
  // otherwise divide to Infinity.
  const firstValue = history.length ? Number(history[0].value) : 0;
  const lastValue = history.length ? Number(history[history.length - 1].value) : 0;
  const windowChange = history.length >= 2 && firstValue !== 0
    ? (((lastValue - firstValue) / firstValue) * 100).toFixed(1)
    : null;

  const formatLabel = (val) => val >= 1000 ? `Rs. ${(val / 1000).toFixed(1)}k` : `Rs. ${val.toFixed(0)}`;
  const yLabels = [
    formatLabel(maxValue),
    formatLabel(maxValue * 0.75),
    formatLabel(maxValue * 0.5),
    formatLabel(maxValue * 0.25),
    'Rs. 0'
  ];

  // Only the first and last bars carry a date label: 30 daily labels would overlap
  // into illegibility in a card this wide, and the point count in the header is
  // what actually tells the user how much history exists.
  const dayLabel = (iso) => {
    const parsed = new Date(`${iso}T00:00:00`);
    return Number.isNaN(parsed.getTime())
      ? String(iso ?? '')
      : parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />
      
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Image
            source={{ uri: `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.full_name || 'Investor')}&background=0052FF&color=fff` }}
            style={styles.avatar}
          />
          <Text style={styles.headerTitle}>InvestAI</Text>
        </View>
        <View style={styles.headerRight}>

          <TouchableTick style={[styles.settingsBtn, styles.glassButton]} onPress={() => navigation.navigate('ProfileMain')}>
            <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFillObject} />
            <MaterialIcons name="settings" size={24} color={colors.primary} />
          </TouchableTick>
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        
        {/* Greeting & Notifications */}
        <View style={styles.greetingSection}>
          <View>
            <Text style={styles.greetingText}>Good morning, {userName}</Text>
            <Text style={styles.subtitleText}>Here's your market brief for today.</Text>
          </View>
          <TouchableTick style={[styles.notificationBtn, styles.glassButton]} onPress={() => navigation.navigate('Alerts')}>
            <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFillObject} />
            <MaterialIcons name="notifications-none" size={24} color={colors.onSurfaceVariant} />
            <View style={styles.notificationDot} />
          </TouchableTick>
        </View>

        {/* ASPI Market Overview */}
        <View style={[styles.card, styles.aspiCard, { padding: 20 }]}>
          <LinearGradient
            colors={['#0a2e4a', '#051624']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={StyleSheet.absoluteFillObject}
          />
          <LinearGradient
            colors={['rgba(255, 255, 255, 0.1)', 'transparent']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.cardGlowOverlay}
          />
          
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', zIndex: 1 }}>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 6 }}>
                 <MaterialIcons name="auto-graph" size={16} color="rgba(255, 255, 255, 0.7)" />
                 <Text style={[styles.cardLabelNew, { color: 'rgba(255, 255, 255, 0.7)' }]}>
                   ASPI INDEX{aspiAsOf ? ` · ${aspiAsOf}` : ''}
                 </Text>
              </View>
              
              <Text style={[styles.aspiValueNew, { color: '#ffffff', letterSpacing: 1, fontSize: 32 }]}>
                {aspiCount === null
                  ? '—'
                  : aspiCount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </Text>

              <View style={[styles.aspiChangeBadgeNew, { backgroundColor: aspiTrend.tint, alignSelf: 'flex-start', marginTop: 12 }]}>
                <MaterialIcons name={aspiTrend.icon} size={14} color={aspiTrend.colour} />
                <Text style={[styles.aspiChangeTextNew, { color: aspiTrend.colour }]}>
                  {aspiChangePct === null
                    ? 'No reading'
                    : `${aspiChangePct > 0 ? '+' : ''}${aspiChangePct.toFixed(2)}%`}
                </Text>
              </View>
            </View>

            <View style={{ alignItems: 'flex-end', justifyContent: 'center', marginTop: 4 }}>
                 <Svg height="72" width="72" viewBox="0 0 120 120">
                   <G transform="rotate(-90 60 60)">
                     {sectorArcs.length === 0 ? (
                       <Circle cx="60" cy="60" r="45" stroke="rgba(255,255,255,0.12)" strokeWidth="14" fill="transparent" />
                     ) : sectorArcs.map((arc) => (
                       <Circle
                         key={arc.code}
                         cx="60" cy="60" r="45"
                         stroke={arc.colour}
                         strokeWidth="14"
                         fill="transparent"
                         strokeDasharray={arc.dashArray}
                         strokeDashoffset={arc.dashOffset}
                       />
                     ))}
                   </G>
                 </Svg>
                 <View style={{ position: 'absolute', right: 24, top: 24 }}>
                   <MaterialIcons name="pie-chart" size={24} color="rgba(255,255,255,0.9)" />
                 </View>
            </View>
          </View>

          {/* Turnover share by sector. Two columns rather than one row: the real
              CSE names ("Diversified Financials", "Food & Staples Retailing") do
              not fit four-across, and there are four slices now that the
              remainder is shown rather than three that summed to a tidy 100. */}
          {sectorArcs.length > 0 && (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginTop: 24, zIndex: 1, paddingTop: 16, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.1)' }}>
               {sectorArcs.map((arc) => (
                 <View key={arc.code} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, width: '50%', paddingRight: 8, marginBottom: 6 }}>
                    <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: arc.colour }} />
                    <Text numberOfLines={1} style={{ flex: 1, fontSize: 11, color: 'rgba(255,255,255,0.7)', fontFamily: 'Satoshi-Medium' }}>
                      {arc.name}
                    </Text>
                    <Text style={{ fontSize: 11, color: 'rgba(255,255,255,0.9)', fontFamily: 'Satoshi-Medium' }}>
                      {arc.share.toFixed(0)}%
                    </Text>
                 </View>
               ))}
            </View>
          )}
        </View>

        {/* Core Values / Alignment Icons */}
        {/* Core Values / Alignment Icons */}
        <View style={styles.alignmentRow}>
          {[
            { id: 0, icon: 'psychology', label: 'AI Driven' },
            { id: 1, icon: 'insights', label: 'Insights' },
            { id: 2, icon: 'security', label: 'Secure' },
            { id: 3, icon: 'location-on', label: 'CSE Focus' }
          ].map((item, index) => (
            <Animated.View 
              key={item.id} 
              style={[styles.alignmentItem, {
                opacity: animValues[index],
                transform: [
                  { translateY: animValues[index].interpolate({ inputRange: [0, 1], outputRange: [20, 0] }) },
                  { scale: animValues[index].interpolate({ inputRange: [0, 1], outputRange: [0.8, 1] }) },
                  { translateY: floatAnims[index].interpolate({ inputRange: [0, 1], outputRange: [0, -8] }) }
                ]
              }]}
            >
              <View style={styles.alignmentIconBox}>
                <MaterialIcons name={item.icon} size={30} color={colors.onPrimary} />
              </View>
              <Text style={styles.alignmentText}>{item.label}</Text>
            </Animated.View>
          ))}
        </View>

        {/* AI Insights Card Stack */}
        <View style={{ height: 230, width: '100%', position: 'relative' }}>
          {renderInsightsStack()}
        </View>

        {/* Category chips: two views of the whole market, then the CSE's real
            industry groups with their live company counts. Was six fixed strings,
            three of which ("Banking", "Manufacturing", "AI Picks") are not sectors
            and one of which ("Capital Goods") matched six of its 29 companies by
            ticker prefix. */}
        <ScrollView style={{ marginTop: 36 }} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsScroll}>
          {[
            { label: ALL_MARKETS, count: null },
            { label: TOP_MOVERS, count: null },
            ...sectorChips.map(s => ({ label: s.sector, count: s.count })),
          ].map(({ label, count }) => {
            const isActive = activeChip === label;
            return (
              <TouchableTick
                key={label}
                style={[styles.chip, isActive ? styles.chipActive : styles.chipInactive, isActive ? styles.glassButtonDark : styles.glassButton]}
                onPress={() => setActiveChip(label)}
              >
                <BlurView intensity={isActive ? 40 : 30} tint={isActive ? "dark" : "light"} style={StyleSheet.absoluteFillObject} />
                <Text style={[styles.chipText, isActive ? styles.chipTextActive : styles.chipTextInactive]}>
                  {count === null ? label : `${label} ${count}`}
                </Text>
              </TouchableTick>
            );
          })}
        </ScrollView>

        {/* Watchlist Banner / Preview */}
        <TouchableTick style={[styles.watchlistBanner, styles.glassButton, { flexDirection: 'column', alignItems: 'flex-start', padding: 20 }]} onPress={() => navigation.navigate('Watchlist')}>
          <BlurView intensity={40} tint="light" style={StyleSheet.absoluteFillObject} />
          
          <View style={[styles.watchlistBannerLeft, { width: '100%', justifyContent: 'space-between' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', flex: 1 }}>
              <View style={[styles.watchlistIconBox, { width: 32, height: 32, borderRadius: 8 }]}>
                <MaterialIcons name={activeChip === TOP_MOVERS ? "trending-up" : "stacked-line-chart"} size={18} color="#FFF" />
              </View>
              <Text numberOfLines={1} style={[styles.watchlistBannerTitle, { marginLeft: 10, fontSize: 16, flex: 1 }]}>
                {activeChip === ALL_MARKETS ? 'Most traded today' : activeChip}
              </Text>
            </View>
            <View style={styles.watchlistArrowBox}>
              <MaterialIcons name="arrow-forward" size={18} color={colors.primary} />
            </View>
          </View>

          {/* Six rows of real market data, or a line saying why there are none. */}
          <View style={{ width: '100%', marginTop: 15 }}>
            {stocksError !== null ? (
              <Text style={styles.previewNote}>{stocksError}</Text>
            ) : filteredStocks.length === 0 ? (
              <Text style={styles.previewNote}>
                {activeChip === ALL_MARKETS || activeChip === TOP_MOVERS
                  ? 'No market data recorded yet.'
                  : `No quotes recorded for ${activeChip} yet.`}
              </Text>
            ) : filteredStocks.map((stock) => {
              // Same null-change defect as the browse list: `null >= 0` is true, so a
              // symbol with no previous close rendered as a green "+null%" gain.
              const pct = Number.isFinite(stock.change_pct) ? stock.change_pct : null;
              const up = pct !== null && pct >= 0;
              return (
                // Keyed on the symbol rather than the array index — the chip
                // reorders and refilters this list.
                <View key={stock.symbol} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <Text style={{ color: colors.onBackground, fontFamily: 'Inter_600SemiBold', fontSize: 14 }}>{stock.symbol.split('.')[0]}</Text>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={{ color: colors.onBackground, fontFamily: 'Inter_600SemiBold', fontSize: 14 }}>
                      {/* Optional-chained: `price` is nullable on the response and
                          `.toFixed` on null threw, taking the whole screen down. */}
                      Rs. {Number.isFinite(stock.price) ? stock.price.toFixed(2) : '—'}
                    </Text>
                    <Text style={{ color: pct === null ? colors.onSurfaceVariant : up ? colors.success : colors.error, fontFamily: 'Inter_500Medium', fontSize: 12 }}>
                      {pct === null ? 'no prior close' : `${up ? '+' : ''}${pct.toFixed(2)}%`}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>
        </TouchableTick>

        {/* Monthly Allocation */}
        <View style={styles.card}>
          <View style={styles.allocationHeader}>
            <Text style={styles.cardTitle}>Investment Goal</Text>
            <MaterialIcons name="more-horiz" size={24} color={colors.onSurfaceVariant} />
          </View>

          {hasGoal ? (
            <>
              <View style={styles.allocationLabels}>
                <Text style={styles.allocationLabel}>Current Value</Text>
                <Text style={styles.allocationValue}>
                  Rs. {currentVal.toLocaleString('en-US', { maximumFractionDigits: 0 })} / Rs. {targetVal.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                </Text>
              </View>

              <View style={styles.progressBarBg}>
                <View style={[styles.progressBarFill, { width: progressPct }]} />
              </View>

              {/* Scale markers for the bar above, not portfolio figures. */}
              <View style={styles.allocationTags}>
                <View style={styles.tagNormal}><Text style={styles.tagNormalText}>70%</Text></View>
                <View style={styles.tagWarning}><Text style={styles.tagWarningText}>85% Alert</Text></View>
                <View style={styles.tagNormal}><Text style={styles.tagNormalText}>100%</Text></View>
              </View>
            </>
          ) : (
            <View style={styles.chartEmpty}>
              <MaterialIcons name="savings" size={28} color={colors.onSurfaceVariant} />
              <Text style={styles.chartEmptyTitle}>No holdings yet</Text>
              <Text style={styles.chartEmptyText}>
                Add a stock to a portfolio and this tile tracks its value against a
                goal.
              </Text>
            </View>
          )}
        </View>

        {/* Portfolio valuation history */}
        <TouchableTick style={[styles.card, { marginBottom: 30 }]} onPress={() => setShowTrendModal(true)}>
          <View style={styles.trendHeaderNew}>
            <Text style={styles.trendTitleNew}>Portfolio Performance</Text>
            {/* The point count, where a two-item legend reading "This week / Last
                week" used to be. The legend described a comparison that did not
                exist: the grey bar was just the previous bar's value replotted, and
                for the first bar it was that value × 0.9. The series is as long as
                the snapshot task has been running, so how many days it covers is
                the thing the user actually needs in order to read it. */}
            <Text style={styles.trendMetaNew}>
              {history.length === 0
                ? 'No history yet'
                : `${history.length} ${history.length === 1 ? 'day' : 'days'} · last ${historyDays}d`}
            </Text>
          </View>

          {history.length === 0 ? (
            <View style={styles.chartEmpty}>
              <MaterialIcons name="show-chart" size={28} color={colors.onSurfaceVariant} />
              <Text style={styles.chartEmptyTitle}>No valuation history yet</Text>
              <Text style={styles.chartEmptyText}>
                Your holdings are valued once each trading day. The chart starts
                filling in from the first snapshot.
              </Text>
            </View>
          ) : (
            <View style={styles.chartWrapperNew}>
              {/* Y-Axis & Grid Lines */}
              <View style={styles.chartGrid}>
                {yLabels.map((label, index) => (
                  <View key={index} style={[styles.gridLineContainer, index === 4 && styles.gridLineContainerLast]}>
                    <Text style={styles.gridLabel}>{label}</Text>
                    <View style={[styles.gridLine, index === 4 && { borderTopWidth: 0 }]} />
                  </View>
                ))}
              </View>

              {/* One bar per stored trading day, oldest first. Rendered from the
                  series rather than as four hardcoded groups, because the length is
                  whatever has accumulated — one point on the first day, thirty once
                  the window is full. */}
              <View style={styles.barsWrapperNew}>
                {history.map((point, index) => (
                  <View key={point.date ?? index} style={styles.dayGroup}>
                    {windowChange !== null && index === history.length - 1 && (
                      <View style={styles.calloutContainer}>
                        <Text style={styles.calloutText}>
                          {windowChange}% {Number(windowChange) >= 0 ? '↑' : '↓'}
                        </Text>
                      </View>
                    )}
                    <Animated.View
                      style={[styles.barNew, {
                        height: chartAnim.interpolate({
                          inputRange: [0, 1],
                          outputRange: [0, getH(point.value)],
                        }),
                        backgroundColor: colors.primary,
                      }]}
                    />
                    {(index === 0 || index === history.length - 1) && (
                      <Text style={styles.dayLabelNew} numberOfLines={1}>
                        {dayLabel(point.date)}
                      </Text>
                    )}
                  </View>
                ))}
              </View>
            </View>
          )}
        </TouchableTick>

      </ScrollView>

      {/* Animated Popup for Weekly Trend */}
      <ActionFeedbackModal
        visible={showTrendModal}
        onClose={() => setShowTrendModal(false)}
        title="Portfolio Performance"
        message={
          history.length === 0
            ? `Your portfolio is valued once each trading day and the last ${historyDays} days are charted here. Nothing has been recorded yet — add a holding and the first point appears after the next valuation.`
            : `This chart plots ${history.length} recorded ${history.length === 1 ? 'valuation' : 'valuations'} of your holdings, from ${dayLabel(history[0].date)} to ${dayLabel(history[history.length - 1].date)}, using closing prices from the CSE.${windowChange !== null ? ` Over that period the total moved ${windowChange}%.` : ' A second valuation is needed before a change can be shown.'}`
        }
        type="info"
        autoClose={false}
      />
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
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.05)',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.surfaceVariant,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '500',
    fontFamily: 'Satoshi-Medium',
    color: colors.primary,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  settingsBtn: {
    padding: 8,
    borderRadius: 20,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 24,
    paddingBottom: 40,
    gap: 24,
  },
  greetingSection: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  greetingText: {
    fontSize: 24,
    fontWeight: '700',
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  subtitleText: {
    fontSize: 16,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurfaceVariant,
    marginTop: 4,
  },
  loginTag: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  loginText: {
    fontSize: 12,
    fontWeight: '700',
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  notificationBtn: {
    padding: 8,
    borderRadius: 24,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 10,
    position: 'relative',
  },
  notificationDot: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 8,
    height: 8,
    backgroundColor: colors.error,
    borderRadius: 4,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 24,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 10,
    overflow: 'hidden',
  },
  aspiCard: {
    position: 'relative',
    backgroundColor: '#0a2e4a',
    borderColor: 'rgba(255, 255, 255, 0.2)',
    borderWidth: 1,
    borderRadius: 16,
    shadowColor: '#002743',
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.4,
    shadowRadius: 24,
    elevation: 20,
    overflow: 'hidden'
  },
  cardGlowOverlay: {
    ...StyleSheet.absoluteFillObject,
    opacity: 0.8,
  },
  aspiRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 16,
    zIndex: 1,
  },
  cardLabelNew: {
    fontSize: 11,
    fontFamily: 'Satoshi-Bold',
    color: colors.onSurfaceVariant,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
  aspiValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 6,
  },
  aspiValueNew: {
    fontSize: 36,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
    letterSpacing: -0.5,
    fontVariant: ['tabular-nums'],
  },
  aspiChangeBadgeNew: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ccfbf1',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
  },
  aspiChangeTextNew: {
    fontSize: 13,
    fontFamily: 'Satoshi-Bold',
    color: '#0d9488',
  },
  volumeWrapper: {
    width: '100%',
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 16,
    gap: 24,
  },
  volumeWidget: {
    width: 120,
    height: 120,
    justifyContent: 'center',
    alignItems: 'center',
  },
  volumeCenter: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  volumeLegend: {
    gap: 12,
    justifyContent: 'center',
  },
  alignmentRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 8,
    marginVertical: 24,
  },
  alignmentItem: {
    alignItems: 'center',
    gap: 12,
  },
  alignmentIconBox: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 20,
    elevation: 8,
  },
  alignmentText: {
    fontSize: 16,
    fontFamily: 'Satoshi-Bold',
    color: colors.onSurfaceVariant,
  },
  aiCard: {
    backgroundColor: colors.primaryContainer,
    borderRadius: 12,
    padding: 24,
    height: 210,
    overflow: 'hidden',
    shadowColor: colors.primaryContainer,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 32,
    elevation: 10,
  },
  aiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
  },
  aiLabel: {
    fontSize: 14,
    fontWeight: '700',
    fontFamily: 'Satoshi-Bold',
    color: colors.primaryFixed,
    letterSpacing: 0.5,
  },
  aiBody: {
    fontSize: 18,
    fontFamily: 'Satoshi-Regular',
    lineHeight: 28,
    color: colors.onPrimary,
    marginBottom: 16,
  },
  aiButton: {
    alignSelf: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  aiButtonText: {
    fontSize: 14,
    fontWeight: '700',
    fontFamily: 'Satoshi-Bold',
    color: '#FFF',
  },
  chipsScroll: {
    paddingBottom: 8,
    gap: 12,
  },
  chip: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chipActive: {
  },
  chipInactive: {
  },
  chipText: {
    fontSize: 14,
    fontWeight: '500',
    fontFamily: 'Satoshi-Medium',
  },
  chipTextActive: {
    color: colors.onPrimary,
  },
  chipTextInactive: {
    color: colors.primary,
  },
  watchlistBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderRadius: 16,
  },
  watchlistBannerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  watchlistIconBox: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  watchlistBannerTitle: {
    fontSize: 18,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  watchlistBannerSub: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
    marginTop: 2,
  },
  watchlistArrowBox: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#FFF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Stands in for the six preview rows when there are none. Previously the banner
  // just collapsed to its title, so an empty market and a market of six flat stocks
  // looked like two different screens with no explanation of which was which.
  previewNote: {
    fontSize: 13,
    lineHeight: 20,
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
    paddingVertical: 8,
  },
  allocationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: '500',
    fontFamily: 'Satoshi-Medium',
    color: colors.primary,
  },
  allocationLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  allocationLabel: {
    fontSize: 14,
    fontWeight: '500',
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
  },
  allocationValue: {
    fontSize: 14,
    fontWeight: '700',
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  progressBarBg: {
    height: 12,
    backgroundColor: colors.surfaceVariant,
    borderRadius: 6,
    overflow: 'hidden',
    marginBottom: 16,
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: colors.warning,
    borderRadius: 6,
  },
  allocationTags: {
    flexDirection: 'row',
    gap: 8,
  },
  tagNormal: {
    backgroundColor: colors.surfaceVariant,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  tagNormalText: {
    fontSize: 12,
    fontWeight: '500',
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
  },
  tagWarning: {
    backgroundColor: 'rgba(245, 166, 35, 0.2)',
    borderWidth: 1,
    borderColor: 'rgba(245, 166, 35, 0.3)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  tagWarningText: {
    fontSize: 12,
    fontWeight: '500',
    fontFamily: 'Satoshi-Medium',
    color: colors.warning,
  },
  trendHeaderNew: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
    flexWrap: 'wrap',
    gap: 12,
  },
  trendTitleNew: {
    fontSize: 18,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
    letterSpacing: -0.5,
  },
  chartWrapperNew: {
    marginTop: 8,
    position: 'relative',
    height: 200, 
  },
  chartGrid: {
    ...StyleSheet.absoluteFillObject,
    bottom: 24,
  },
  gridLineContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    height: 40,
  },
  gridLineContainerLast: {
    height: 20, 
  },
  gridLabel: {
    width: 44,
    fontSize: 11,
    color: '#94a3b8',
    fontFamily: 'Satoshi-Medium',
    marginTop: -8, 
  },
  gridLine: {
    flex: 1,
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
  },
  barsWrapperNew: {
    position: 'absolute',
    bottom: 24,
    left: 48,
    right: 0,
    height: 160,
    flexDirection: 'row',
    // space-around was right for four fixed-width groups; with flex: 1 day groups
    // the row is already fully divided, and the leftover margin it adds would
    // shrink each bar for nothing.
    alignItems: 'flex-end',
  },
  trendMetaNew: {
    fontSize: 11,
    fontFamily: 'Satoshi-Medium',
    color: '#94a3b8',
  },
  chartEmpty: {
    alignItems: 'center',
    paddingVertical: 28,
    paddingHorizontal: 12,
    gap: 8,
  },
  chartEmptyTitle: {
    fontSize: 14,
    fontFamily: 'Satoshi-Bold',
    color: colors.onBackground,
  },
  chartEmptyText: {
    fontSize: 12,
    lineHeight: 18,
    textAlign: 'center',
    fontFamily: 'Satoshi-Medium',
    color: colors.onSurfaceVariant,
  },
  // flex: 1 rather than the old fixed-width group. The number of bars is now the
  // number of days recorded, up to 30, so any fixed width overflows the card as
  // soon as the series outgrows the four it used to hardcode.
  dayGroup: {
    flex: 1,
    height: 160,
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
  barNew: {
    // A share of the slot the flex gave us, so bars thin out as days accumulate
    // instead of spilling over. maxWidth keeps a one-point series from drawing a
    // single bar the full width of the chart, which reads as a filled area rather
    // than as one day; minWidth keeps a full 30-day series visible.
    width: '62%',
    maxWidth: 16,
    minWidth: 2,
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
  },
  dayLabelNew: {
    fontSize: 11,
    fontFamily: 'Satoshi-Medium',
    color: '#475569',
    position: 'absolute',
    bottom: -22,
    // Wider than the bar slot it sits in, centred on it, so a date is not clipped
    // to "2" when thirty bars leave each slot a few points wide.
    width: 60,
    textAlign: 'center',
  },
  calloutContainer: {
    position: 'absolute',
    top: -24,
    alignItems: 'center',
    width: 60,
  },
  calloutText: {
    color: '#c98375',
    fontSize: 11,
    fontFamily: 'Satoshi-Bold',
  },
  glassButton: {
    overflow: 'hidden',
    backgroundColor: 'rgba(255, 255, 255, 0.4)',
    borderColor: 'rgba(255, 255, 255, 0.6)',
    borderWidth: 1,
  },
  glassButtonDark: {
    overflow: 'hidden',
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    borderColor: 'rgba(255, 255, 255, 0.2)',
    borderWidth: 1,
  }
});
