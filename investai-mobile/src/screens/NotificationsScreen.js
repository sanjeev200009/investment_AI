// src/screens/NotificationsScreen.js
//
// Alerts, v2 "Soft pastel": unread notifications are pastel cards in a stack
// (tone by type), read ones turn white. Swipe left to delete.
import TouchableTick from '../components/TouchableTick';
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, Alert, Animated as RNAnimated } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { Swipeable } from 'react-native-gesture-handler';
import {
  Screen, CircleButton, IconCircle, Chip, Card, StackCard, Title, Label, Body, EmptyState, Loading, accent,
} from '../components/ui';
import { notificationsApi } from '../api/api';
import { toast } from '../components/Toast';
import { useT } from '../store/languageStore';
import { palette, fonts, radii, sizes } from '../theme/tokens';

// A relative time, without pulling a date library into one screen. The API
// returns ISO timestamps in UTC.
const timeAgo = (iso, t) => {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return t('alerts_just_now');
  if (mins < 60) return t('alerts_minutes_ago').replace('{n}', mins);
  const hours = Math.round(mins / 60);
  if (hours < 24) return t('alerts_hours_ago').replace('{n}', hours);
  const days = Math.round(hours / 24);
  if (days < 7) return t('alerts_days_ago').replace('{n}', days);
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
};

// Icon and pastel tone per notification type: yellow = needs attention,
// lime = done/ok, lavender = information.
const typeStyle = (type) => {
  switch (type) {
    case 'rule_alert': return { icon: 'notifications-active', tone: 'yellow' };
    case 'TEST': return { icon: 'check-circle', tone: 'lime' };
    case 'news': return { icon: 'newspaper', tone: 'lavender' };
    case 'market_open': return { icon: 'wb-sunny', tone: 'lime' };
    case 'market_close': return { icon: 'nights-stay', tone: 'coral' };
    case 'system': return { icon: 'shield', tone: 'lavender' };
    default: return { icon: 'notifications', tone: 'lavender' };
  }
};

// Chip with a 44px touch target (the kit's chip is 40 tall).
const FilterChip = ({ label, selected, onPress }) => (
  <TouchableTick onPress={onPress} accessibilityRole="button" accessibilityState={{ selected }} style={styles.chipHit}>
    <Chip label={label} selected={selected} />
  </TouchableTick>
);

export default function NotificationsScreen({ navigation }) {
  const { t } = useT();
  // Real notifications from GET /notifications (I-11).
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [activeTab, setActiveTab] = useState('all');

  const fetchAlerts = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const data = await notificationsApi.list();
      setAlerts(Array.isArray(data) ? data : []);
      setLoadError(null);
    } catch (err) {
      setLoadError(err?.response?.data?.detail || err?.message || t('alerts_load_error'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  const handleDelete = async (notifId) => {
    // Optimistic removal, reconciled by the server call; a failed delete is
    // restored on the next refresh rather than silently vanishing.
    const snapshot = alerts;
    setAlerts(alerts.filter(a => a.notif_id !== notifId));
    try {
      await notificationsApi.remove(notifId);
      toast(t('toast_notif_deleted'), 'info');
    } catch (err) {
      console.warn('[Notifications] delete failed:', err?.message || err);
      setAlerts(snapshot);
      toast(t('error_generic'), 'error');
    }
  };

  const markAllRead = async () => {
    setAlerts(alerts.map(a => ({ ...a, is_read: true })));
    try {
      await notificationsApi.markAllRead();
      toast(t('toast_notif_all_read'), 'success');
    } catch (err) {
      console.warn('[Notifications] mark-all failed:', err?.message || err);
      fetchAlerts();
      toast(t('error_generic'), 'error');
    }
  };

  const markOneRead = async (notifId) => {
    setAlerts(prev => prev.map(a => a.notif_id === notifId ? { ...a, is_read: true } : a));
    try {
      await notificationsApi.markRead(notifId);
    } catch { /* the next fetch reconciles */ }
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
        accessibilityRole="button"
        accessibilityLabel={t('delete')}
      >
        <RNAnimated.View style={[styles.deleteCircle, { transform: [{ scale: trans }] }]}>
          <MaterialIcons name="delete-outline" size={24} color={palette.coralInk} />
        </RNAnimated.View>
      </TouchableTick>
    );
  };

  // Tabs that match the data the API actually sends.
  const TABS = [
    { id: 'all', label: t('alerts_tab_all') },
    { id: 'unread', label: t('alerts_tab_unread') },
  ];
  const visibleAlerts = activeTab === 'unread'
    ? alerts.filter(a => !a.is_read)
    : alerts;

  return (
    <Screen refreshing={refreshing} onRefresh={() => fetchAlerts(true)}>
      {/* Header */}
      <View style={styles.headRow}>
        <Title style={{ flex: 1 }}>{t('alerts_title')}</Title>
        <CircleButton icon="done-all" label={t('alerts_mark_all')} onPress={markAllRead} />
        <CircleButton icon="settings" label={t('profile_title')} onPress={() => navigation.navigate('ProfileMain')} />
      </View>

      {/* Filters */}
      <View style={styles.chipRow}>
        {TABS.map(tab => (
          <FilterChip key={tab.id} label={tab.label} selected={activeTab === tab.id} onPress={() => setActiveTab(tab.id)} />
        ))}
      </View>

      {/* Entry point to the rules manager (I-10): the screen that makes
          rule_alert notifications exist in the first place. */}
      {navigation && (
        <Card onPress={() => navigation.navigate('Rules')} label={t('alerts_manage_rules')} style={styles.rulesRow}>
          <IconCircle icon="rule" />
          <Text style={styles.rowTitle}>{t('alerts_manage_rules')}</Text>
          <MaterialIcons name="arrow-forward" size={22} color={palette.ink} />
        </Card>
      )}

      {/* Alerts stack */}
      {loading ? (
        <Loading />
      ) : loadError ? (
        <EmptyState icon="cloud-off" tone="coral" message={loadError} />
      ) : visibleAlerts.length === 0 ? (
        <EmptyState
          icon={activeTab === 'unread' ? 'done-all' : 'notifications-none'}
          tone={activeTab === 'unread' ? 'lime' : 'lavender'}
          message={activeTab === 'unread' ? t('alerts_caught_up') : t('alerts_empty_hint')}
        />
      ) : (
        <View>
          {visibleAlerts.map((alert, i) => {
            const { icon, tone: typeTone } = typeStyle(alert.type);
            const tone = alert.is_read ? 'white' : typeTone;
            const a = accent(tone);
            const title = t({
              rule_alert: 'alerts_type_rule', TEST: 'alerts_type_test',
              market_open: 'alerts_type_market_open', market_close: 'alerts_type_market_close',
            }[alert.type] || 'alerts_type_other');
            return (
              <Swipeable
                key={alert.notif_id}
                renderRightActions={(prog, drag) => renderRightActions(prog, drag, alert.notif_id)}
                overshootRight={false}
                containerStyle={{ marginTop: i === 0 ? 0 : -22, borderRadius: radii.xxl }}
              >
                <StackCard
                  tone={tone}
                  first
                  last={i === visibleAlerts.length - 1}
                  onPress={() => markOneRead(alert.notif_id)}
                  label={`${alert.is_read ? '' : `${t('alerts_tab_unread')}, `}${title}, ${alert.message}`}
                >
                  <View style={styles.cardRow}>
                    <IconCircle icon={icon} color={a.ink} borderColor="rgba(0,0,0,0.15)" />
                    <View style={{ flex: 1, gap: 4 }}>
                      <View style={styles.titleRow}>
                        {!alert.is_read && <View style={[styles.unreadDot, { backgroundColor: a.ink }]} />}
                        <Text style={[styles.cardTitle, { color: a.ink }, !alert.is_read && { fontFamily: fonts.bold }]} numberOfLines={1}>
                          {title}
                        </Text>
                        <Label style={{ color: alert.is_read ? palette.faint : a.ink }}>{timeAgo(alert.timestamp, t)}</Label>
                      </View>
                      <Body style={{ color: alert.is_read ? palette.muted : a.ink }}>{alert.message}</Body>
                    </View>
                  </View>
                </StackCard>
              </Swipeable>
            );
          })}
        </View>
      )}
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  chipRow: { flexDirection: 'row', gap: 8, marginTop: -8 },
  chipHit: { minHeight: sizes.touch, justifyContent: 'center' },
  rulesRow: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 14 },
  rowTitle: { ...text, flex: 1, fontFamily: fonts.medium, fontSize: 16 },
  cardRow: { flexDirection: 'row', gap: 14, alignItems: 'flex-start' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  unreadDot: { width: 8, height: 8, borderRadius: radii.full },
  cardTitle: { ...text, flex: 1, fontFamily: fonts.medium, fontSize: 17 },
  deleteAction: { width: 88, alignItems: 'center', justifyContent: 'center' },
  deleteCircle: {
    width: 56, height: 56, borderRadius: radii.full, backgroundColor: palette.coral,
    alignItems: 'center', justifyContent: 'center',
  },
});
