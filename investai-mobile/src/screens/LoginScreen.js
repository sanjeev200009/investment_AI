import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography } from '../theme/theme';

export default function LoginScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>LoginScreen</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.bgApp },
  text: { ...typography.sectionHead, color: colors.textPrimary },
});
