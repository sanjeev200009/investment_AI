import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, Animated, PanResponder, KeyboardAvoidingView, Platform, Alert } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { Screen, Header, PillButton, Title, Label } from '../../components/ui';
import { PillPal } from '../../components/PillPals';
import TouchableTick from '../../components/TouchableTick';
import { palette, fonts, radii } from '../../theme/tokens';
import { useAuthStore } from '../../store/authStore';
import { useT } from '../../store/languageStore';

const KNOB_HIT = 44; // touch target around the slider knob
const KNOB = 28;

// Must stay identical to the canonical bank in
// investai-backend/app/services/risk_scoring.py, which is what scores these
// answers. It is also served by GET /me/assessment/questions. A mismatched
// option string is no longer scored as zero — the backend rejects it with a 422
// naming the question, which surfaces in handleNext's Alert below.
// Only the display is translated: `text` shows as t(`assess_q${id}`) and each
// option as t(`assess_q${id}_o${index + 1}`), while the English option string
// is what gets stored in `answers` and sent. Reordering options means
// renumbering those keys in src/i18n/screens/auth.js.
const QUESTIONS = [
  { id: 1, text: "What is your primary investment goal?", type: "single", options: ["Retirement", "Wealth Growth", "Major Purchase (e.g., home)", "Income Generation"] },
  { id: 2, text: "How comfortable are you with potential short-term fluctuations in your investment value?", type: "single", options: ["Not comfortable at all", "Slightly comfortable", "Moderately comfortable", "Very comfortable"] },
  { id: 3, text: "How long do you plan to keep your investments?", type: "single", options: ["Less than 1 year", "1–3 years", "3–5 years", "5+ years"] },
  { id: 4, text: "Have you invested in stocks before?", type: "single", options: ["Never", "Once or twice", "Occasionally", "Regularly"] },
  { id: 5, text: "What is your monthly income range (LKR)?", type: "single", options: ["Below 50,000", "50,000–100,000", "100,000–250,000", "Above 250,000"] },
  { id: 6, text: "How much of your savings are you willing to invest?", type: "single", options: ["Less than 10%", "10–25%", "25–50%", "More than 50%"] },
  { id: 7, text: "Do you understand what a P/E ratio is?", type: "single", options: ["Yes, completely", "Somewhat", "I've heard of it", "No"] },
  { id: 8, text: "How would you react if your portfolio dropped 20% in one month?", type: "single", options: ["Sell everything", "Sell some", "Hold", "Buy more"] },
  { id: 9, text: "How often do you want to check your investments?", type: "single", options: ["Multiple times a day", "Daily", "Weekly", "Monthly"] },
  { id: 10, text: "What is your preferred investment style?", type: "single", options: ["Very safe (bonds/FDs)", "Balanced", "Growth-focused", "High risk / High reward"] },
  { id: 11, text: "What is your risk tolerance?", type: "slider" },
  { id: 12, text: "Do you follow financial news regularly?", type: "single", options: ["Yes, daily", "Few times a week", "Rarely", "Never"] },
  { id: 13, text: "Which sectors interest you most?", type: "multi", options: ["Banking & Finance", "Technology", "Healthcare", "Energy", "Consumer Goods"] },
  { id: 14, text: "What is your preferred language for investment guidance?", type: "single", options: ["English", "Sinhala", "Tamil"] },
  { id: 15, text: "How did you hear about InvestAI?", type: "single", options: ["Social Media", "Friend/Family", "University", "Other"] }
];

const RiskSlider = ({ value = 50, onChange }) => {
  const [trackWidth, setTrackWidthState] = useState(0);
  // The PanResponder below is created once, so it closed over the first
  // render's trackWidth (0) and every drag was ignored: each user submitted 50.
  // It reads this ref instead.
  const trackWidthRef = useRef(0);
  const setTrackWidth = (w) => { trackWidthRef.current = w; setTrackWidthState(w); };
  const position = useRef(new Animated.Value(value)).current;
  const valRef = useRef(value);
  const { t } = useT();

  useEffect(() => {
    position.setValue(value);
    valRef.current = value;
  }, []);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        position.setOffset(position._value);
        position.setValue(0);
      },
      onPanResponderMove: (e, gestureState) => {
        const width = trackWidthRef.current;
        if (width > 0) {
          const deltaVal = (gestureState.dx / width) * 100;
          position.setValue(deltaVal);
          let raw = position._offset + deltaVal;
          raw = Math.max(0, Math.min(100, Math.round(raw)));
          if (raw !== valRef.current) {
            valRef.current = raw;
            onChange(raw);
          }
        }
      },
      onPanResponderRelease: () => {
        position.flattenOffset();
        let raw = position._value;
        raw = Math.max(0, Math.min(100, Math.round(raw)));
        position.setValue(raw);
        onChange(raw);
      }
    })
  ).current;

  const pct = position.interpolate({
    inputRange: [0, 100],
    outputRange: ['0%', '100%'],
    extrapolate: 'clamp'
  });

  return (
    <View
      style={styles.sliderContainer}
      accessible
      accessibilityLabel={t('assess_q11')}
      accessibilityValue={{ min: 0, max: 100, now: valRef.current }}
    >
      <View style={styles.sliderBadge}>
        <Text style={styles.sliderBadgeText}>{valRef.current}%</Text>
      </View>
      <View
        style={styles.trackWrapper}
        onLayout={(e) => setTrackWidth(e.nativeEvent.layout.width)}
      >
        <View style={styles.track}>
          <Animated.View style={[styles.trackFill, { width: pct }]} />
        </View>
        <Animated.View
          style={[styles.thumbHit, { left: pct, transform: [{ translateX: -KNOB_HIT / 2 }] }]}
          {...panResponder.panHandlers}
        >
          <View style={styles.thumb} />
        </Animated.View>
      </View>
      <View style={styles.sliderLabels}>
        <Text style={styles.sliderLabel}>{t('assess_low')}</Text>
        <Text style={styles.sliderLabel}>{t('assess_medium')}</Text>
        <Text style={styles.sliderLabel}>{t('assess_high')}</Text>
      </View>
    </View>
  );
};

export default function AssessmentScreen({ navigation, route }) {
  // Also opened from Profile to retake it; that copy returns to Profile when
  // done instead of entering the app, and has nothing to skip.
  const isRetake = route?.name === 'RetakeAssessment';
  // Identity comes from the backend user row, not Clerk. `user.user_id` is the
  // same UUID the API authorises against, so the per-user
  // `profile_setup_done_<id>` flag now keys on the real account.
  const user = useAuthStore(state => state.user);
  const setProfileSetupDone = useAuthStore(state => state.setProfileSetupDone);
  const setAssessmentResults = useAuthStore(state => state.setAssessmentResults);
  const { t } = useT();

  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const progressAnim = useRef(new Animated.Value(0)).current;

  const currentQuestion = QUESTIONS[currentQ];

  useEffect(() => {
    Animated.timing(progressAnim, {
      toValue: ((currentQ + 1) / QUESTIONS.length) * 100,
      duration: 300,
      useNativeDriver: false,
    }).start();
  }, [currentQ]);

  const handleSelect = (option) => {
    if (currentQuestion.type === 'single') {
      setAnswers({ ...answers, [currentQuestion.id]: option });
    } else if (currentQuestion.type === 'multi') {
      const currentSelections = answers[currentQuestion.id] || [];
      if (currentSelections.includes(option)) {
        setAnswers({ ...answers, [currentQuestion.id]: currentSelections.filter(i => i !== option) });
      } else {
        setAnswers({ ...answers, [currentQuestion.id]: [...currentSelections, option] });
      }
    }
  };

  // The slider always has a value, so only the choice questions can be blank.
  const isAnswered = () => {
    const a = answers[currentQuestion.id];
    if (currentQuestion.type === 'slider') return true;
    if (currentQuestion.type === 'multi') return Array.isArray(a) && a.length > 0;
    return a !== undefined && a !== null && a !== '';
  };

  const handleNext = async () => {
    if (!isAnswered()) {
      // The backend needs at least 60% of the scored weight to return a
      // reliable score, so gaps are refused here rather than at submit time
      // where the user has lost the context of which question they skipped.
      Alert.alert(t('assess_please_answer'), t('assess_please_answer_msg'));
      return;
    }

    if (currentQ < QUESTIONS.length - 1) {
      setCurrentQ(currentQ + 1);
      return;
    }

    if (submitting) return;
    setSubmitting(true);
    try {
      // Sliders default to 50 in the UI but are only in `answers` once dragged;
      // send the displayed value so the score reflects what the user saw.
      const payload = { ...answers };
      QUESTIONS.forEach(q => {
        if (q.type === 'slider' && payload[q.id] === undefined) payload[q.id] = 50;
      });

      await setAssessmentResults(payload);
      if (isRetake) {
        navigation.goBack();
        return;
      }
      await setProfileSetupDone(user?.user_id);
      navigation.reset({ index: 0, routes: [{ name: 'MainTab' }] });
    } catch (err) {
      // Never mark the wizard done on failure — that was the old behaviour and
      // it left users with no risk profile and no way to notice.
      const detail = err?.response?.data?.detail;
      Alert.alert(
        t('assess_save_failed'),
        typeof detail === 'string'
          ? detail
          : t('assess_check_connection')
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleSkip = async () => {
    await setProfileSetupDone(user?.user_id);
    navigation.reset({ index: 0, routes: [{ name: 'MainTab' }] });
  };

  const handlePrev = () => {
    if (currentQ > 0) {
      setCurrentQ(currentQ - 1);
    }
  };

  const renderOptions = () => {
    if (currentQuestion.type === 'slider') {
      return (
        <RiskSlider 
          value={answers[currentQuestion.id] !== undefined ? answers[currentQuestion.id] : 50} 
          onChange={(val) => setAnswers({ ...answers, [currentQuestion.id]: val })} 
        />
      );
    }

    return currentQuestion.options.map((option, index) => {
      let isSelected = false;
      if (currentQuestion.type === 'single') {
        isSelected = answers[currentQuestion.id] === option;
      } else if (currentQuestion.type === 'multi') {
        isSelected = (answers[currentQuestion.id] || []).includes(option);
      }

      const multi = currentQuestion.type === 'multi';
      return (
        <TouchableTick
          key={index}
          style={[styles.option, isSelected && styles.optionSelected]}
          onPress={() => handleSelect(option)}
          accessibilityRole={multi ? 'checkbox' : 'radio'}
          accessibilityState={multi ? { checked: isSelected } : { selected: isSelected }}
        >
          <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>{t(`assess_q${currentQuestion.id}_o${index + 1}`)}</Text>
          {isSelected
            ? <MaterialIcons name="check" size={20} color="#FFFFFF" />
            : <View style={multi ? styles.boxEmpty : styles.ringEmpty} />}
        </TouchableTick>
      );
    });
  };

  const progress = progressAnim.interpolate({
    inputRange: [0, 100],
    outputRange: ['0%', '100%']
  });

  return (
    <Screen
      edges={['top', 'bottom']}
      contentStyle={styles.content}
      footer={
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <View style={styles.navRow}>
            <PillButton
              variant="secondary"
              title={t('assess_previous')}
              onPress={handlePrev}
              disabled={currentQ === 0}
              style={styles.navBtn}
            />
            <PillButton
              title={currentQ === QUESTIONS.length - 1 ? t('assess_complete') : t('assess_next')}
              icon={currentQ === QUESTIONS.length - 1 ? 'check' : undefined}
              onPress={handleNext}
              loading={submitting}
              style={styles.navBtn}
            />
          </View>
        </KeyboardAvoidingView>
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

      <View style={styles.introRow}>
        <View style={[styles.intro, { flex: 1 }]}>
          <Label>{t('assess_header')}</Label>
          <Title style={styles.title}>{t('assess_subtitle')}</Title>
        </View>
        <PillPal tone="lavender" mood="calm" badge="quiz" size={120} />
      </View>

      {/* Progress */}
      <View style={styles.progress}>
        <Text style={styles.progressText}>{t('assess_progress').replace('{current}', currentQ + 1).replace('{total}', QUESTIONS.length)}</Text>
        <View style={styles.progressTrack}>
          <Animated.View style={[styles.progressFill, { width: progress }]} />
        </View>
      </View>

      <Text style={styles.questionText} accessibilityRole="header">{t(`assess_q${currentQuestion.id}`)}</Text>
      <View style={styles.options}>
        {renderOptions()}
      </View>
    </Screen>
  );
}

const text = { color: palette.ink, fontFamily: fonts.regular };
const WHITE = 'rgba(255,255,255,0.92)';

const styles = StyleSheet.create({
  content: { paddingBottom: 24, gap: 24 },
  intro: { gap: 6 },
  introRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { fontSize: 40, lineHeight: 44, letterSpacing: -1.5 },
  skip: {
    minHeight: 44, paddingHorizontal: 20, borderRadius: radii.full,
    backgroundColor: palette.glass, alignItems: 'center', justifyContent: 'center',
  },
  skipText: { ...text, fontFamily: fonts.medium, fontSize: 15 },
  progress: { gap: 10 },
  progressText: { ...text, fontSize: 13, color: palette.muted },
  progressTrack: { height: 12, borderRadius: radii.full, backgroundColor: WHITE, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: radii.full, backgroundColor: palette.ink },
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
  boxEmpty: { width: 20, height: 20, borderRadius: 6, borderWidth: 1.5, borderColor: palette.outline },
  navRow: { flexDirection: 'row', gap: 12, paddingHorizontal: 20, paddingTop: 8, paddingBottom: 12 },
  navBtn: { flex: 1 },
  sliderContainer: { marginTop: 16, gap: 16 },
  sliderBadge: {
    alignSelf: 'center', backgroundColor: palette.ink, borderRadius: radii.full,
    paddingHorizontal: 18, paddingVertical: 8,
  },
  sliderBadgeText: { color: '#FFFFFF', fontFamily: fonts.medium, fontSize: 18, fontVariant: ['tabular-nums'] },
  trackWrapper: { height: KNOB_HIT, justifyContent: 'center' },
  track: { height: 12, borderRadius: radii.full, backgroundColor: WHITE, overflow: 'hidden' },
  trackFill: { height: '100%', borderRadius: radii.full, backgroundColor: palette.outline },
  thumbHit: {
    position: 'absolute', top: 0, width: KNOB_HIT, height: KNOB_HIT,
    alignItems: 'center', justifyContent: 'center',
  },
  thumb: { width: KNOB, height: KNOB, borderRadius: radii.full, backgroundColor: palette.ink },
  sliderLabels: { flexDirection: 'row', justifyContent: 'space-between' },
  sliderLabel: { ...text, fontFamily: fonts.medium, fontSize: 13, color: palette.muted },
});
