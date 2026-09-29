import React, { useState } from 'react';
import { View, Text, StyleSheet, Alert } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Screen, Header, PillButton, Title, Label, Chip } from '../../components/ui';
import { PillPal } from '../../components/PillPals';
import TouchableTick from '../../components/TouchableTick';
import JourneyRoad from '../../components/JourneyRoad';
import Celebrate from '../../components/Celebrate';
import VictoryScreen from './VictoryScreen';
import { palette, fonts, radii } from '../../theme/tokens';
import { useAuthStore } from '../../store/authStore';
import { useT } from '../../store/languageStore';
import { authApi } from '../../api/authApi';

// The investor journey: 10 profile questions and 5 knowledge checks, in the
// order they are walked. Option strings must stay identical to the canonical
// bank in investai-backend/app/services/risk_scoring.py (also served by
// GET /me/assessment/questions); the server rejects an unknown option with a
// 422 naming the question. Only the display is translated: profile questions
// show t(`assess_q${id}`) / t(`assess_q${id}_o${n}`) (src/i18n/screens/auth.js),
// knowledge checks t(`assess_k${id}`) / _o${n} / _x (src/i18n/features/onboarding.js).
// `correct` here only drives the celebration; the server marks the answers.
const P = (id, options) => ({ id, kind: 'profile', options });
const K = (id, options, correct) => ({ id, kind: 'knowledge', options, correct });

const QUESTIONS = [
  P(1, ['Retirement', 'Wealth Growth', 'Major Purchase (e.g., home)', 'Income Generation']),
  P(4, ['Never', 'Once or twice', 'Occasionally', 'Regularly']),
  K(101, ['A small part of the company', 'A loan you gave the company', 'A fixed-return savings deposit', 'A guarantee of future profits'], 0),
  P(3, ['Less than 1 year', '1–3 years', '3–5 years', '5+ years']),
  P(8, ['Sell everything', 'Sell some', 'Hold', 'Buy more']),
  K(102, ["The price of one bank's shares", 'The overall price movement of all shares listed on the CSE', "The Central Bank's interest rate", 'The value of the rupee against the dollar'], 1),
  P(2, ['Not comfortable at all', 'Slightly comfortable', 'Moderately comfortable', 'Very comfortable']),
  P(6, ['Less than 10%', '10–25%', '25–50%', 'More than 50%']),
  K(103, ['Guarantees you make a profit', 'Makes all your shares rise together', 'Spreads your money so one bad company hurts you less', 'Removes all risk from investing'], 2),
  P(10, ['Very safe (bonds/FDs)', 'Balanced', 'Growth-focused', 'High risk / High reward']),
  P(7, ['Yes, completely', 'Somewhat', "I've heard of it", 'No']),
  K(104, ['Trading volume to market value', 'Profit to the number of employees', "Last year's price to today's price", "A share's price to the company's earnings per share"], 3),
  P(5, ['Below 50,000', '50,000–100,000', '100,000–250,000', 'Above 250,000']),
  P(12, ['Yes, daily', 'Few times a week', 'Rarely', 'Never']),
  K(105, ['A fee you pay your stockbroker', 'A part of company profit paid to shareholders', 'A tax on selling shares', 'The gap between buying and selling prices'], 1),
];
const KINDS = QUESTIONS.map(q => q.kind);
const textKey = (q) => (q.kind === 'knowledge' ? `assess_k${q.id}` : `assess_q${q.id}`);

export default function AssessmentScreen({ navigation, route }) {
  // Also opened from Profile to retake it; that copy returns to Profile when
  // done instead of entering the app, and has nothing to skip.
  const isRetake = route?.name === 'RetakeAssessment';
  const user = useAuthStore(state => state.user);
  const setProfileSetupDone = useAuthStore(state => state.setProfileSetupDone);
  const setAssessmentResults = useAuthStore(state => state.setAssessmentResults);
  const { t } = useT();

  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [burst, setBurst] = useState(0);
  const [done, setDone] = useState(null); // { profile, plan } once submitted

  const q = QUESTIONS[currentQ];
  const answer = answers[q.id];
  const isLast = currentQ === QUESTIONS.length - 1;
  const rightFor = (item) => answers[item.id] === item.options[item.correct];

  // Per stop, whether its knowledge check was answered right (for the road).
  const results = {};
  QUESTIONS.forEach((item, i) => {
    if (item.kind === 'knowledge' && answers[item.id] !== undefined) results[i] = rightFor(item);
  });

  const handleSelect = (option) => {
    if (q.kind === 'knowledge') {
      if (answer !== undefined) return; // locked once revealed
      if (option === q.options[q.correct]) {
        setBurst(b => b + 1);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
      }
    }
    setAnswers({ ...answers, [q.id]: option });
  };

  const finish = async () => {
    if (isRetake) {
      navigation.goBack();
      return;
    }
    await setProfileSetupDone(user?.user_id);
    navigation.reset({ index: 0, routes: [{ name: 'MainTab' }] });
  };

  const handleNext = async () => {
    if (answer === undefined) {
      // The backend needs most of the scored weight for a reliable score, so
      // gaps are refused here, while the user still has the question in view.
      Alert.alert(t('assess_please_answer'), t('assess_please_answer_msg'));
      return;
    }
    if (!isLast) {
      setCurrentQ(currentQ + 1);
      return;
    }
    if (submitting) return;
    setSubmitting(true);
    try {
      const profile = await setAssessmentResults({ ...answers });
      // The plan is a bonus on the victory screen; Home fetches it again.
      const plan = await authApi.getPlan().catch(() => null);
      setDone({ profile, plan });
    } catch (err) {
      // Never mark the wizard done on failure: that left users with no risk
      // profile and no way to notice.
      const detail = err?.response?.data?.detail;
      Alert.alert(t('assess_save_failed'), typeof detail === 'string' ? detail : t('assess_check_connection'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSkip = async () => {
    await setProfileSetupDone(user?.user_id);
    navigation.reset({ index: 0, routes: [{ name: 'MainTab' }] });
  };

  if (done) {
    return <VictoryScreen profile={done.profile} plan={done.plan} isRetake={isRetake} onContinue={finish} />;
  }

  const knowledge = q.kind === 'knowledge';
  const revealed = knowledge && answer !== undefined;
  const right = revealed && rightFor(q);
  let pal = { tone: 'lavender', mood: 'calm', pose: 'rest' };
  if (revealed) pal = right ? { tone: 'lime', mood: 'joy', pose: 'cheer', confetti: true } : { tone: 'coral', mood: 'oops', pose: 'rest' };
  else if (answer !== undefined) pal = { tone: 'lavender', mood: 'happy', pose: 'wave' };
  else if (knowledge) pal = { tone: 'yellow', mood: 'calm', pose: 'rest', badge: 'lightbulb' };

  const stopLabel = t('journey_stop').replace('{current}', currentQ + 1).replace('{total}', QUESTIONS.length);

  const renderOption = (option, index) => {
    const selected = answer === option;
    const isCorrect = revealed && index === q.correct;
    const isWrongPick = revealed && selected && !isCorrect;
    let icon = null;
    if (isCorrect) icon = 'check';
    else if (isWrongPick) icon = 'close';
    else if (selected) icon = 'check';
    return (
      <TouchableTick
        key={index}
        style={[
          styles.option,
          selected && !revealed && styles.optionSelected,
          isCorrect && { backgroundColor: palette.lime },
          isWrongPick && { backgroundColor: palette.coral },
          revealed && !isCorrect && !isWrongPick && { opacity: 0.55 },
        ]}
        onPress={() => handleSelect(option)}
        disabled={revealed}
        accessibilityRole="radio"
        accessibilityState={{ selected, disabled: revealed }}
      >
        <Text style={[styles.optionText, selected && !revealed && styles.optionTextSelected]}>
          {t(`${textKey(q)}_o${index + 1}`)}
        </Text>
        {icon
          ? <MaterialIcons name={icon} size={20} color={selected && !revealed ? '#FFFFFF' : palette.ink} />
          : <View style={styles.ringEmpty} />}
      </TouchableTick>
    );
  };

  return (
    <Screen
      edges={['top', 'bottom']}
      contentStyle={styles.content}
      footer={
        <View style={styles.navRow}>
          <PillButton
            variant="secondary"
            title={t('assess_previous')}
            onPress={() => currentQ > 0 && setCurrentQ(currentQ - 1)}
            disabled={currentQ === 0}
            style={styles.navBtn}
          />
          <PillButton
            title={isLast ? t('journey_finish') : t('assess_next')}
            icon={isLast ? 'flag' : undefined}
            onPress={handleNext}
            loading={submitting}
            style={styles.navBtn}
          />
        </View>
      }
    >
      <Header
        onBack={navigation.canGoBack() ? () => navigation.goBack() : null}
        backLabel={t('auth_back')}
        right={isRetake ? null : (
          <TouchableTick onPress={handleSkip} style={styles.skip} accessibilityRole="button">
            <Text style={styles.skipText}>{t('assess_skip')}</Text>
          </TouchableTick>
        )}
      />

      <View style={styles.intro}>
        <Label>{t('journey_label')}</Label>
        <Title style={styles.title}>{t('journey_title')}</Title>
      </View>

      <View style={styles.roadCard}>
        <JourneyRoad
          total={QUESTIONS.length}
          current={currentQ}
          kinds={KINDS}
          results={results}
          pal={pal}
          label={stopLabel}
        />
      </View>

      <View style={styles.qHead}>
        <Chip label={knowledge ? t('journey_quick_check') : t('journey_about_you')} tone={knowledge ? 'yellow' : 'lavender'} icon={knowledge ? 'lightbulb' : 'person'} />
        <Text style={styles.stopText}>{stopLabel}</Text>
      </View>
      <Text style={styles.questionText} accessibilityRole="header">{t(textKey(q))}</Text>
      <View style={styles.options}>{q.options.map(renderOption)}</View>

      {revealed ? (
        <View style={[styles.feedback, { backgroundColor: right ? palette.lime : '#FFFFFF' }]} accessibilityLiveRegion="polite">
          <View>
            <PillPal size={92} tone={right ? 'lime' : 'coral'} mood={right ? 'joy' : 'oops'} pose={right ? 'cheer' : 'rest'} />
            {right ? <Celebrate fire={burst} spread={120} /> : null}
          </View>
          <View style={{ flex: 1, gap: 6 }}>
            <Text style={styles.feedbackTitle}>{right ? t('journey_correct') : t('journey_wrong')}</Text>
            <Text style={styles.feedbackBody}>{t(`assess_k${q.id}_x`)}</Text>
          </View>
        </View>
      ) : null}

      {!knowledge && answer !== undefined ? (
        <View style={styles.react} accessibilityLiveRegion="polite">
          <MaterialIcons name="favorite" size={16} color={palette.coralInk} />
          <Text style={styles.reactText}>{t(`journey_react_${(currentQ % 4) + 1}`)}</Text>
        </View>
      ) : null}
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };
const WHITE = 'rgba(255,255,255,0.92)';

const styles = StyleSheet.create({
  content: { paddingBottom: 24, gap: 18 },
  intro: { gap: 6 },
  title: { fontSize: 32, lineHeight: 36, letterSpacing: -1 },
  skip: {
    minHeight: 44, paddingHorizontal: 20, borderRadius: radii.full,
    backgroundColor: palette.glass, alignItems: 'center', justifyContent: 'center',
  },
  skipText: { ...text, fontFamily: fonts.medium, fontSize: 15 },
  roadCard: { borderRadius: radii.xl, backgroundColor: palette.glassSoft, paddingHorizontal: 4 },
  qHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  stopText: { ...text, fontSize: 13, color: palette.muted },
  questionText: { ...text, fontSize: 24, lineHeight: 30, letterSpacing: -0.5 },
  options: { gap: 10 },
  option: {
    minHeight: 60, borderRadius: radii.full, backgroundColor: WHITE,
    paddingHorizontal: 24, paddingVertical: 14,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12,
  },
  optionSelected: { backgroundColor: palette.ink },
  optionText: { ...text, fontSize: 16, flex: 1 },
  optionTextSelected: { color: '#FFFFFF', fontFamily: fonts.medium },
  ringEmpty: { width: 20, height: 20, borderRadius: radii.full, borderWidth: 1.5, borderColor: palette.outline },
  feedback: { flexDirection: 'row', alignItems: 'center', gap: 14, borderRadius: radii.xl, padding: 16 },
  feedbackTitle: { ...text, fontFamily: fonts.medium, fontSize: 18 },
  feedbackBody: { ...text, fontSize: 15, lineHeight: 21, color: palette.ink },
  react: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', backgroundColor: WHITE, borderRadius: radii.full, paddingHorizontal: 14, paddingVertical: 8 },
  reactText: { ...text, fontFamily: fonts.medium, fontSize: 14 },
  navRow: { flexDirection: 'row', gap: 12, paddingHorizontal: 20, paddingTop: 8, paddingBottom: 12 },
  navBtn: { flex: 1 },
});
