// src/screens/WatchlistScreen.js
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  StatusBar,
  Dimensions,
  Platform,
  LayoutAnimation
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { Swipeable, GestureHandlerRootView } from 'react-native-gesture-handler';
import { useAppTheme } from '../hooks/useAppTheme';
import AppHeader from '../components/AppHeader';
import ActionFeedbackModal from '../components/ActionFeedbackModal';

const WATCHLIST_MOCK = [
  {
    id: '1',
    symbol: 'JKH',
    name: 'John Keells Holdings',
    price: '194.25',
    change: '+2.15 (1.12%)',
    isPositive: true,
    data: [4, 6, 5, 8, 7, 9, 10] // Heights for bars
  },
  {
    id: '2',
    symbol: 'HAYL',
    name: 'Hayleys PLC',
    price: '82.10',
    change: '-0.45 (0.54%)',
    isPositive: false,
    data: [7, 8, 6, 4, 5, 3, 2]
  },
  {
    id: '3',
    symbol: 'SAMP',
    name: 'Sampath Bank PLC',
    price: '78.50',
    change: '+1.20 (1.55%)',
    isPositive: true,
    data: [3, 4, 6, 5, 7, 8, 9]
  }
];

const INDICES = [
  { name: 'ASPI', value: '10,432.12', change: '+0.42%', isPositive: true },
  { name: 'S&P SL20', value: '3,012.45', change: '-0.15%', isPositive: false, fontMono: true },
  { name: 'NIKKEI', value: '38,124.00', change: '+1.2%', isPositive: true, opacity: 0.6 }
];

const MicroChart = ({ data, isPositive }) => (
  <View style={styles.chartContainer}>
    {data.map((val, idx) => (
      <View
        key={idx}
        style={[
          styles.chartBar,
          {
            height: `${val * 10}%`,
            backgroundColor: isPositive ? 'rgba(52, 199, 89, 0.2)' : 'rgba(255, 59, 48, 0.2)',
            // Last bar is solid
            ...(idx === data.length - 1 && { backgroundColor: isPositive ? '#34C759' : '#FF3B30' })
          }
        ]}
      />
    ))}
  </View>
);

const WatchlistCard = ({ item, onDelete }) => {
  const theme = useAppTheme();
  
  const renderRightActions = () => (
    <TouchableOpacity 
      style={styles.deleteAction} 
      onPress={() => onDelete(item.id)}
      activeOpacity={0.8}
    >
      <MaterialIcons name="delete" size={24} color="#FFFFFF" />
      <Text style={styles.deleteText}>REMOVE</Text>
    </TouchableOpacity>
  );

  return (
    <Swipeable renderRightActions={renderRightActions} friction={2} rightThreshold={40}>
      <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
        <View style={styles.cardHeader}>
          <View style={styles.symbolInfo}>
            <View style={[styles.symbolBadge, { backgroundColor: theme.isDark ? '#1E293B' : '#F1F5F9' }]}>
              <Text style={[styles.symbolText, { color: theme.colors.textSecondary }]}>{item.symbol}</Text>
            </View>
            <View>
              <Text style={[styles.symbolName, { color: theme.colors.textPrimary }]}>{item.symbol}</Text>
              <Text style={[styles.companyName, { color: theme.colors.textSecondary }]}>{item.name}</Text>
            </View>
          </View>
          <View style={styles.actionButtons}>
            <TouchableOpacity style={styles.iconBtn}>
              <MaterialIcons name="star" size={22} color="#FFB800" />
            </TouchableOpacity>
            <TouchableOpacity style={styles.iconBtn}>
              <MaterialIcons name="notifications-none" size={22} color="#94A3B8" />
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.cardFooter}>
          <View>
            <Text style={[styles.priceText, { color: theme.colors.textPrimary }]}>{item.price}</Text>
            <View style={styles.changeRow}>
              <MaterialIcons 
                name={item.isPositive ? "arrow-drop-up" : "arrow-drop-down"} 
                size={18} 
                color={item.isPositive ? "#34C759" : "#FF3B30"} 
              />
              <Text style={[styles.changeText, { color: item.isPositive ? "#34C759" : "#FF3B30" }]}>
                {item.change}
              </Text>
            </View>
          </View>
          <MicroChart data={item.data} isPositive={item.isPositive} />
        </View>
      </View>
    </Swipeable>
  );
};

export default function WatchlistScreen({ navigation }) {
  const theme = useAppTheme();
  const [watchlist, setWatchlist] = useState(WATCHLIST_MOCK);
  const [showFeedback, setShowFeedback] = useState(false);

  const handleDelete = (id) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setWatchlist(prev => prev.filter(item => item.id !== id));
  };

  const bgColor = theme.isDark ? theme.colors.background : '#F2F2F7';

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaView style={[styles.container, { backgroundColor: bgColor }]} edges={['top']}>
        <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />
        
        <AppHeader 
          title="Watchlist" 
          onBack={() => navigation.goBack()}
          rightAction={
            <TouchableOpacity 
              style={styles.addBtn}
              onPress={() => setShowFeedback(true)}
            >
              <MaterialIcons name="add" size={20} color={theme.colors.primary} />
            </TouchableOpacity>
          }
        />

        <View style={[styles.header, { backgroundColor: bgColor }]}>
          {/* Indices Scroll */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.indicesContainer}
            style={{ marginTop: 12 }}
          >
            {INDICES.map((idx, index) => (
              <View 
                key={index} 
                style={[
                  styles.indexCard, 
                  { backgroundColor: theme.colors.surface },
                  idx.opacity && { opacity: idx.opacity }
                ]}
              >
                <Text style={[styles.indexLabel, { color: theme.colors.textSecondary }, idx.fontMono && styles.monoText]}>
                  {idx.name}
                </Text>
                <Text style={[styles.indexVal, { color: theme.colors.textPrimary }]}>{idx.value}</Text>
                <Text style={[styles.indexChange, { color: idx.isPositive ? '#34C759' : '#FF3B30' }]}>
                  {idx.change}
                </Text>
              </View>
            ))}
          </ScrollView>
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
          {watchlist.length > 0 ? (
            watchlist.map(item => (
              <WatchlistCard key={item.id} item={item} onDelete={handleDelete} />
            ))
          ) : (
            <View style={styles.emptyState}>
              <View style={[styles.emptyIconCircle, { backgroundColor: theme.isDark ? '#1E293B' : '#F8FAFC' }]}>
                <MaterialIcons name="star-outline" size={48} color={theme.isDark ? '#475569' : '#CBD5E1'} />
              </View>
              <Text style={[styles.emptyTitle, { color: theme.colors.textMuted }]}>No more stocks</Text>
              <Text style={[styles.emptySubtitle, { color: theme.colors.textMuted }]}>
                Add stocks to your watchlist to track their performance and receive AI-powered insights.
              </Text>
              <TouchableOpacity 
                style={styles.exploreBtn} 
                onPress={() => navigation.navigate('Markets')}
              >
                <MaterialIcons name="search" size={20} color={theme.colors.primary} />
                <Text style={[styles.exploreText, { color: theme.colors.primary }]}>Explore Market</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>
        <ActionFeedbackModal 
          visible={showFeedback} 
          onClose={() => setShowFeedback(false)}
          title="Stock Search"
          message="Search and add functionality is coming soon!"
          type="info"
        />
      </SafeAreaView>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingBottom: 4,
    zIndex: 10,
  },
  headerInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingTop: 8,
    alignItems: 'center',
  },
  timeText: {
    fontSize: 14,
    fontWeight: '700',
  },
  statusIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  titleSection: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    paddingHorizontal: 20,
    marginTop: 12,
    marginBottom: 8,
  },
  largeTitle: {
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1.5,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 4,
  },
  addText: {
    fontSize: 14,
    fontWeight: '700',
  },
  indicesContainer: {
    paddingHorizontal: 20,
    gap: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.05)',
  },
  indexCard: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  indexLabel: {
    fontSize: 10,
    fontWeight: '800',
  },
  monoText: {
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontSize: 9,
  },
  indexVal: {
    fontSize: 13,
    fontWeight: '700',
  },
  indexChange: {
    fontSize: 10,
    fontWeight: '800',
  },
  scrollContent: {
    padding: 16,
    gap: 12,
    paddingBottom: 100,
  },
  card: {
    borderRadius: 20,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  symbolInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  symbolBadge: {
    width: 40,
    height: 40,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  symbolText: {
    fontSize: 11,
    fontWeight: '800',
  },
  symbolName: {
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 18,
  },
  companyName: {
    fontSize: 12,
    marginTop: 2,
    fontWeight: '500',
  },
  actionButtons: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconBtn: {
    padding: 6,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  priceText: {
    fontSize: 24,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  changeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: -4,
  },
  changeText: {
    fontSize: 13,
    fontWeight: '700',
  },
  chartContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 48,
    gap: 3,
    width: 96,
  },
  chartBar: {
    flex: 1,
    borderRadius: 2,
  },
  deleteAction: {
    backgroundColor: '#FF3B30',
    justifyContent: 'center',
    alignItems: 'center',
    width: 100,
    borderRadius: 20,
    marginLeft: 8,
  },
  deleteText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
    marginTop: 4,
  },
  emptyState: {
    alignItems: 'center',
    paddingHorizontal: 32,
    paddingVertical: 60,
    marginTop: 40,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: '#E2E8F0',
    borderRadius: 32,
  },
  emptyIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '800',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  exploreBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  exploreText: {
    fontSize: 15,
    fontWeight: '700',
  },
});
