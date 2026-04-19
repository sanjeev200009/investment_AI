// src/screens/NotificationsScreen.js
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  StatusBar,
  Dimensions,
  Animated
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { Swipeable, GestureHandlerRootView } from 'react-native-gesture-handler';
import { BlurView } from 'expo-blur';
import { useAppTheme } from '../hooks/useAppTheme';
import AppHeader from '../components/AppHeader';
import ActionFeedbackModal from '../components/ActionFeedbackModal';

const NOTIFICATIONS_DATA = [
  {
    id: '1',
    showAccent: true,
    type: 'up',
    title: "HNB crosses LKR 185",
    subtitle: "HNB is currently trading at 185.50. This is 2.3% above your alert price of 185.00.",
    time: "2m ago"
  },
  {
    id: '2',
    showAccent: true,
    type: 'down',
    title: "JKH Alert",
    subtitle: "John Keells Holdings (JKH) dropped below LKR 190. Current price: 189.20.",
    time: "15m ago"
  },
  {
    id: '3',
    icon: "school",
    color: "#42A5F5",
    title: "Tip: Understanding P/E Ratios",
    subtitle: "Learn how Price-to-Earnings ratios help you evaluate if a stock is overvalued or bargain.",
    time: "1h ago"
  },
  {
    id: '4',
    icon: "newspaper",
    color: "#94A3B8",
    title: "Market Update: CSE High",
    subtitle: "The Colombo Stock Exchange ASPI closed today with a gain of 45 points reaching a 3-month high.",
    time: "3h ago"
  },
  {
    id: '5',
    icon: "settings",
    color: "#94A3B8",
    title: "Account Security",
    subtitle: "Your login session was verified. New device: iPhone 15 Pro.",
    time: "Yesterday"
  },
  {
    id: '6',
    type: 'up',
    title: "SAMP reaches Target",
    subtitle: "Sampath Bank PLC reached your target price of LKR 78.00.",
    time: "Yesterday"
  }
];

const NotificationCard = ({ item, onDelete }) => {
  const theme = useAppTheme();
  const { icon, title, subtitle, time, color, showAccent, type } = item;

  let dotColor = null;
  if (type === 'up') dotColor = '#34C759';
  if (type === 'down') dotColor = '#FF3B30';

  const renderRightActions = (progress, dragX) => {
    return (
      <TouchableOpacity 
        style={styles.deleteAction} 
        onPress={() => onDelete(item.id)}
        activeOpacity={0.8}
      >
        <MaterialIcons name="delete" size={24} color="#FFFFFF" />
      </TouchableOpacity>
    );
  };

  const cardBgColor = theme.isDark ? theme.colors.surface : '#FFFFFF';

  return (
    <Swipeable
      renderRightActions={renderRightActions}
      friction={2}
      containerStyle={styles.swipeContainer}
      rightThreshold={40}
    >
      <View style={[
        styles.card,
        { backgroundColor: cardBgColor },
        showAccent && { borderLeftColor: '#1565c1', borderLeftWidth: 4 },
        !theme.isDark && styles.iosShadow
      ]}>
        <View style={styles.cardContent}>
          <View style={styles.iconArea}>
            {dotColor ? (
              <View style={[styles.statusDot, { backgroundColor: dotColor }]} />
            ) : (
              <MaterialIcons name={icon} size={20} color={color || '#64748B'} />
            )}
          </View>
          <View style={styles.textColumn}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: theme.colors.textPrimary }]}>{title}</Text>
              <Text style={[styles.cardTime, { color: '#94A3B8' }]}>{time}</Text>
            </View>
            <Text style={[styles.cardSubtitle, { color: theme.isDark ? '#E0E0E0' : '#475569' }]}>{subtitle}</Text>
          </View>
        </View>
      </View>
    </Swipeable>
  );
};

export default function NotificationsScreen({ navigation }) {
  const theme = useAppTheme();
  const [activeTab, setActiveTab] = useState('Price Alerts');
  const [notifications, setNotifications] = useState(NOTIFICATIONS_DATA);
  const [showFeedback, setShowFeedback] = useState(false);

  const categories = ['Price Alerts', 'News', 'Educational', 'System'];
  const bgColor = theme.isDark ? theme.colors.background : '#F2F2F7';

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaView style={[styles.container, { backgroundColor: bgColor }]} edges={['top']}>
        <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />

        <AppHeader 
          title="Notifications" 
          onBack={() => navigation.goBack()}
          rightAction={
            <TouchableOpacity onPress={() => setShowFeedback(true)}>
              <MaterialIcons name="done-all" size={24} color={theme.colors.primary} />
            </TouchableOpacity>
          }
        />

        {/* Categories Tab Bar */}
        <View style={styles.pillContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.pillScroll}
          >
                {categories.map(cat => (
                  <TouchableOpacity
                    key={cat}
                    style={[
                      styles.pill,
                      { backgroundColor: activeTab === cat ? '#1A237E' : (theme.isDark ? theme.colors.surface : '#FFFFFF') },
                      activeTab !== cat && { borderColor: theme.colors.divider, borderWidth: 1 }
                    ]}
                    onPress={() => setActiveTab(cat)}
                  >
                    <Text style={[
                      styles.pillText,
                      { color: activeTab === cat ? '#FFFFFF' : (theme.isDark ? '#9CA3AF' : '#475569') }
                    ]}>
                      {cat}
                    </Text>
                  </TouchableOpacity>
                ))}
          </ScrollView>
        </View>

        <ScrollView 
          showsVerticalScrollIndicator={false} 
          contentContainerStyle={styles.scrollContent}
        >
          {notifications.length > 0 ? (
            notifications.map(item => (
              <NotificationCard
                key={item.id}
                item={item}
                onDelete={(id) => setNotifications(prev => prev.filter(n => n.id !== id))}
              />
            ))
          ) : (
            <View style={styles.emptyState}>
              <MaterialIcons name="notifications-none" size={64} color={theme.colors.textMuted} />
              <Text style={[styles.emptyText, { color: theme.colors.textSecondary }]}>No notifications yet</Text>
            </View>
          )}
        </ScrollView>

        <ActionFeedbackModal 
          visible={showFeedback} 
          onClose={() => setShowFeedback(false)}
          title="Cleared"
          message="All notifications have been marked as read."
          type="success"
        />
      </SafeAreaView>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  stickyHeader: {
    zIndex: 10,
  },
  blurHeader: {
    paddingTop: 10,
    paddingBottom: 4,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    marginBottom: 12,
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
  headerContent: {
    paddingHorizontal: 20,
    marginBottom: 15,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
  },
  largeTitle: {
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  actionText: {
    fontSize: 14,
    fontWeight: '600',
  },
  pillContainer: {
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.05)',
  },
  pillScroll: {
    paddingHorizontal: 20,
    gap: 12,
  },
  pill: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 25,
    justifyContent: 'center',
    alignItems: 'center',
  },
  pillText: {
    fontSize: 14,
    fontWeight: '600',
  },
  scrollContent: {
    padding: 16,
    gap: 12,
    paddingBottom: 40,
  },
  swipeContainer: {
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: '#FF3B30', // Revealed background
  },
  deleteAction: {
    backgroundColor: '#FF3B30',
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
    height: '100%',
  },
  card: {
    padding: 16,
    borderRadius: 16,
  },
  iosShadow: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 3,
  },
  cardContent: {
    flexDirection: 'row',
    gap: 12,
  },
  iconArea: {
    width: 20,
    alignItems: 'center',
    paddingTop: 4,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  textColumn: {
    flex: 1,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 4,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
    flex: 1,
  },
  cardTime: {
    fontSize: 12,
    fontWeight: '500',
    marginLeft: 8,
  },
  cardSubtitle: {
    fontSize: 14,
    lineHeight: 19,
    opacity: 0.9,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 120,
  },
  emptyText: {
    marginTop: 16,
    fontSize: 16,
    fontWeight: '500',
  },
  homeIndicatorWrapper: {
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'transparent',
  },
  homeIndicator: {
    width: 120,
    height: 5,
    borderRadius: 2.5,
  },
});
