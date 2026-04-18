import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, StatusBar, Platform, Animated } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { Swipeable } from 'react-native-gesture-handler';
import { useAppTheme } from '../hooks/useAppTheme';

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
    const trans = dragX.interpolate({
      inputRange: [-80, 0],
      outputRange: [0, 80],
      extrapolate: 'clamp',
    });
    return (
      <TouchableOpacity style={styles.deleteAction} onPress={() => onDelete(item.id)}>
        <Animated.View style={{ transform: [{ translateX: 0 }] }}>
          <MaterialIcons name="delete" size={24} color="#FFFFFF" />
        </Animated.View>
      </TouchableOpacity>
    );
  };

  const cardBgColor = theme.isDark ? theme.colors.surface : '#FFFFFF';

  return (
    <Swipeable
      renderRightActions={renderRightActions}
      friction={2}
      rightThreshold={40}
      onSwipeableOpen={() => onDelete(item.id)}
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

  const categories = ['Price Alerts', 'News', 'Educational', 'System'];

  const deleteNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const bgColor = theme.isDark ? theme.colors.background : '#F2F2F7';

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: bgColor }]}>
      <StatusBar barStyle={theme.isDark ? 'light-content' : 'dark-content'} />

      {/* iOS Style Sticky Header */}
      <View style={[styles.header, { backgroundColor: theme.isDark ? 'rgba(10, 10, 10, 0.8)' : 'rgba(242, 242, 247, 0.8)' }]}>
        <View style={styles.topActions}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <MaterialIcons name="arrow-back-ios" size={20} color="#1565c1" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setNotifications([])}>
            <Text style={[styles.actionText, { color: '#1565c1' }]}>Mark All Read</Text>
          </TouchableOpacity>
        </View>
        <Text style={[styles.largeTitle, { color: theme.colors.textPrimary }]}>Notifications</Text>
      </View>

      {/* Pill Categories */}
      <View style={[styles.pillContainer, { borderBottomColor: theme.colors.divider }]}>
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

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {notifications.length > 0 ? (
          notifications.map(item => (
            <NotificationCard
              key={item.id}
              item={item}
              onDelete={deleteNotification}
            />
          ))
        ) : (
          <View style={styles.emptyState}>
            <MaterialIcons name="notifications-none" size={64} color={theme.colors.textMuted} />
            <Text style={[styles.emptyText, { color: theme.colors.textSecondary }]}>No notifications yet</Text>
          </View>
        )}
      </ScrollView>

      {/* Visual Home Indicator Mockup */}
      <View style={styles.homeIndicatorWrapper}>
        <View style={[styles.homeIndicator, { backgroundColor: theme.isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)' }]} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 20,
  },
  topActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  backBtn: {
    paddingVertical: 5,
  },
  actionText: {
    fontSize: 16,
    fontWeight: '500',
  },
  largeTitle: {
    fontSize: 34,
    fontWeight: '800',
    letterSpacing: -1,
  },
  pillContainer: {
    borderBottomWidth: 1,
    paddingBottom: 15,
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
    flexGrow: 1,
  },
  deleteAction: {
    backgroundColor: '#FF3B30',
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
    borderRadius: 12,
    height: '100%',
    marginBottom: 12, // Match card gap
  },
  card: {
    padding: 16,
    borderRadius: 12,
    marginBottom: 12, // Space between cards
  },
  iosShadow: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 2,
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
    marginBottom: 2,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
    flex: 1,
  },
  cardTime: {
    fontSize: 11,
    fontWeight: '500',
    marginLeft: 8,
  },
  cardSubtitle: {
    fontSize: 14,
    lineHeight: 19,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 100,
  },
  emptyText: {
    marginTop: 16,
    fontSize: 16,
    fontWeight: '500',
  },
  homeIndicatorWrapper: {
    position: 'absolute',
    bottom: 8,
    left: 0,
    right: 0,
    alignItems: 'center',
  },
  homeIndicator: {
    width: 120,
    height: 5,
    borderRadius: 2.5,
  },
});
