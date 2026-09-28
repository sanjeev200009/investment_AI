// src/screens/RulesScreen.js
// Investment rules — the screen I-10 waited on. tasks/rules_tasks.py has been
// evaluating rules every 15 market-hours minutes since it was written; until
// this screen (and its router) existed, nothing in the system could create one.
// A rule the user creates here fires a real notification the agent writes an
// explanation for — the cheapest end-to-end demonstration of the agentic claim.
//
// v2 "Soft pastel" (V2Alerts): big title, a Create pill with one circle per
// condition type, rules as a stack of pastel cards.
import TouchableTick from '../components/TouchableTick';
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, Modal, Alert } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import {
  Screen, Header, CircleButton, IconCircle, PillButton, Chip, StackCard, Title, Heading, Label,
  Field, EmptyState, Loading, accent, ACCENT_CYCLE,
} from '../components/ui';
import { rulesApi } from '../api/api';
import { useT } from '../store/languageStore';
import { palette, fonts, radii, sizes } from '../theme/tokens';

// Mirrors tasks/rules_tasks.py's CONDITION_EVALUATORS. The backend rejects
// anything else with a 422 listing the valid set, so this list is the UI's
// copy of that contract — keep the two in step.
const CONDITIONS = [
  { key: 'price_above', labelKey: 'rule_price_above', icon: 'trending-up', unit: 'LKR', example: '180' },
  { key: 'price_below', labelKey: 'rule_price_below', icon: 'trending-down', unit: 'LKR', example: '150' },
  { key: 'change_pct_up', labelKey: 'rule_change_pct_up', icon: 'north-east', unit: '%', example: '5' },
  { key: 'change_pct_down', labelKey: 'rule_change_pct_down', icon: 'south-east', unit: '%', example: '5' },
  { key: 'volume_spike', labelKey: 'rule_volume_spike', icon: 'bar-chart', unit: 'shares', example: '500000' },
];

export default function RulesScreen({ route, navigation }) {
  const prefillSymbol = route?.params?.symbol || '';
  const { t } = useT();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(null);

  // Opened from a stock's alert bell: go straight to the create form for it.
  const [createVisible, setCreateVisible] = useState(!!prefillSymbol);
  const [symbol, setSymbol] = useState(prefillSymbol);
  const [condition, setCondition] = useState(CONDITIONS[0].key);
  const [threshold, setThreshold] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchRules = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const data = await rulesApi.list();
      setRules(Array.isArray(data) ? data : []);
      setLoadError(null);
    } catch (err) {
      setLoadError(err?.response?.data?.detail || err?.message || t('rules_load_error'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const handleCreate = async () => {
    const sym = symbol.trim().toUpperCase();
    const value = parseFloat(threshold);
    if (!sym) {
      Alert.alert(t('rules_missing_symbol_title'), t('rules_missing_symbol_body'));
      return;
    }
    if (!Number.isFinite(value)) {
      Alert.alert(t('rules_missing_threshold_title'), t('rules_missing_threshold_body'));
      return;
    }
    setSaving(true);
    try {
      await rulesApi.create(sym, condition, value);
      setSymbol('');
      setThreshold('');
      setCreateVisible(false);
      fetchRules();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      Alert.alert(
        t('rules_create_error_title'),
        err?.response?.status === 404
          ? t('rules_no_market_data').replace('{symbol}', sym)
          : detail || t('rules_try_again'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (ruleId) => {
    const snapshot = rules;
    setRules(rules.filter(r => r.rule_id !== ruleId));
    try {
      await rulesApi.remove(ruleId);
    } catch (err) {
      console.warn('[Rules] delete failed:', err?.message || err);
      setRules(snapshot);
    }
  };

  const openCreate = (key) => {
    if (key) setCondition(key);
    setCreateVisible(true);
  };

  const activeCondition = CONDITIONS.find(c => c.key === condition);
  const unitLabel = (unit) => (unit === 'shares' ? t('rules_unit_shares') : unit || '');

  return (
    <Screen refreshing={refreshing} onRefresh={() => fetchRules(true)}>
      {navigation?.canGoBack?.() ? (
        <Header title={t('tab_alerts')} onBack={() => navigation.goBack()} backLabel={t('account_back')} />
      ) : null}

      <Title>{t('rules_heading')}</Title>

      {/* Create row: tap the pill for a new rule, or a circle to start with that condition. */}
      <View style={styles.createPill}>
        <TouchableTick
          style={styles.createHit}
          onPress={() => openCreate()}
          accessibilityRole="button"
          accessibilityLabel={t('rules_add')}
        >
          <MaterialIcons name="add" size={20} color={palette.ink} />
          <Text style={styles.createText} numberOfLines={1}>{t('rules_create_row')}</Text>
        </TouchableTick>
        {CONDITIONS.map(c => (
          <TouchableTick
            key={c.key}
            onPress={() => openCreate(c.key)}
            accessibilityRole="button"
            accessibilityLabel={t(c.labelKey)}
          >
            <IconCircle icon={c.icon} size={sizes.touch} />
          </TouchableTick>
        ))}
      </View>

      {loading ? (
        <Loading />
      ) : loadError ? (
        <EmptyState icon="cloud-off" tone="coral" message={loadError} />
      ) : rules.length === 0 ? (
        <EmptyState
          icon="notifications-active"
          title={t('rules_empty')}
          message={t('rules_empty_body')}
          action={t('rules_add')}
          onAction={() => openCreate()}
        />
      ) : (
        <View style={{ gap: 14 }}>
          <View style={styles.watchingRow}>
            <Heading>{t('rules_watching')}</Heading>
            <Text>
              <Text style={styles.count}>{rules.length}</Text>
              <Label> {t(rules.length === 1 ? 'rules_count_one' : 'rules_count_other')}</Label>
            </Text>
          </View>
          <View>
            {rules.map((rule, i) => {
              const cond = CONDITIONS.find(c => c.key === rule.condition_type);
              const tone = ACCENT_CYCLE[i % ACCENT_CYCLE.length];
              const a = accent(tone);
              return (
                <StackCard key={rule.rule_id} tone={tone} first={i === 0} last={i === rules.length - 1}>
                  <View style={styles.ruleRow}>
                    <View style={styles.ruleLeft}>
                      <IconCircle icon={cond?.icon || 'notifications'} color={a.ink} borderColor="rgba(0,0,0,0.18)" size={48} />
                      <Text style={[styles.ruleSymbol, { color: a.ink }]} numberOfLines={1}>{rule.symbol.split('.')[0]}</Text>
                    </View>
                    <View style={{ flex: 1, gap: 4 }}>
                      <Text style={[styles.ruleCondition, { color: a.ink }]}>
                        {cond ? t(cond.labelKey) : rule.condition_type}{' '}
                        {Number(rule.threshold).toLocaleString()} {unitLabel(cond?.unit)}
                      </Text>
                      <Label style={{ color: a.ink }}>{t('rules_check_schedule')}</Label>
                    </View>
                    <CircleButton
                      icon="delete-outline"
                      size={44}
                      iconColor={a.ink}
                      label={t('rules_delete_a11y')}
                      onPress={() => handleDelete(rule.rule_id)}
                    />
                  </View>
                </StackCard>
              );
            })}
          </View>
        </View>
      )}

      {/* Create-rule sheet */}
      <Modal visible={createVisible} animationType="slide" transparent onRequestClose={() => setCreateVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.sheet}>
            <View style={styles.headRow}>
              <Heading style={{ flex: 1 }}>{t('rules_create')}</Heading>
              <CircleButton icon="close" label={t('rules_close_a11y')} onPress={() => setCreateVisible(false)} />
            </View>

            <Field
              label={t('rules_symbol')}
              value={symbol}
              onChangeText={setSymbol}
              placeholder="HNB.N0000"
              autoCapitalize="characters"
              autoCorrect={false}
            />

            <View style={{ gap: 6 }}>
              <Text style={styles.fieldLabel}>{t('rules_condition')}</Text>
              <View style={styles.conditionList}>
                {CONDITIONS.map(c => (
                  <TouchableTick
                    key={c.key}
                    onPress={() => setCondition(c.key)}
                    accessibilityRole="button"
                    accessibilityState={{ selected: condition === c.key }}
                    style={styles.chipHit}
                  >
                    <Chip label={t(c.labelKey)} icon={c.icon} selected={condition === c.key} />
                  </TouchableTick>
                ))}
              </View>
            </View>

            <Field
              label={`${t('rules_threshold')} ${activeCondition ? `(${unitLabel(activeCondition.unit)})` : ''}`}
              value={threshold}
              onChangeText={setThreshold}
              placeholder={activeCondition ? t('rules_example').replace('{value}', activeCondition.example) : '0'}
              keyboardType="numeric"
            />

            <PillButton title={t('rules_create')} onPress={handleCreate} loading={saving} />
          </View>
        </View>
      </Modal>
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  createPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: sizes.circle,
    borderRadius: radii.full, backgroundColor: palette.glass, paddingLeft: 12, paddingRight: 6,
  },
  createHit: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: sizes.touch, minWidth: 0 },
  createText: { ...text, fontSize: 15, flexShrink: 1 },
  watchingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', paddingHorizontal: 4 },
  count: { ...text, fontSize: 40, letterSpacing: -1 },
  ruleRow: { flexDirection: 'row', gap: 14, alignItems: 'flex-start' },
  ruleLeft: { width: 64, gap: 10 },
  ruleSymbol: { ...text, fontSize: 13, fontFamily: fonts.medium },
  ruleCondition: { ...text, fontSize: 19 },
  fieldLabel: { ...text, fontFamily: fonts.medium, fontSize: 13, color: palette.muted, paddingLeft: 18 },
  conditionList: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 8 },
  chipHit: { minHeight: sizes.touch, justifyContent: 'center', maxWidth: '100%' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15,17,21,0.45)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#F3F3FA', borderTopLeftRadius: radii.xxl, borderTopRightRadius: radii.xxl,
    padding: 20, paddingBottom: 40, gap: 16,
  },
});
