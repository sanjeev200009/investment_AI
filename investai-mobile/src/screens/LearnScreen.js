// src/screens/LearnScreen.js
//
// Beginner lessons (proposal 6.5). The text comes from the backend, the same
// text the AI assistant teaches from, so the two never disagree.
// v2 "Soft pastel": lessons as a stack of pastel cards, each with a large
// light lesson number; the last card is white.
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import {
  Screen, Header, StackCard, Title, Label, EmptyState, Loading, accent, ACCENT_CYCLE,
} from '../components/ui';
import { learnApi } from '../api/api';
import { useT } from '../store/languageStore';
import { palette, fonts } from '../theme/tokens';

export default function LearnScreen({ navigation }) {
  const { t } = useT();
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
          {lessons.map((lesson, i) => {
            const last = i === lessons.length - 1;
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
                label={t('learn_row_a11y').replace('{title}', lesson.title).replace('{minutes}', lesson.minutes)}
              >
                <Text style={[styles.number, { color: last ? palette.muted : ink }]}>{i + 1}</Text>
                <View style={{ flex: 1, gap: 2 }}>
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
      <Label style={{ textAlign: 'center' }}>{t('learn_disclaimer')}</Label>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  number: { fontFamily: fonts.light, fontSize: 44, lineHeight: 50, width: 50 },
  rowTitle: { fontFamily: fonts.regular, fontSize: 19, lineHeight: 24 },
  meta: { fontFamily: fonts.regular, fontSize: 13 },
});
