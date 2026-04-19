// src/screens/LearnScreen.js
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  StatusBar,
  Dimensions,
  Platform
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAppTheme } from '../hooks/useAppTheme';

const { width } = Dimensions.get('window');

const CATEGORIES = ['Stock Basics', 'Risk Management', 'Technical Analysis', 'Strategies'];

const ARTICLES = [
  {
    id: '1',
    level: 'Beginner',
    levelColor: '#DCFCE7',
    levelTextColor: '#15803D',
    title: 'First Steps: How to pick your first dividend stock',
    stats: '5 min read • 2k views',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDY4fwVa6eSsHh99EbKXqFTX0TneSVVMRy8nHRsYrnCqrIObNcu9XUizyZq0hjlM-mmnB4FpwlP0B3G065pBKG6Zok0dJ3_r9QgYaZKJwRGnjWls-zhI3HKQnvUFmlIRtIBCK_kOZxW2k6uQ5jZB-ZEFN6G0zLQJGQzzgIMBWHgKQ4pa8wmZQ3BWHhu0jPyo8k2oWgjTJxlqaWnwQN57cfrwXv2XJxiZMLWd8Jro8zcayjjY022_L6s6jiX6zIIHugYG6M6fBUlqgSd'
  },
  {
    id: '2',
    level: 'Advanced',
    levelColor: '#FEE2E2',
    levelTextColor: '#B91C1C',
    title: 'Complex Derivatives: Hedging against market volatility',
    stats: '15 min read • 800 views',
    bookmarked: true,
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBDCy78_IWd4JGge_-0ohtAmhUttwlFjgGaUHZLHjqWl5QN8VplWrDZBsTL-oZKWEyomQNPn3cWKtxlrmpd3u_7jPWXin3QvRQpHWGQf0sIsoXXVV7JccPKtBs6UjyWUVwOagYh9nnf3ZtHNyrvpZqZ9HvvYazH3GXkFnciI4XKJiiUMhDKBLx0k7hsZcF7KJwzQ08ck1V0QXy3trACM0smwh-FSEa0i14LVjciN-7Rf5XwGhdV1IVaFCfZOh3JenLfVI-BG8uF4Hf-'
  },
  {
    id: '3',
    level: 'Beginner',
    levelColor: '#DCFCE7',
    levelTextColor: '#15803D',
    title: 'The Magic of Compound Interest Explained',
    stats: '4 min read • 5k views',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDoKPacAHqfhA_g27SxGq5mTxVeIFdext0o8o3DF6pf0FmORd8IkgTVFpnbZGiKYt5_rESCOssuDlDuQyZj354DIf08ofO_GZmKensFizThFcN4SpmwR5m7vHwSNZh0kIqFbqFX6Rlx6CSH_W5O-Kql2P9KApFapGrPzofipJ4av0RXBVvRYN7Gy8bGT3Y2GsbXyMkfOkHv64rH_Ca-U48tu_-wvXEM9FU2igxYPWCdqjT5Gd049ReMGWqY2nPrR7eUO4YqTYidvC3D'
  }
];

export default function LearnScreen({ navigation }) {
  const theme = useAppTheme();
  const [activeCategory, setActiveCategory] = useState('Stock Basics');

  // Hide tab bar when on this screen as requested
  useEffect(() => {
    const parent = navigation.getParent();
    if (parent) {
      parent.setOptions({
        tabBarStyle: { display: 'none' }
      });
    }
    return () => {
      if (parent) {
        parent.setOptions({
          tabBarStyle: undefined // Restore default tab bar when leaving
        });
      }
    };
  }, [navigation]);

  return (
    <View style={[styles.container, { backgroundColor: '#F8FAFC' }]}>
      <StatusBar barStyle="light-content" />
      
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* Header Section */}
        <LinearGradient
          colors={['#4F46E5', '#7C3AED']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.header}
        >
          <SafeAreaView edges={['top']}>
            <View style={styles.headerTop}>
              <TouchableOpacity onPress={() => navigation.goBack()} style={styles.headerIconBtn}>
                <MaterialIcons name="arrow-back-ios" size={20} color="#FFFFFF" />
              </TouchableOpacity>
              <TouchableOpacity style={styles.headerIconBtn}>
                <MaterialIcons name="search" size={24} color="#FFFFFF" />
              </TouchableOpacity>
            </View>
            
            <View style={styles.headerText}>
              <Text style={styles.headerTitle}>Learn</Text>
              <Text style={styles.headerSubtitle}>Master the stock market</Text>
            </View>
          </SafeAreaView>

          {/* Progress Card (Positioned Absolutely) */}
          <View style={[styles.progressCard, styles.shadow]}>
            <View style={styles.progressRow}>
              <View style={styles.progressTextGroup}>
                <View style={styles.bookIcon}>
                  <MaterialIcons name="auto-stories" size={20} color="#4F46E5" />
                </View>
                <View>
                  <Text style={styles.progressTitle}>Your Progress</Text>
                  <Text style={styles.progressStats}>14 of 20 lessons completed</Text>
                </View>
              </View>
              <Text style={styles.progressPercentage}>70%</Text>
            </View>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: '70%' }]} />
            </View>
          </View>
        </LinearGradient>

        <View style={styles.mainContent}>
          {/* Categories */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.categoryScroll}
          >
            {CATEGORIES.map(cat => (
              <TouchableOpacity
                key={cat}
                style={[
                  styles.categoryPill,
                  activeCategory === cat ? styles.categoryPillActive : styles.categoryPillInactive
                ]}
                onPress={() => setActiveCategory(cat)}
              >
                <Text style={[
                  styles.categoryText,
                  activeCategory === cat ? styles.categoryTextActive : styles.categoryTextInactive
                ]}>
                  {cat}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Featured Lesson */}
          <TouchableOpacity style={[styles.featuredCard, styles.shadow]} activeOpacity={0.9}>
            <Image
              source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAMYnyCyVCvfARH2X0P7ihnbXOdO2R5oS3jD3lgsPSyO2Ly94doNh3ZW4LdscrJFn9wWC1gNXluIcs3vfjv2-HQY77yJxsgO1fyiTUzdwEMwZOBH654AQoXkdyWUWjpebl8jO7ZMT6qJd1NBVAcCgTaFb6OOv7mexV75fztAiU7EWeJREQgwMlI08sooxDSDwGJIWOIPoFmVkpLWigxUxX7PpXN1tdud0908QM8SLbbt7pONQvNIEtAZRbkKe73hXQw8wqKrthKRpOb' }}
              style={styles.featuredImage}
            />
            <LinearGradient
              colors={['transparent', 'rgba(0,0,0,0.8)']}
              style={styles.featuredOverlay}
            >
              <Text style={styles.featuredLabel}>FEATURED LESSON</Text>
              <Text style={styles.featuredTitle}>Understanding the Colombo Stock Exchange</Text>
              <View style={styles.featuredMeta}>
                <View style={styles.metaItem}>
                  <MaterialIcons name="schedule" size={14} color="rgba(255,255,255,0.9)" />
                  <Text style={styles.metaText}>12 min</Text>
                </View>
                <View style={styles.metaItem}>
                  <MaterialIcons name="bar-chart" size={14} color="rgba(255,255,255,0.9)" />
                  <Text style={styles.metaText}>Intermediate</Text>
                </View>
              </View>
            </LinearGradient>
          </TouchableOpacity>

          {/* Quiz Card */}
          <LinearGradient
            colors={['#2563EB', '#42A5F5']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={[styles.quizCard, styles.shadow]}
          >
            <View style={styles.quizLeft}>
              <Text style={styles.quizTitle}>Daily Quiz</Text>
              <Text style={styles.quizSubtitle}>Test your knowledge & earn points</Text>
              <TouchableOpacity 
                style={styles.quizBtn}
                onPress={() => navigation.navigate('Assessment', {
                  isEducationQuiz: true,
                  questions: [
                    {
                      id: 'basic-1',
                      header: 'Stock Basics',
                      question: 'What does "Dividends" refer to in investing?',
                      options: ['Company profits shared with shareholders', 'The cost of buying a stock', 'A type of government tax', 'A technical market crash']
                    },
                    {
                      id: 'basic-2',
                      header: 'Common Terms',
                      question: 'What is a "Bull Market"?',
                      options: ['A period of falling stock prices', 'A period of rising stock prices', 'A market where only animals are traded', 'A market with zero volatility']
                    }
                  ]
                })}
              >
                <Text style={styles.quizBtnText}>Start Quiz</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.quizRight}>
              <View style={styles.quizIconCircle}>
                <MaterialCommunityIcons name="psychology" size={32} color="#FFFFFF" />
              </View>
            </View>
          </LinearGradient>

          {/* Top Articles Section */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Top Articles</Text>
            <TouchableOpacity>
              <Text style={styles.seeAllText}>See All</Text>
            </TouchableOpacity>
          </View>

          {ARTICLES.map(article => (
            <TouchableOpacity key={article.id} style={[styles.articleCard, styles.shadow]} activeOpacity={0.7}>
              <Image source={{ uri: article.image }} style={styles.articleImage} />
              <View style={styles.articleContent}>
                <View style={styles.articleHeader}>
                  <View style={[styles.levelBadge, { backgroundColor: article.levelColor }]}>
                    <Text style={[styles.levelText, { color: article.levelTextColor }]}>{article.level.toUpperCase()}</Text>
                  </View>
                  <MaterialIcons 
                    name={article.bookmarked ? "bookmark" : "bookmark-outline"} 
                    size={18} 
                    color={article.bookmarked ? "#4F46E5" : "#CBD5E1"} 
                  />
                </View>
                <Text style={styles.articleTitle} numberOfLines={2}>{article.title}</Text>
                <Text style={styles.articleStats}>{article.stats}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 40,
  },
  header: {
    paddingBottom: 60,
    borderBottomLeftRadius: 40,
    borderBottomRightRadius: 40,
    paddingHorizontal: 24,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    marginBottom: 20,
  },
  headerIconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerText: {
    marginBottom: 10,
  },
  headerTitle: {
    fontSize: 32,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -0.5,
  },
  headerSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
    fontWeight: '500',
  },
  progressCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
    marginTop: 20,
    marginBottom: -40,
  },
  progressRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  progressTextGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  bookIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  progressTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1E293B',
  },
  progressStats: {
    fontSize: 12,
    color: '#64748B',
    fontWeight: '500',
  },
  progressPercentage: {
    fontSize: 16,
    fontWeight: '800',
    color: '#4F46E5',
  },
  progressBarBg: {
    height: 10,
    backgroundColor: '#F1F5F9',
    borderRadius: 5,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#4F46E5',
    borderRadius: 5,
  },
  mainContent: {
    paddingTop: 60,
    paddingHorizontal: 24,
  },
  categoryScroll: {
    marginBottom: 24,
    gap: 12,
  },
  categoryPill: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 25,
    justifyContent: 'center',
    alignItems: 'center',
  },
  categoryPillActive: {
    backgroundColor: '#4F46E5',
  },
  categoryPillInactive: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#F1F5F9',
  },
  categoryText: {
    fontSize: 14,
    fontWeight: '600',
  },
  categoryTextActive: {
    color: '#FFFFFF',
  },
  categoryTextInactive: {
    color: '#64748B',
  },
  featuredCard: {
    width: '100%',
    height: 180,
    borderRadius: 24,
    overflow: 'hidden',
    marginBottom: 24,
  },
  featuredImage: {
    width: '100%',
    height: '100%',
    position: 'absolute',
  },
  featuredOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    padding: 20,
  },
  featuredLabel: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.5,
    marginBottom: 4,
  },
  featuredTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '800',
    lineHeight: 26,
    marginBottom: 12,
  },
  featuredMeta: {
    flexDirection: 'row',
    gap: 16,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  metaText: {
    color: 'rgba(255,255,255,0.9)',
    fontSize: 12,
    fontWeight: '600',
  },
  quizCard: {
    padding: 24,
    borderRadius: 24,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 32,
  },
  quizLeft: {
    flex: 1,
  },
  quizTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 4,
  },
  quizSubtitle: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 12,
  },
  quizBtn: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    alignSelf: 'flex-start',
  },
  quizBtnText: {
    color: '#2563EB',
    fontSize: 12,
    fontWeight: '800',
  },
  quizRight: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#1E293B',
  },
  seeAllText: {
    fontSize: 14,
    color: '#4F46E5',
    fontWeight: '700',
  },
  articleCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    flexDirection: 'row',
    gap: 16,
    marginBottom: 12,
  },
  articleImage: {
    width: 80,
    height: 80,
    borderRadius: 16,
  },
  articleContent: {
    flex: 1,
    justifyContent: 'space-between',
  },
  articleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  levelBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  levelText: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  articleTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1E293B',
    lineHeight: 18,
  },
  articleStats: {
    fontSize: 10,
    color: '#94A3B8',
    fontWeight: '600',
  },
  shadow: {
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.05,
        shadowRadius: 10,
      },
      android: {
        elevation: 3,
      },
    }),
  },
});
