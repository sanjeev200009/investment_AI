// The end of the onboarding journey: a dancing Pal in pill confetti, the
// knowledge score counting up, the risk profile, the persona and the first
// three steps of the plan from GET /me/plan. Rendered by AssessmentScreen once
// the answers are saved, so it needs no route of its own.
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, Animated, Easing } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { Screen, PillButton, Title, Label, Card } from '../../components/ui';
import { PillPal } from '../../components/PillPals';
import Celebrate from '../../components/Celebrate';
import { palette, fonts, radii } from '../../theme/tokens';
import { isReduceMotion } from '../../theme/motion';
import { useT } from '../../store/languageStore';

// Mirrors investai-backend/app/services/plan.py, for when the plan did not load.
const PERSONAS = { Low: 'cautious_starter', Medium: 'steady_builder', High: 'growth_explorer' };
const RISK_TONE = { Low: 'lime', Medium: 'yellow', High: 'coral' };

function DancingPal() {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (isReduceMotion()) return undefined;
    const ease = Easing.inOut(Easing.sin);
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 360, easing: ease, useNativeDriver: true }),
      Animated.timing(v, { toValue: 0, duration: 360, easing: ease, useNativeDriver: true }),
      Animated.timing(v, { toValue: -1, duration: 360, easing: ease, useNativeDriver: true }),
      Animated.timing(v, { toValue: 0, duration: 360, easing: ease, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [v]);
  return (
    <Animated.View style={{
      transform: [
        { translateY: v.interpolate({ inputRange: [-1, 0, 1], outputRange: [-10, 0, -10] }) },
        { rotate: v.interpolate({ inputRange: [-1, 1], outputRange: ['-9deg', '9deg'] }) },
      ],
    }}>
      <PillPal size={150} tone="lime" mood="joy" pose="cheer" confetti bob={false} />
    </Animated.View>
  );
}

function CountUp({ to, total }) {
  const [n, setN] = useState(isReduceMotion() ? to : 0);
  useEffect(() => {
    if (isReduceMotion()) return undefined;
    const v = new Animated.Value(0);
    const id = v.addListener(({ value }) => setN(Math.round(value)));
    const anim = Animated.timing(v, { toValue: to, duration: 900, delay: 300, easing: Easing.out(Easing.cubic), useNativeDriver: false });
    anim.start();
    return () => { anim.stop(); v.removeListener(id); };
  }, [to]);
  return <Text style={styles.score}>{n}<Text style={styles.scoreTotal}>/{total}</Text></Text>;
}

export default function VictoryScreen({ profile, plan, isRetake, onContinue }) {
  const { t } = useT();
  const [busy, setBusy] = useState(false);
  const category = profile?.category;
  const persona = plan?.persona || PERSONAS[category] || 'cautious_starter';
  const score = profile?.knowledge_score;
  const total = profile?.knowledge_total || 5;
  const steps = (plan?.steps || []).slice(0, 3);

  const go = async () => {
    setBusy(true);
    try { await onContinue(); } finally { setBusy(false); }
  };

  return (
    <Screen
      edges={['top', 'bottom']}
      contentStyle={styles.content}
      footer={
        <View style={styles.footer}>
          <PillButton
            title={isRetake ? t('victory_back_profile') : t('victory_continue')}
            knob={isRetake ? undefined : 'lime'}
            onPress={go}
            loading={busy}
          />
        </View>
      }
    >
      <View style={styles.hero}>
        <Celebrate loop count={22} spread={170} />
        <DancingPal />
      </View>
      <View style={styles.center}>
        <Title style={styles.title}>{t('victory_title')}</Title>
        <Text style={styles.subtitle}>{t('victory_subtitle')}</Text>
      </View>

      <View style={styles.statsRow}>
        {typeof score === 'number' ? (
          <Card style={styles.stat}>
            <View accessible accessibilityLabel={`${t('victory_knowledge')}: ${t('victory_score_a11y').replace('{score}', score).replace('{total}', total)}`} style={{ gap: 8 }}>
              <Label>{t('victory_knowledge')}</Label>
              <CountUp to={score} total={total} />
            </View>
          </Card>
        ) : null}
        {category ? (
          <Card style={styles.stat} tone={RISK_TONE[category]}>
            <Label>{t('victory_risk')}</Label>
            <View style={styles.riskRow}>
              <MaterialIcons name="shield" size={22} color={palette.ink} />
              <Text style={styles.riskText}>{t(`victory_risk_${category.toLowerCase()}`)}</Text>
            </View>
          </Card>
        ) : null}
      </View>

      <Card tone="lavender" style={{ gap: 6 }}>
        <Label>{t('victory_persona')}</Label>
        <Text style={styles.personaTitle}>{t(`persona_${persona}_title`)}</Text>
        <Text style={styles.body}>{t(`persona_${persona}_summary`)}</Text>
      </Card>

      <Card style={{ gap: 14 }}>
        <Label>{t('victory_plan')}</Label>
        {steps.length ? steps.map((s, i) => (
          <View key={s.id} style={styles.step}>
            <View style={[styles.stepDot, s.done && { backgroundColor: palette.lime }]}>
              {s.done
                ? <MaterialIcons name="check" size={16} color={palette.ink} />
                : <Text style={styles.stepNum}>{i + 1}</Text>}
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={styles.stepTitle}>{t(`plan_step_${s.id}_title`)}</Text>
              <Text style={styles.stepBody}>{t(`plan_step_${s.id}_body`)}</Text>
            </View>
          </View>
        )) : <Text style={styles.body}>{t('victory_plan_offline')}</Text>}
      </Card>

      <Text style={styles.disclaimer}>{t('victory_disclaimer')}</Text>
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  content: { paddingBottom: 24, gap: 16 },
  hero: { alignItems: 'center', justifyContent: 'center', paddingTop: 12, minHeight: 190 },
  center: { alignItems: 'center', gap: 6 },
  title: { fontSize: 40, lineHeight: 44, letterSpacing: -1.5, textAlign: 'center' },
  subtitle: { ...text, fontSize: 16, lineHeight: 22, color: palette.muted, textAlign: 'center' },
  statsRow: { flexDirection: 'row', gap: 12 },
  stat: { flex: 1, gap: 8 },
  score: { ...text, fontSize: 44, lineHeight: 50, letterSpacing: -1.5, fontVariant: ['tabular-nums'] },
  scoreTotal: { fontSize: 22, color: palette.muted },
  riskRow: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 50 },
  riskText: { ...text, fontFamily: fonts.medium, fontSize: 18, flexShrink: 1 },
  personaTitle: { ...text, fontFamily: fonts.medium, fontSize: 24, letterSpacing: -0.5 },
  body: { ...text, fontSize: 15, lineHeight: 21 },
  step: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  stepDot: {
    width: 28, height: 28, borderRadius: radii.full, borderWidth: 1.5, borderColor: palette.ink,
    alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFFFFF',
  },
  stepNum: { ...text, fontFamily: fonts.medium, fontSize: 13 },
  stepTitle: { ...text, fontFamily: fonts.medium, fontSize: 16 },
  stepBody: { ...text, fontSize: 14, lineHeight: 19, color: palette.muted },
  disclaimer: { ...text, fontSize: 12, color: palette.faint, textAlign: 'center' },
  footer: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 12 },
});
