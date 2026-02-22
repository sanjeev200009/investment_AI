import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, typography } from '../../theme/theme';

export default function OnboardingScreen({ navigation }) {
  const scheme = 'light'; // Defaulting to light as per theme setup
  const themeColors = colors(scheme);
  const themeTypography = typography(scheme);

  return (
    <View style={[styles.container, { backgroundColor: themeColors.bgApp }]}>
      <Text style={[styles.text, { color: themeColors.textPrimary }]}>Onboarding Screen</Text>
      <TouchableOpacity
        style={styles.button}
        onPress={() => navigation.navigate('Login')}
      >
        <Text style={styles.buttonText}>Go to Login</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  text: { fontSize: 24, fontWeight: 'bold', marginBottom: 20 },
  button: {
    backgroundColor: '#3B82F6',
    paddingHorizontal: 30,
    paddingVertical: 15,
    borderRadius: 12,
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '700',
  }
});
