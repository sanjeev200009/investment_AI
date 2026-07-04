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
import { useUser, useAuth } from '@clerk/clerk-expo';
import axios from 'axios';

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
  warning: '#F5A623',
  cardShadow: 'rgba(28, 61, 90, 0.06)'
};

export default function HomeScreen({ navigation }) {
  const { user, isAuthenticated } = useAuthStore();
  const { user: clerkUser } = useUser();
  const { getToken } = useAuth();
  
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const userName = clerkUser?.firstName || clerkUser?.fullName?.split(' ')[0] || clerkUser?.primaryEmailAddress?.emailAddress?.split('@')[0] || user?.full_name?.split(' ')[0] || 'Sanjeev';
  const lastName = clerkUser?.lastName || user?.full_name?.split(' ').slice(1).join(' ') || 'PERERA';

  const [aspiCount, setAspiCount] = useState(12000);
  const [showTrendModal, setShowTrendModal] = useState(false);

  const animValues = useRef([...Array(4)].map(() => new Animated.Value(0))).current;
  const floatAnims = useRef([...Array(4)].map(() => new Animated.Value(0))).current;
  const chartAnim = useRef(new Animated.Value(0)).current;

  // AI Insights Swipeable Stack State
  const [insightIndex, setInsightIndex] = useState(0);
  const swipePosition = useRef(new Animated.ValueXY()).current;
  
  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const token = await getToken();
        const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
        const res = await axios.get(`${baseUrl}/dashboard/`, {
          headers: { 
            Authorization: `Bearer ${token}`,
            'ngrok-skip-browser-warning': 'true'
          }
        });
        setDashboardData(res.data);
      } catch (e) {
        console.error("Dashboard fetch error", e);
        // Fallback data so the UI doesn't break if API/DB is unreachable
        setDashboardData({
          aspi: { value: 12450.80, change_pct: 1.2 },
          portfolio: { current_value: 145000, target_value: 200000 },
          insights: [
            {
              id: 'insight1',
              label: 'AI INSIGHT',
              body: 'Banking sector showing irregular volume spikes. Consider reviewing your financial allocations before close.',
              buttonText: 'Analyze Portfolio'
            },
            {
              id: 'insight2',
              label: 'MARKET MOVER',
              body: 'Renewable energy stocks are rallying. WindForce is up 12% today following the new policy announcements.',
              buttonText: 'View Stocks'
            },
            {
              id: 'insight3',
              label: 'RISK ALERT',
              body: 'Your portfolio is highly concentrated in Finance. Diversifying into Manufacturing could lower your risk profile.',
              buttonText: 'Diversify Now'
            }
          ],
          watchlist_preview: [
            { symbol: 'SAMP.N0000', price: 78.50, change_pct: 1.2 },
            { symbol: 'JKH.N0000', price: 195.25, change_pct: -0.5 },
            { symbol: 'EXPO.N0000', price: 145.00, change_pct: 2.1 }
          ]
        });
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  const AI_INSIGHTS = dashboardData?.insights || [];

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
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
            setInsightIndex((prev) => (prev + 1) % AI_INSIGHTS.length);
            swipePosition.setValue({ x: 0, y: 0 });
          });
        } else if (gestureState.dx < -120) {
          Animated.timing(swipePosition, {
            toValue: { x: -width - 100, y: 0 },
            duration: 200,
            useNativeDriver: false
          }).start(() => {
            setInsightIndex((prev) => (prev + 1) % AI_INSIGHTS.length);
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
    return AI_INSIGHTS.map((item, i) => {
      let relIndex = i - insightIndex;
      if (relIndex < 0) relIndex += AI_INSIGHTS.length;

      if (relIndex > 1) return null;

      const isTop = relIndex === 0;

      const animatedStyle = isTop ? {
        transform: [
          { translateX: swipePosition.x },
          { rotate: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: ['-5deg', '0deg', '5deg'] }) }
        ],
        zIndex: 99
      } : {
        transform: [
          { scale: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: [1, 0.95, 1], extrapolate: 'clamp' }) },
          { translateY: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: [0, 15, 0], extrapolate: 'clamp' }) }
        ],
        zIndex: 1,
        opacity: swipePosition.x.interpolate({ inputRange: [-width/2, 0, width/2], outputRange: [1, 0.5, 1], extrapolate: 'clamp' })
      };

      return (
        <Animated.View
          key={item.id}
          style={[styles.aiCard, { position: 'absolute', width: '100%', top: 0 }, animatedStyle]}
          {...(isTop ? panResponder.panHandlers : {})}
        >
          <View style={styles.aiHeader}>
            <MaterialIcons name="auto-awesome" size={20} color={colors.primaryFixed} />
            <Text style={styles.aiLabel}>{item.label}</Text>
          </View>
          <Text style={styles.aiBody}>{item.body}</Text>
          <TouchableTick style={[styles.aiButton, styles.glassButtonDark]}>
            <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFillObject} />
            <Text style={styles.aiButtonText}>{item.buttonText}</Text>
          </TouchableTick>
        </Animated.View>
      );
    }).reverse();
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

  // Simple counting animation for ASPI
  useEffect(() => {
    if (!dashboardData) return;
    let start = 12000;
    const end = dashboardData.aspi.value;
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
            source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCRuV64gZivpBqIADKt06wm-68V-FCe8a9BZomAQ3ab8MDZ2FsvJ1HLg5pdO7xl7jYZjY9iaqzZ27XXB5oei50JrGa_ER45mkkY61ClOjQD2eBUQDubUAGYinzsR0cl4-Edsp9SgS7XYEYGZ5aZx6M2rl4YSG6ImwAhf5x_puLwc0rMQZjpvGElkqopRbhXD6qcRH3DD6djp_oKpyPRhyHhwGchkNc238vSC5Na76wlkakejugIasdwa6DXPlA2UqMLWyOZj0_jUKE' }}
            style={styles.avatar}
          />
          <Text style={styles.headerTitle}>InvestAI</Text>
        </View>
        <View style={styles.headerRight}>
          {!isAuthenticated && (
              <TouchableTick style={[styles.notificationBtn, styles.glassButton, { marginTop: 0, marginRight: 8 }]} onPress={() => navigation.navigate('Auth')}>
                <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFillObject} />
                <MaterialIcons name="login" size={24} color={colors.primary} />
              </TouchableTick>
          )}
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

        {/* ASPI Market Overview (Credit Card Design) */}
        <View style={[styles.card, styles.aspiCard]}>
          <LinearGradient
            colors={['#0a2e4a', '#051624']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={StyleSheet.absoluteFillObject}
          />
          <LinearGradient
            colors={['rgba(255, 255, 255, 0.15)', 'rgba(0, 0, 0, 0.3)']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.cardGlowOverlay}
          />
          
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, zIndex: 1 }}>
            <MaterialIcons name="memory" size={44} color="#eab308" />
            <MaterialIcons name="contactless" size={28} color="rgba(255,255,255,0.6)" style={{ transform: [{ rotate: '90deg' }] }} />
          </View>

          <View style={[styles.aspiRow, { flexWrap: 'nowrap', flexDirection: 'column', alignItems: 'stretch' }]}>
            <View>
              <Text style={[styles.cardLabelNew, { color: 'rgba(255, 255, 255, 0.6)' }]}>ASPI MARKET OVERVIEW</Text>
              <View style={styles.aspiValueRow}>
                <Text style={[styles.aspiValueNew, { color: '#ffffff', letterSpacing: 2 }]}>
                  {aspiCount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                </Text>
                <View style={[styles.aspiChangeBadgeNew, { backgroundColor: 'rgba(45, 212, 191, 0.15)' }]}>
                  <MaterialIcons name="trending-up" size={14} color="#2dd4bf" />
                  <Text style={[styles.aspiChangeTextNew, { color: '#2dd4bf' }]}>+1.2%</Text>
                </View>
              </View>

              <View style={{ flexDirection: 'row', marginTop: 16, gap: 32 }}>
                <View>
                  <Text style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', fontFamily: 'Satoshi-Medium', marginBottom: 2 }}>INVESTOR</Text>
                  <Text style={{ fontSize: 13, color: '#ffffff', fontFamily: 'Satoshi-Bold', letterSpacing: 1, textTransform: 'uppercase' }}>{userName} {lastName}</Text>
                </View>
                <View>
                  <Text style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', fontFamily: 'Satoshi-Medium', marginBottom: 2 }}>MEMBER SINCE</Text>
                  <Text style={{ fontSize: 13, color: '#ffffff', fontFamily: 'Satoshi-Bold', letterSpacing: 1 }}>12/28</Text>
                </View>
              </View>
            </View>
            
            <View style={[styles.volumeWrapper, { marginTop: 24, justifyContent: 'space-between' }]}>
              <View style={styles.volumeWidget}>
                 <Svg height="120" width="120" viewBox="0 0 120 120">
                   <G transform="rotate(-90 60 60)">
                     <Circle cx="60" cy="60" r="45" stroke={colors.primary} strokeWidth="8" fill="transparent" strokeDasharray="109 282.74" strokeDashoffset="0" strokeLinecap="round" />
                     <Circle cx="60" cy="60" r="45" stroke={colors.onPrimaryContainer} strokeWidth="8" fill="transparent" strokeDasharray="95 282.74" strokeDashoffset="-117" strokeLinecap="round" />
                     <Circle cx="60" cy="60" r="45" stroke={colors.warning} strokeWidth="8" fill="transparent" strokeDasharray="66 282.74" strokeDashoffset="-216" strokeLinecap="round" />
                   </G>
                 </Svg>
                 <View style={styles.volumeCenter}>
                   <MaterialIcons name="bar-chart" size={48} color="#ffffff" />
                 </View>
              </View>
              <View style={[styles.volumeLegend, { alignItems: 'flex-end' }]}>
                 <View style={styles.legendItem}>
                    <Text style={[styles.legendText, { color: 'rgba(255,255,255,0.9)' }]}>Banking (40%)</Text>
                    <View style={[styles.legendDot, { backgroundColor: colors.primary, marginLeft: 6 }]} />
                 </View>
                 <View style={styles.legendItem}>
                    <Text style={[styles.legendText, { color: 'rgba(255,255,255,0.9)' }]}>Capital Goods (35%)</Text>
                    <View style={[styles.legendDot, { backgroundColor: colors.onPrimaryContainer, marginLeft: 6 }]} />
                 </View>
                 <View style={styles.legendItem}>
                    <Text style={[styles.legendText, { color: 'rgba(255,255,255,0.9)' }]}>Food & Bev (25%)</Text>
                    <View style={[styles.legendDot, { backgroundColor: colors.warning, marginLeft: 6 }]} />
                 </View>
              </View>
            </View>
          </View>
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
        <View style={{ height: 210, width: '100%', position: 'relative' }}>
          {renderInsightsStack()}
        </View>

        {/* Category Chips */}
        <ScrollView style={{ marginTop: 36 }} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsScroll}>
          <TouchableTick style={[styles.chip, styles.chipActive, styles.glassButtonDark]}>
            <BlurView intensity={40} tint="dark" style={StyleSheet.absoluteFillObject} />
            <Text style={[styles.chipText, styles.chipTextActive]}>All Markets</Text>
          </TouchableTick>
          <TouchableTick style={[styles.chip, styles.chipInactive, styles.glassButton]}>
            <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFillObject} />
            <Text style={[styles.chipText, styles.chipTextInactive]}>AI Picks</Text>
          </TouchableTick>
          <TouchableTick style={[styles.chip, styles.chipInactive, styles.glassButton]}>
            <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFillObject} />
            <Text style={[styles.chipText, styles.chipTextInactive]}>Banking</Text>
          </TouchableTick>
          <TouchableTick style={[styles.chip, styles.chipInactive, styles.glassButton]}>
            <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFillObject} />
            <Text style={[styles.chipText, styles.chipTextInactive]}>Manufacturing</Text>
          </TouchableTick>
          <TouchableTick style={[styles.chip, styles.chipInactive, styles.glassButton]}>
            <BlurView intensity={30} tint="light" style={StyleSheet.absoluteFillObject} />
            <Text style={[styles.chipText, styles.chipTextInactive]}>Capital Goods</Text>
          </TouchableTick>
        </ScrollView>

        {/* Watchlist Banner / Preview */}
        <TouchableTick style={[styles.watchlistBanner, styles.glassButton, { flexDirection: 'column', alignItems: 'flex-start', padding: 20 }]} onPress={() => navigation.navigate('Watchlist')}>
          <BlurView intensity={40} tint="light" style={StyleSheet.absoluteFillObject} />
          
          <View style={[styles.watchlistBannerLeft, { width: '100%', justifyContent: 'space-between' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <View style={[styles.watchlistIconBox, { width: 32, height: 32, borderRadius: 8 }]}>
                <MaterialIcons name="trending-up" size={18} color="#FFF" />
              </View>
              <Text style={[styles.watchlistBannerTitle, { marginLeft: 10, fontSize: 16 }]}>Top Movers</Text>
            </View>
            <View style={styles.watchlistArrowBox}>
              <MaterialIcons name="arrow-forward" size={18} color={colors.primary} />
            </View>
          </View>

          {/* Real Data Preview */}
          <View style={{ width: '100%', marginTop: 15 }}>
            {dashboardData?.watchlist_preview?.map((stock, idx) => (
              <View key={idx} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <Text style={{ color: colors.onBackground, fontFamily: 'Inter_600SemiBold', fontSize: 14 }}>{stock.symbol.split('.')[0]}</Text>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={{ color: colors.onBackground, fontFamily: 'Inter_600SemiBold', fontSize: 14 }}>Rs. {stock.price.toFixed(2)}</Text>
                  <Text style={{ color: stock.change_pct >= 0 ? colors.success : colors.error, fontFamily: 'Inter_500Medium', fontSize: 12 }}>
                    {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct}%
                  </Text>
                </View>
              </View>
            ))}
          </View>
        </TouchableTick>

        {/* Monthly Allocation */}
        <View style={styles.card}>
          <View style={styles.allocationHeader}>
            <Text style={styles.cardTitle}>Investment Goal</Text>
            <MaterialIcons name="more-horiz" size={24} color={colors.onSurfaceVariant} />
          </View>
          
          <View style={styles.allocationLabels}>
            <Text style={styles.allocationLabel}>Current Value</Text>
            <Text style={styles.allocationValue}>Rs. {dashboardData?.portfolio?.current_value?.toLocaleString()} / Rs. {dashboardData?.portfolio?.target_value?.toLocaleString()}</Text>
          </View>

          <View style={styles.progressBarBg}>
            <View style={[styles.progressBarFill, { width: '72.5%' }]} />
          </View>

          <View style={styles.allocationTags}>
            <View style={styles.tagNormal}><Text style={styles.tagNormalText}>70%</Text></View>
            <View style={styles.tagWarning}><Text style={styles.tagWarningText}>85% Alert</Text></View>
            <View style={styles.tagNormal}><Text style={styles.tagNormalText}>100%</Text></View>
          </View>
        </View>

        {/* Weekly Trend */}
        <TouchableTick style={[styles.card, { marginBottom: 30 }]} onPress={() => setShowTrendModal(true)}>
          <View style={styles.trendHeaderNew}>
            <Text style={styles.trendTitleNew}>Portfolio Performance</Text>
            <View style={styles.trendLegendContainer}>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: colors.primary }]} />
                <Text style={styles.legendText}>This week</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: '#cbd5e1' }]} />
                <Text style={styles.legendText}>Last week</Text>
              </View>
            </View>
          </View>
          
          <View style={styles.chartWrapperNew}>
            {/* Y-Axis & Grid Lines */}
            <View style={styles.chartGrid}>
              {['Rs. 10k', 'Rs. 7.5k', 'Rs. 5k', 'Rs. 2.5k', 'Rs. 0'].map((label, index) => (
                <View key={index} style={[styles.gridLineContainer, index === 4 && styles.gridLineContainerLast]}>
                  <Text style={styles.gridLabel}>{label}</Text>
                  <View style={[styles.gridLine, index === 4 && { borderTopWidth: 0 }]} />
                </View>
              ))}
            </View>

            {/* Bars Container */}
            <View style={styles.barsWrapperNew}>
              {/* Week 1 */}
              <View style={styles.weekGroup}>
                <View style={styles.barGroup}>
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 55] }), backgroundColor: '#cbd5e1' }]} />
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 75] }), backgroundColor: colors.primary }]} />
                </View>
                <Text style={styles.weekLabel}>Week 1</Text>
              </View>
              
              {/* Week 2 */}
              <View style={styles.weekGroup}>
                <View style={styles.barGroup}>
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 70] }), backgroundColor: '#cbd5e1' }]} />
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 95] }), backgroundColor: colors.primary }]} />
                </View>
                <Text style={styles.weekLabel}>Week 2</Text>
              </View>
              
              {/* Week 3 */}
              <View style={styles.weekGroup}>
                <View style={styles.calloutContainer}>
                  <Text style={styles.calloutText}>30% ↑</Text>
                </View>
                <View style={styles.barGroup}>
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 105] }), backgroundColor: '#cbd5e1' }]} />
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 145] }), backgroundColor: colors.primary }]} />
                </View>
                <Text style={styles.weekLabel}>Week 3</Text>
              </View>
              
              {/* Week 4 */}
              <View style={styles.weekGroup}>
                <View style={styles.barGroup}>
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 85] }), backgroundColor: '#cbd5e1' }]} />
                  <Animated.View style={[styles.barNew, { height: chartAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 0] }), backgroundColor: 'transparent' }]} />
                </View>
                <Text style={styles.weekLabel}>Week 4</Text>
              </View>
            </View>
          </View>
        </TouchableTick>

      </ScrollView>

      {/* Animated Popup for Weekly Trend */}
      <ActionFeedbackModal
        visible={showTrendModal}
        onClose={() => setShowTrendModal(false)}
        title="Sector Performance"
        message="The Banking sector is currently outperforming the broader market by 30% this week. Our AI suggests maintaining your current positions."
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
  trendLegendContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendText: {
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
    color: '#64748b',
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
    justifyContent: 'space-around',
    alignItems: 'flex-end',
  },
  weekGroup: {
    alignItems: 'center',
  },
  barGroup: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 6,
    height: 160,
  },
  barNew: {
    width: 16, 
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
  },
  weekLabel: {
    marginTop: 8,
    fontSize: 11,
    fontFamily: 'Satoshi-Medium',
    color: '#475569',
    position: 'absolute',
    bottom: -24,
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
