// src/screens/LegalScreen.js
//
// Privacy policy and terms, in-app. Both stores require a privacy policy for
// an app that holds account and portfolio data. The text below describes what
// this codebase actually does; it is a draft for the project team to review
// and, for a store listing, to host at a public URL as well.
import React from 'react';
import { View } from 'react-native';
import { Screen, Header, Card, Title, Heading, Label, Body } from '../components/ui';
import { useT } from '../store/languageStore';

const UPDATED = '28 September 2026';

// [heading, body] translation keys, in order.
const PRIVACY = [1, 2, 3, 4, 5, 6].map(i => [`legal_privacy_${i}_heading`, `legal_privacy_${i}_body`]);
const TERMS = [1, 2, 3, 4, 5].map(i => [`legal_terms_${i}_heading`, `legal_terms_${i}_body`]);

export default function LegalScreen({ route, navigation }) {
  const { t } = useT();
  const doc = route?.params?.doc === 'terms' ? 'terms' : 'privacy';
  const sections = doc === 'terms' ? TERMS : PRIVACY;

  return (
    <Screen>
      <Header onBack={() => navigation.goBack()} backLabel={t('legal_back')} />
      <View style={{ gap: 6, paddingHorizontal: 4 }}>
        <Title>{t(doc === 'terms' ? 'legal_terms_title' : 'legal_privacy_title')}</Title>
        <Label>{t('legal_updated').replace('{date}', UPDATED)}</Label>
      </View>
      <Card style={{ gap: 22 }}>
        {sections.map(([heading, text]) => (
          <View key={heading} style={{ gap: 6 }}>
            <Heading style={{ fontSize: 18 }}>{t(heading)}</Heading>
            <Body>{t(text)}</Body>
          </View>
        ))}
      </Card>
    </Screen>
  );
}
