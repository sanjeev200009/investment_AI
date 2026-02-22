import React from 'react';
import { View, Text, StyleSheet, StatusBar } from 'react-native';
import { useAppTheme } from '../../hooks/useAppTheme';
import AppButton from '../../components/AppButton';

export default function OnboardingScreen({ navigation }) {
  const theme = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar barStyle={theme.isDark ? "light-content" : "dark-content"} />

      <View style={styles.content}>
        <Text style={[styles.title, { color: theme.colors.textPrimary, fontSize: theme.typography.sizes.h1 }]}>InvestAI</Text>
        <Text style={[styles.subtitle, { color: theme.colors.textSecondary, fontSize: theme.typography.sizes.body1 }]}>
          Your journey to smarter investing starts here.
        </Text>
      </View>

      <View style={styles.footer}>
        <AppButton
          title="Get Started"
          onPress={() => navigation.navigate('Login')}
          style={styles.button}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'space-between',
    padding: 32,
    paddingTop: 100,
    paddingBottom: 60,
  },
  content: {
    alignItems: 'center',
  },
  title: {
    fontWeight: '800',
    marginBottom: 16,
    letterSpacing: -1,
  },
  subtitle: {
    textAlign: 'center',
    lineHeight: 24,
  },
  footer: {
    width: '100%',
  },
  button: {
    // Custom button tweaks if needed
  }
});
