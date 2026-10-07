// src/screens/LearnScreen.js
//
// Beginner lessons (proposal 6.5). The text comes from the backend, the same
// text the AI assistant teaches from, so the two never disagree.
// v2 "Soft pastel": lessons as a stack of pastel cards, each with a large
// light lesson number; the last card is white.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import TouchableTick from '../components/TouchableTick';
import { useFocusEffect } from '@react-navigation/native';
import {
  Screen, Header, StackCard, Card, Title, Label, EmptyState, Loading, Chip, accent, ACCENT_CYCLE,
} from '../components/ui';
import { learnApi, planApi } from '../api/api';
import { useT } from '../store/languageStore';
import { palette, fonts } from '../theme/tokens';
import { afterTransition } from '../theme/motion';

export default function LearnScreen({ navigation }) {
  const { t } = useT();
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [lessons, setLessons] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setLessons(await learnApi.list());
    } catch (err) {
      setLessons([]);
      setError(err?.response?.data?.detail || t('learn_load_error'));
    }
  }, []); // t is recreated each render; not a dep

  useEffect(() => { load(); }, [load]);

  // The personal plan orders the lessons and knows which ones were opened
  // (its learn_* steps are done once the lesson is viewed). No plan: API order.
  const [plan, setPlan] = useState(null);
  useFocusEffect(useCallback(() => {
    let cancelled = false;
    const cancel = afterTransition(() => planApi.get().then(p => { if (!cancelled) setPlan(p); }));
    return () => { cancelled = true; cancel(); };
  }, []));

  const { ordered, recommendedId } = useMemo(() => {
    const list = lessons || [];
    const order = (plan?.lesson_ids || []).filter(id => list.some(l => l.id === id));
    if (!order.length) return { ordered: list, recommendedId: null };
    const rank = id => { const i = order.indexOf(id); return i === -1 ? order.length : i; };
    const opened = new Set((plan.steps || []).filter(st => st.done && st.lesson_id).map(st => st.lesson_id));
    return {
      ordered: [...list].sort((a, b) => rank(a.id) - rank(b.id)),
      recommendedId: order.find(id => !opened.has(id)) || null,
    };
  }, [lessons, plan]);

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  return (
    <Screen refreshing={refreshing} onRefresh={onRefresh}>
      <Header title={t('learn_title')} onBack={() => navigation.goBack()} backLabel={t('learn_back')} />

      <View style={{ gap: 6, paddingHorizontal: 4 }}>
        <Title>{t('learn_heading')}</Title>
        <Label style={{ fontSize: 15, lineHeight: 21 }}>{t('learn_subtitle')}</Label>
      </View>

      {lessons === null ? (
        <Loading />
      ) : error ? (
        <EmptyState icon="error-outline" tone="coral" message={error} />
      ) : (
        <View style={{ marginHorizontal: -8 }}>
          {ordered.map((lesson, i) => {
            const last = i === ordered.length - 1;
            const recommended = lesson.id === recommendedId;
            const tone = last && i > 0 ? 'white' : ACCENT_CYCLE[i % ACCENT_CYCLE.length];
            const ink = accent(tone).ink;
            return (
              <StackCard
                key={lesson.id}
                tone={tone}
                first={i === 0}
                last={last}
                style={styles.card}
                onPress={() => navigation.navigate('Lesson', { id: lesson.id, title: lesson.title })}
                label={`${recommended ? `${t('learn_recommended')}. ` : ''}${t('learn_row_a11y').replace('{title}', lesson.title).replace('{minutes}', lesson.minutes)}`}
              >
                <Text style={[styles.number, { color: last ? palette.muted : ink }]}>{i + 1}</Text>
                <View style={{ flex: 1, gap: 2 }}>
                  {recommended ? <Chip tone="white" icon="auto-awesome" label={t('learn_recommended')} /> : null}
                  <Text style={[styles.rowTitle, { color: ink }]}>{lesson.title}</Text>
                  <Text style={[styles.meta, { color: last ? palette.muted : ink }]}>
                    {t('learn_minutes').replace('{minutes}', lesson.minutes)} · {lesson.theme}
                  </Text>
                </View>
              </StackCard>
            );
          })}
        </View>
      )}
      {/* Words explained: every investing word the app uses, in plain language */}
      <Card style={{ gap: 12 }}>
        <TouchableTick
          onPress={() => setGlossaryOpen(o => !o)}
          accessibilityRole="button"
          accessibilityState={{ expanded: glossaryOpen }}
          style={styles.glossHead}
        >
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.rowTitle}>{t('glossary_title')}</Text>
            <Label>{t('glossary_sub')}</Label>
          </View>
          <MaterialIcons name={glossaryOpen ? 'expand-less' : 'expand-more'} size={26} color={palette.ink} />
        </TouchableTick>
        {glossaryOpen && GLOSSARY.map(n => (
          <View key={n} style={{ gap: 2 }}>
            <Text style={styles.term}>{t(`gl_${n}_t`)}</Text>
            <Text style={styles.meaning}>{t(`gl_${n}_d`)}</Text>
          </View>
        ))}
      </Card>
      <Label style={{ textAlign: 'center' }}>{t('learn_disclaimer')}</Label>
    </Screen>
  );
}

const GLOSSARY = Array.from({ length: 20 }, (_, i) => i + 1); // gl_1 … gl_20 in i18n/simple.js

const styles = StyleSheet.create({
  glossHead: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 44 },
  term: { fontFamily: fonts.medium, fontSize: 16, color: palette.ink },
  meaning: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 21, color: palette.ink },
  card: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  number: { fontFamily: fonts.light, fontSize: 44, lineHeight: 50, width: 50 },
  rowTitle: { fontFamily: fonts.regular, fontSize: 19, lineHeight: 24 },
  meta: { fontFamily: fonts.regular, fontSize: 13 },
});
