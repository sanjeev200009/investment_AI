// src/screens/LessonScreen.js — one beginner lesson, read top to bottom.
// v2 "Soft pastel": meta chip, big light title, readable body, lavender key terms.
import React, { useEffect, useState } from 'react';
import { View, StyleSheet } from 'react-native';
import {
  Screen, Header, PillButton, Chip, Card, Title, Heading, Label, Body, EmptyState, Loading,
} from '../components/ui';
import { learnApi } from '../api/api';
import { useT } from '../store/languageStore';
import { palette } from '../theme/tokens';

export default function LessonScreen({ route, navigation }) {
  const { id, title } = route.params || {};
  const { t } = useT();
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    learnApi.get(id)
      .then(data => { if (!cancelled) setLesson(data); })
      .catch(err => { if (!cancelled) setError(err?.response?.data?.detail || t('lesson_load_error')); });
    return () => { cancelled = true; };
  }, [id]);

  const askAssistant = () => navigation.navigate('AIChat', {
    prompt: t('lesson_ask_prompt').replace('{title}', lesson?.title || title),
  });

  return (
    <Screen>
      <Header onBack={() => navigation.goBack()} backLabel={t('lesson_back')} />
      {error ? (
        <EmptyState icon="error-outline" tone="coral" message={error} />
      ) : !lesson ? (
        <Loading />
      ) : (
        <>
          <View style={{ gap: 12, paddingHorizontal: 4 }}>
            <Chip tone="lavender" label={`${t('lesson_min_read').replace('{minutes}', lesson.minutes)} · ${lesson.theme}`} />
            <Title>{lesson.title}</Title>
            <Body style={styles.summary}>{lesson.summary}</Body>
          </View>
          {lesson.sections.map(s => (
            <View key={s.heading} style={{ gap: 8, paddingHorizontal: 4 }}>
              <Heading>{s.heading}</Heading>
              <Body style={styles.body}>{s.body}</Body>
            </View>
          ))}
          <Card style={{ gap: 12 }}>
            <Label>{t('lesson_key_terms')}</Label>
            <View style={styles.termRow}>
              {lesson.key_terms.map(term => <Chip key={term} tone="lavender" label={term} />)}
            </View>
          </Card>
          <PillButton
            icon="auto-awesome"
            title={t('lesson_ask')}
            label={t('lesson_ask_a11y')}
            onPress={askAssistant}
          />
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  summary: { fontSize: 17, lineHeight: 25, color: palette.muted },
  body: { fontSize: 16, lineHeight: 25 },
  termRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
});
