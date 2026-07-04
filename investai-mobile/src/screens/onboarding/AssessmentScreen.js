import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Animated, PanResponder, SafeAreaView, Dimensions, KeyboardAvoidingView, Platform } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuthStore } from '../../store/authStore';
import { useUser } from '@clerk/clerk-expo';

const { width } = Dimensions.get('window');

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
  const [trackWidth, setTrackWidth] = useState(0);
  const position = useRef(new Animated.Value(value)).current;
  const valRef = useRef(value);

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
        if(trackWidth > 0) {
          const deltaVal = (gestureState.dx / trackWidth) * 100;
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

  return (
    <View style={styles.sliderContainer}>
      <View style={styles.sliderBadge}>
        <Text style={styles.sliderBadgeText}>{valRef.current}%</Text>
      </View>
      <View 
        style={styles.trackWrapper} 
        onLayout={(e) => setTrackWidth(e.nativeEvent.layout.width)}
      >
        <LinearGradient
          colors={['#1976D2', '#E5E7EB']}
          start={{x: 0, y: 0}}
          end={{x: 1, y: 0}}
          style={styles.track}
        />
        <Animated.View
          style={[
            styles.thumb,
            {
              left: position.interpolate({
                inputRange: [0, 100],
                outputRange: ['0%', '100%'],
                extrapolate: 'clamp'
              }),
              transform: [{ translateX: -12 }]
            }
          ]}
          {...panResponder.panHandlers}
        />
      </View>
      <View style={styles.sliderLabels}>
        <Text style={styles.sliderLabel}>Low</Text>
        <Text style={styles.sliderLabel}>Medium</Text>
        <Text style={styles.sliderLabel}>High</Text>
      </View>
    </View>
  );
};

export default function AssessmentScreen({ navigation }) {
  const { user } = useUser();
  const { setProfileSetupDone, setAssessmentResults } = useAuthStore();
  
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState({});
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

  const handleNext = async () => {
    if (currentQ < QUESTIONS.length - 1) {
      setCurrentQ(currentQ + 1);
    } else {
      // Complete
      if (user) {
        await setAssessmentResults(answers);
        await setProfileSetupDone(user.id);
      }
      navigation.navigate('MainTab');
    }
  };

  const handleSkip = async () => {
    if (user) {
      await setProfileSetupDone(user.id);
    }
    navigation.navigate('MainTab');
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

      return (
        <TouchableOpacity 
          key={index} 
          style={[styles.optionCard, isSelected && styles.optionCardSelected]}
          onPress={() => handleSelect(option)}
          activeOpacity={0.7}
        >
          <Text style={styles.optionText}>{option}</Text>
          <View style={currentQuestion.type === 'multi' ? [styles.checkbox, !isSelected && styles.checkboxUnselected] : [styles.radioCircle, !isSelected && styles.radioCircleUnselected]}>
            {isSelected && (
              currentQuestion.type === 'multi' ? 
                <MaterialIcons name="check" size={16} color="#FFF" /> : 
                <View style={styles.radioInner} />
            )}
          </View>
        </TouchableOpacity>
      );
    });
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <MaterialIcons name="arrow-back" size={24} color="#1A1A2E" />
          </TouchableOpacity>
          <Text style={styles.headerTitle} numberOfLines={1}>Financial Literacy & Risk Assessment Wizard</Text>
          <TouchableOpacity onPress={handleSkip}>
            <Text style={styles.exitText}>Skip</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.subtitle}>Financial Profile</Text>
      </View>

      {/* Progress */}
      <View style={styles.progressContainer}>
        <Text style={styles.progressText}>Question {currentQ + 1} of {QUESTIONS.length}</Text>
        <View style={styles.progressBarBg}>
          <Animated.View style={[styles.progressBarFill, { 
            width: progressAnim.interpolate({
              inputRange: [0, 100],
              outputRange: ['0%', '100%']
            }) 
          }]} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Text style={styles.questionText}>{currentQuestion.text}</Text>
        <View style={styles.optionsContainer}>
          {renderOptions()}
        </View>
      </ScrollView>

      {/* Nav Buttons */}
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={styles.navRow}>
          <TouchableOpacity 
            style={[styles.navBtn, styles.navBtnPrev, currentQ === 0 && styles.navBtnDisabled]} 
            onPress={handlePrev}
            disabled={currentQ === 0}
          >
            <Text style={[styles.navBtnTextPrev, currentQ === 0 && { color: '#9CA3AF' }]}>Previous</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.navBtn, styles.navBtnNext]} onPress={handleNext}>
            {currentQ === QUESTIONS.length - 1 ? (
              <>
                <MaterialIcons name="check" size={20} color="#FFF" style={{marginRight: 6}}/>
                <Text style={styles.navBtnTextNext}>Complete</Text>
              </>
            ) : (
              <Text style={styles.navBtnTextNext}>Next</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 16,
    backgroundColor: '#FFFFFF',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: '#1A1A2E',
    textAlign: 'center',
    marginHorizontal: 12,
  },
  exitText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#F44336',
  },
  subtitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1A1A2E',
    marginTop: 16,
  },
  progressContainer: {
    paddingHorizontal: 16,
    paddingBottom: 24,
    backgroundColor: '#FFFFFF',
  },
  progressText: {
    fontSize: 13,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 8,
  },
  progressBarBg: {
    height: 6,
    backgroundColor: '#E5E7EB',
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#1976D2',
    borderRadius: 3,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingBottom: 40,
  },
  questionText: {
    fontSize: 20,
    fontWeight: '600',
    color: '#1A1A2E',
    lineHeight: 28,
    marginTop: 24,
    marginBottom: 24,
  },
  optionsContainer: {
    flex: 1,
  },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1.5,
    borderColor: '#E5E7EB',
  },
  optionCardSelected: {
    backgroundColor: '#EBF5FB',
    borderColor: '#1976D2',
  },
  optionText: {
    fontSize: 15,
    color: '#1A1A2E',
    flex: 1,
  },
  radioCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: '#1976D2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioCircleUnselected: {
    borderColor: '#E5E7EB',
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#1976D2',
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: '#1976D2',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1976D2',
  },
  checkboxUnselected: {
    backgroundColor: 'transparent',
    borderColor: '#E5E7EB',
  },
  navRow: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  navBtn: {
    flex: 1,
    height: 48,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  navBtnPrev: {
    borderWidth: 1.5,
    borderColor: '#1976D2',
  },
  navBtnNext: {
    backgroundColor: '#1976D2',
  },
  navBtnDisabled: {
    borderColor: '#9CA3AF',
  },
  navBtnTextPrev: {
    color: '#1976D2',
    fontSize: 16,
    fontWeight: '600',
  },
  navBtnTextNext: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  sliderContainer: {
    marginTop: 32,
    paddingHorizontal: 8,
  },
  sliderBadge: {
    alignSelf: 'center',
    backgroundColor: '#1976D2',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    marginBottom: 16,
  },
  sliderBadgeText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  trackWrapper: {
    height: 24,
    justifyContent: 'center',
    position: 'relative',
  },
  track: {
    height: 8,
    borderRadius: 4,
    width: '100%',
  },
  thumb: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#FFF',
    borderWidth: 2,
    borderColor: '#1976D2',
    position: 'absolute',
    top: 0,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
    elevation: 3,
  },
  sliderLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  sliderLabel: {
    fontSize: 13,
    color: '#6B7280',
    fontWeight: '500',
  }
});
