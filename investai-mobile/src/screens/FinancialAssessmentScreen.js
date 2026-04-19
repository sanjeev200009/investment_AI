// src/screens/FinancialAssessmentScreen.js
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  StatusBar,
  Dimensions,
  Platform,
  LayoutAnimation
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';
import { useAuthStore } from '../store/authStore';

const DEFAULT_QUESTIONS = [
  {
    id: 'goal',
    header: 'Financial Profile',
    question: 'What is your primary investment goal?',
    options: ['Retirement', 'Wealth Growth', 'Major Purchase', 'Income Generation']
  },
  {
    id: 'risk',
    header: 'Risk Tolerance',
    question: 'How do you feel about market volatility?',
    options: ['Conservative (Low Risk)', 'Moderate', 'Growth (Aggressive)', 'Speculative']
  },
  {
    id: 'experience',
    header: 'Investment Knowledge',
    question: 'How would you rate your trading experience?',
    options: ['Complete Beginner', 'I know the basics', 'Intermediate Trader', 'Expert Investor']
  },
  {
    id: 'savings',
    header: 'Financial Context',
    question: 'What is your estimated monthly investable amount?',
    options: ['< Rs. 10,000', 'Rs. 10,000 - 50,000', 'Rs. 50,000 - 100,000', '> Rs. 100,000']
  }
];

export default function FinancialAssessmentScreen({ route, navigation }) {
  const theme = useAppTheme();
  const setAssessmentResults = useAuthStore(state => state.setAssessmentResults);
  
  // Accept custom questions if provided (e.g. for educational quizzes)
  const questions = route.params?.questions || DEFAULT_QUESTIONS;
  const isEducationQuiz = route.params?.isEducationQuiz || false;

  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [isFinalizing, setIsFinalizing] = useState(false);

  const currentQuestion = questions[currentIndex];
  const progress = ((currentIndex + 1) / questions.length) * 100;

  const handleSelectOption = (option) => {
    setAnswers(prev => ({ ...prev, [currentQuestion.id]: option }));
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
      setCurrentIndex(currentIndex + 1);
    } else {
      // Completed!
      if (!isEducationQuiz) {
        setIsFinalizing(true);
        // Show success state for a moment to feel premium
        setTimeout(() => {
          setAssessmentResults(answers);
        }, 1500);
      } else {
        navigation.goBack();
      }
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
      setCurrentIndex(currentIndex - 1);
    }
  };

  const isSelected = (option) => answers[currentQuestion.id] === option;

  return (
    <View style={[styles.container, { backgroundColor: '#FFFFFF' }]}>
      <StatusBar barStyle="dark-content" />
      
      {/* iOS Style Status Bar Info */}
      <View style={styles.statusBarMock}>
        <Text style={styles.timeText}>9:41</Text>
        <View style={styles.statusIcons}>
          <MaterialIcons name="signal-cellular-4-bar" size={14} color="#000" />
          <MaterialIcons name="wifi" size={14} color="#000" />
          <MaterialIcons name="battery-full" size={16} color="#000" />
        </View>
      </View>

      {/* Progress Bar Container */}
      <View style={styles.progressContainer}>
        <View style={styles.progressBarBg}>
          <View style={[styles.progressBarFill, { width: `${progress}%` }]} />
        </View>
        <Text style={styles.progressLabel}>Question {currentIndex + 1} of {questions.length}</Text>
      </View>

      <SafeAreaView style={styles.mainArea} edges={['bottom']}>
        {isFinalizing ? (
          <View style={styles.finalizingContent}>
             <MaterialIcons name="check-circle" size={80} color="#1565C0" />
             <Text style={styles.finalizingTitle}>Profile Customized!</Text>
             <Text style={styles.finalizingSub}>Take control of your financial future.</Text>
          </View>
        ) : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
            <Text style={styles.headerText}>{currentQuestion.header}</Text>
            <Text style={styles.questionText}>{currentQuestion.question}</Text>

            <View style={styles.optionsList}>
              {currentQuestion.options.map((option, idx) => (
                <TouchableOpacity
                  key={idx}
                  activeOpacity={0.7}
                  style={[
                    styles.optionCard,
                    isSelected(option) && styles.optionCardSelected
                  ]}
                  onPress={() => handleSelectOption(option)}
                >
                  <View style={[
                    styles.customRadio,
                    isSelected(option) && styles.customRadioSelected
                  ]}>
                    {isSelected(option) && <View style={styles.radioInner} />}
                  </View>
                  <Text style={[
                    styles.optionText,
                    isSelected(option) && styles.optionTextSelected
                  ]}>
                    {option}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        )}

        {!isFinalizing && (
          <View style={styles.footer}>
            <TouchableOpacity 
              style={[styles.btn, styles.prevBtn]} 
              onPress={handlePrevious}
              disabled={currentIndex === 0}
            >
              <Text style={[styles.btnText, styles.prevBtnText, currentIndex === 0 && { opacity: 0.3 }]}>
                Previous
              </Text>
            </TouchableOpacity>

            <TouchableOpacity 
              style={[styles.btn, styles.nextBtn, !answers[currentQuestion.id] && styles.nextBtnDisabled]} 
              onPress={handleNext}
              disabled={!answers[currentQuestion.id]}
            >
              <Text style={styles.btnText}>
                {currentIndex === questions.length - 1 ? 'Finish' : 'Next'}
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </SafeAreaView>
      
      {/* Home Indicator Mock */}
      <View style={styles.homeIndicator} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  statusBarMock: {
    height: 44,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    alignItems: 'center',
    paddingTop: 10,
  },
  timeText: {
    fontSize: 12,
    fontWeight: '700',
  },
  statusIcons: {
    flexDirection: 'row',
    gap: 4,
    alignItems: 'center',
  },
  progressContainer: {
    marginTop: 8,
  },
  progressBarBg: {
    height: 6,
    backgroundColor: '#F3F4F6',
    width: '100%',
  },
  progressBarFill: {
    height: 6,
    backgroundColor: '#1565C0',
  },
  progressLabel: {
    fontSize: 12,
    color: '#6B7280',
    fontWeight: '500',
    marginLeft: 24,
    marginTop: 8,
  },
  mainArea: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 100,
  },
  headerText: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1565C0',
    marginBottom: 24,
  },
  questionText: {
    fontSize: 22,
    fontWeight: '800',
    color: '#212121',
    lineHeight: 30,
    marginBottom: 32,
  },
  optionsList: {
    gap: 16,
  },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 20,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#E5E7EB',
    backgroundColor: '#FFFFFF',
  },
  optionCardSelected: {
    borderColor: '#1976D2',
    backgroundColor: '#E3F2FD',
  },
  customRadio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: '#D1D5DB',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  customRadioSelected: {
    borderColor: '#1976D2',
  },
  radioInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#1976D2',
  },
  optionText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#4B5563',
  },
  optionTextSelected: {
    color: '#1565C0',
  },
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    padding: 24,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
    gap: 16,
  },
  btn: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  btnText: {
    fontSize: 16,
    fontWeight: '700',
  },
  prevBtn: {
    borderWidth: 2,
    borderColor: '#1565C0',
  },
  prevBtnText: {
    color: '#1565C0',
  },
  nextBtn: {
    backgroundColor: '#1565C0',
    shadowColor: '#1565C0',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  nextBtnDisabled: {
    backgroundColor: '#9CA3AF',
    shadowOpacity: 0,
    elevation: 0,
  },
  nextBtnText: {
    color: '#FFFFFF',
  },
  homeIndicator: {
    position: 'absolute',
    bottom: 8,
    alignSelf: 'center',
    width: 128,
    height: 5,
    borderRadius: 10,
    backgroundColor: '#E5E7EB',
  },
  finalizingContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  finalizingTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#212121',
    marginTop: 24,
    marginBottom: 12,
  },
  finalizingSub: {
    fontSize: 16,
    color: '#6B7280',
    textAlign: 'center',
    lineHeight: 24,
  }
});
