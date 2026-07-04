import TouchableTick from '../components/TouchableTick';
import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Image, StatusBar, Animated as RNAnimated, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { Swipeable } from 'react-native-gesture-handler';

const { width } = Dimensions.get('window');

const colors = {
  surface: '#faf9fc',
  surfaceLowest: '#ffffff',
  surfaceHigh: '#e8e8ea',
  surfaceHighest: '#e3e2e5',
  onSurface: '#1a1c1e',
  onSurfaceVariant: '#43474d',
  primary: '#002743',
  primaryContainer: '#1c3d5a',
  primaryFixed: '#cfe5ff',
  onPrimaryFixed: '#001d34',
  secondaryContainer: '#dae3f5',
  onSecondaryContainer: '#5c6574',
  tertiaryContainer: '#e1e2e4',
  onTertiaryContainer: '#a3a5a7',
  error: '#ba1a1a',
  errorContainer: '#ffdad6',
  onErrorContainer: '#93000a',
  success: '#137333',
  successContainer: '#E6F4EA',
};

const DUMMY_ALERTS = [
  {
    id: '1',
    type: 'ai',
    title: 'AI Portfolio Insight',
    time: '2m ago',
    message: 'Unusual options activity detected in TSLA. Model suggests a 78% probability of volatility within 48 hours.',
    unread: true,
    tags: ['High Priority', 'TSLA']
  },
  {
    id: '2',
    type: 'price_down',
    title: 'Price Target Hit',
    time: '1h ago',
    message: 'AAPL has dropped below your set alert threshold of $170.00. Current price: $169.45.',
    unread: false,
  },
  {
    id: '3',
    type: 'price_up',
    title: '52-Week High',
    time: '3h ago',
    message: 'MSFT has reached a new 52-week high of $420.50. Consider reviewing your position.',
    unread: false,
  },
  {
    id: '4',
    type: 'news',
    title: 'Earnings Report Release',
    time: 'Yesterday',
    message: 'NVDA released Q4 earnings beating expectations by 15%. Revenue up 265% YoY.',
    unread: false,
    opacity: 0.7,
  },
  {
    id: '5',
    type: 'system',
    title: 'New Login Detected',
    time: 'Oct 12',
    message: 'A new sign-in to your InvestAI account was detected from an unrecognized device in New York, NY.',
    unread: false,
    opacity: 0.7,
  }
];

export default function NotificationsScreen({ navigation }) {
  const [alerts, setAlerts] = useState(DUMMY_ALERTS);
  const [activeTab, setActiveTab] = useState('All Alerts');

  const handleDelete = (id) => {
    setAlerts(alerts.filter(alert => alert.id !== id));
  };

  const markAllRead = () => {
    setAlerts(alerts.map(a => ({ ...a, unread: false })));
  };

  const renderRightActions = (progress, dragX, id) => {
    const trans = dragX.interpolate({
      inputRange: [-80, 0],
      outputRange: [1, 0],
      extrapolate: 'clamp',
    });
    
    return (
      <TouchableTick 
        style={styles.deleteAction}
        onPress={() => handleDelete(id)}
      >
        <RNAnimated.View style={{ transform: [{ scale: trans }] }}>
          <MaterialIcons name="delete" size={24} color="#FFF" />
        </RNAnimated.View>
      </TouchableTick>
    );
  };

  const getIconData = (type) => {
    switch(type) {
      case 'ai': return { name: 'psychology', bg: colors.primary, color: '#FFF' };
      case 'price_down': return { name: 'trending-down', bg: colors.errorContainer, color: colors.error };
      case 'price_up': return { name: 'trending-up', bg: colors.successContainer, color: colors.success };
      case 'news': return { name: 'newspaper', bg: colors.secondaryContainer, color: colors.onSecondaryContainer };
      case 'system': return { name: 'shield', bg: colors.tertiaryContainer, color: colors.onSurfaceVariant };
      default: return { name: 'notifications', bg: colors.surfaceHigh, color: colors.primary };
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.surface} />
      
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Image
            source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDLVR6r3X1jaRf-8ZQCTtRjik1MQwU2fEXj9bz30-gRzRVHXkAnVf-K4D5UR1SVgABUX5KuQ98tUpiAG9cSNuS-TgpfoEK9f4iIUUa_fmAETLF7FJ8s4TZeJQ9pnJivpieUwKB28YutCbqsZwNWaeIVJf26tG4I54Dtxle4RLmypNv2ARaKKM4hMvPeCbu7MvREnbTg4M8QcqDPeEgPnF2Wg7ZG8MWJABEP-UJQy209aujDuve73FpEC4Ty6C7HtOfxe5bDAr_n0Pc' }}
            style={styles.avatar}
          />
          <Text style={styles.headerTitle}>InvestAI</Text>
        </View>
        <TouchableTick 
          style={styles.settingsBtn}
          onPress={() => navigation.navigate('ProfileMain')}
        >
          <MaterialIcons name="settings" size={24} color={colors.onSurfaceVariant} />
        </TouchableTick>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        
        {/* Page Title & Actions */}
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Alerts</Text>
          <TouchableTick style={styles.markReadBtn} onPress={markAllRead}>
            <MaterialIcons name="done-all" size={18} color={colors.primary} />
            <Text style={styles.markReadText}>Mark all read</Text>
          </TouchableTick>
        </View>

        {/* Tab Bar */}
        <ScrollView 
          horizontal 
          showsHorizontalScrollIndicator={false} 
          contentContainerStyle={styles.tabContainer}
        >
          {['All Alerts', 'Price Alerts', 'News', 'System'].map((tab) => (
            <TouchableTick 
              key={tab}
              style={[styles.tabBtn, activeTab === tab ? styles.tabBtnActive : styles.tabBtnInactive]}
              onPress={() => setActiveTab(tab)}
            >
              <Text style={[styles.tabText, activeTab === tab ? styles.tabTextActive : styles.tabTextInactive]}>
                {tab}
              </Text>
            </TouchableTick>
          ))}
        </ScrollView>

        {/* Alerts List */}
        <View style={styles.alertsList}>
          {alerts.map((alert) => {
            const icon = getIconData(alert.type);
            return (
              <Swipeable
                key={alert.id}
                renderRightActions={(prog, drag) => renderRightActions(prog, drag, alert.id)}
                overshootRight={false}
              >
                <View style={[styles.alertCard, { opacity: alert.opacity || 1 }]}>
                  {alert.unread && <View style={styles.unreadDot} />}
                  
                  <View style={[styles.iconBox, { backgroundColor: icon.bg }]}>
                    <MaterialIcons name={icon.name} size={24} color={icon.color} />
                  </View>
                  
                  <View style={styles.alertContent}>
                    <View style={styles.alertHeaderRow}>
                      <Text style={styles.alertTitle}>{alert.title}</Text>
                      <Text style={styles.alertTime}>{alert.time}</Text>
                    </View>
                    <Text style={styles.alertMessage}>{alert.message}</Text>
                    
                    {alert.tags && (
                      <View style={styles.tagsContainer}>
                        {alert.tags.map((tag, i) => (
                          <View 
                            key={i} 
                            style={[styles.tag, i === 0 ? styles.tagPrimary : styles.tagSecondary]}
                          >
                            <Text style={[styles.tagText, i === 0 ? styles.tagTextPrimary : styles.tagTextSecondary]}>
                              {tag}
                            </Text>
                          </View>
                        ))}
                      </View>
                    )}
                  </View>
                </View>
              </Swipeable>
            );
          })}
        </View>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    height: 64,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surfaceHigh,
  },
  headerTitle: {
    fontSize: 24,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
    letterSpacing: -0.5,
  },
  settingsBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 120,
  },
  pageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  pageTitle: {
    fontSize: 32,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
    letterSpacing: -0.5,
  },
  markReadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  markReadText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
    color: colors.primary,
  },
  tabContainer: {
    gap: 8,
    paddingBottom: 24,
  },
  tabBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  tabBtnActive: {
    backgroundColor: colors.primary,
  },
  tabBtnInactive: {
    backgroundColor: colors.surfaceHigh,
  },
  tabText: {
    fontSize: 14,
    fontFamily: 'Satoshi-Medium',
  },
  tabTextActive: {
    color: '#FFF',
  },
  tabTextInactive: {
    color: colors.onSurfaceVariant,
  },
  alertsList: {
    gap: 12,
  },
  deleteAction: {
    backgroundColor: colors.error,
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
    borderTopRightRadius: 12,
    borderBottomRightRadius: 12,
  },
  alertCard: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceLowest,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(0, 39, 67, 0.05)',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 30,
    elevation: 10,
  },
  unreadDot: {
    position: 'absolute',
    top: 16,
    right: 16,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  iconBox: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  alertContent: {
    flex: 1,
    paddingRight: 12, // Space for unread dot
  },
  alertHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 4,
  },
  alertTitle: {
    fontSize: 16,
    fontFamily: 'Satoshi-Bold',
    color: colors.primary,
  },
  alertTime: {
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
    color: colors.onTertiaryContainer,
  },
  alertMessage: {
    fontSize: 14,
    fontFamily: 'Satoshi-Regular',
    color: colors.onSurfaceVariant,
    lineHeight: 20,
  },
  tagsContainer: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  tagPrimary: {
    backgroundColor: colors.primaryFixed,
  },
  tagSecondary: {
    backgroundColor: colors.surfaceHigh,
  },
  tagText: {
    fontSize: 12,
    fontFamily: 'Satoshi-Medium',
  },
  tagTextPrimary: {
    color: colors.onPrimaryFixed,
  },
  tagTextSecondary: {
    color: colors.onSurfaceVariant,
  },
});
