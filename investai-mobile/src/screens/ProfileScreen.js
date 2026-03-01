import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image, SafeAreaView, Switch, Platform, StatusBar } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';
import { MaterialIcons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function ProfileScreen({ navigation }) {
  const theme = useAppTheme();
  const isDark = theme.isDark;

  // Adaptive colors based on theme.tokens
  const colors = {
    primary: theme.colors.primary,
    background: theme.colors.background,
    surface: theme.isDark ? '#1E293B80' : '#FFFFFF', // Translucent slate in dark, white in light
    textPrimary: theme.colors.textPrimary,
    textSecondary: theme.colors.textSecondary,
    border: theme.colors.border,
    error: '#EF4444',
    iconBg: theme.isDark ? 'rgba(0, 82, 255, 0.1)' : '#EFF6FF',
  };

  const [notifications, setNotifications] = useState({
    priceAlerts: true,
    news: true,
    education: false,
  });

  const [biometric, setBiometric] = useState(true);

  const handleLogout = async () => {
    await AsyncStorage.removeItem('token');
    navigation.replace('Splash');
  };

  const renderSettingItem = ({ icon, label, rightElement, onPress, isLast }) => (
    <TouchableOpacity
      style={[
        styles.settingItem,
        !isLast && { borderBottomWidth: 1, borderBottomColor: colors.border }
      ]}
      onPress={onPress}
      disabled={!onPress}
    >
      <View style={[styles.iconContainer, { backgroundColor: colors.iconBg }]}>
        <MaterialIcons name={icon} size={22} color={colors.primary} />
      </View>
      <Text style={[styles.settingLabel, { color: colors.textPrimary }]}>{label}</Text>
      {rightElement || <MaterialIcons name="chevron-right" size={24} color={isDark ? '#475569' : '#CBD5E1'} />}
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <StatusBar barStyle={isDark ? 'light-content' : 'dark-content'} />

      {/* Sticky Header */}
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <MaterialIcons name="arrow-back-ios" size={20} color={colors.primary} />
          <Text style={[styles.backText, { color: colors.primary }]}>Back</Text>
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.textPrimary }]}>Profile & Settings</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* User Profile Section */}
        <View style={styles.profileSection}>
          <View style={styles.avatarWrapper}>
            <Image
              source={{ uri: "https://lh3.googleusercontent.com/aida-public/AB6AXuChaExWtlG1lTmRTx_x_UZVPhWuAUabzgVGro4H_Iu2Ww0P44yoLgfSFUAeky0An7I5qPPXaM1m8fvxJeLnpGH3662-Nm3Sk3i3sQsQYx4EIf9S3Sk-PrH3Rd6hLEKFZlw8pFfvF_PkdS9mcwcQ0GHBHch3IogwaoPaP6e6NsWYgOZ_q1ul0ufLmw5e7FsCkxHb445rNQYc-KvbGcbhZ692oMs4oEzWXIb4JmBRiQMVVpKYTpFxlrR-1jjkQShPnYity1Rc510Mj68" }}
              style={[styles.avatar, { borderColor: isDark ? colors.border : '#FFFFFF' }]}
            />
            <TouchableOpacity style={[styles.cameraBtn, { backgroundColor: colors.primary, borderColor: isDark ? colors.background : '#FFFFFF' }]}>
              <MaterialIcons name="photo-camera" size={18} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
          <Text style={[styles.userName, { color: colors.textPrimary }]}>Sanjaya</Text>
          <Text style={[styles.userEmail, { color: colors.textSecondary }]}>Sanjaya@email.com</Text>
        </View>

        {/* Preferences Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>PREFERENCES</Text>
          <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {renderSettingItem({
              icon: 'language',
              label: 'Language',
              rightElement: (
                <View style={styles.selector}>
                  <Text style={[styles.selectorText, { color: colors.textSecondary }]}>English</Text>
                  <MaterialIcons name="arrow-drop-down" size={20} color={colors.textSecondary} />
                </View>
              )
            })}

            <View style={styles.expandableSection}>
              <View style={styles.subHeader}>
                <View style={[styles.iconContainer, { backgroundColor: colors.iconBg }]}>
                  <MaterialIcons name="notifications" size={22} color={colors.primary} />
                </View>
                <Text style={[styles.settingLabel, { color: colors.textPrimary }]}>Notifications</Text>
              </View>

              <View style={styles.subContent}>
                <View style={styles.toggleRow}>
                  <Text style={[styles.toggleLabel, { color: colors.textSecondary }]}>Price Alerts</Text>
                  <Switch
                    value={notifications.priceAlerts}
                    onValueChange={(v) => setNotifications(prev => ({ ...prev, priceAlerts: v }))}
                    trackColor={{ false: '#E2E8F0', true: colors.primary }}
                    thumbColor="#FFFFFF"
                  />
                </View>
                <View style={styles.toggleRow}>
                  <Text style={[styles.toggleLabel, { color: colors.textSecondary }]}>News & Insights</Text>
                  <Switch
                    value={notifications.news}
                    onValueChange={(v) => setNotifications(prev => ({ ...prev, news: v }))}
                    trackColor={{ false: '#E2E8F0', true: colors.primary }}
                    thumbColor="#FFFFFF"
                  />
                </View>
                <View style={[styles.toggleRow, { borderBottomWidth: 0 }]}>
                  <Text style={[styles.toggleLabel, { color: colors.textSecondary }]}>Education</Text>
                  <Switch
                    value={notifications.education}
                    onValueChange={(v) => setNotifications(prev => ({ ...prev, education: v }))}
                    trackColor={{ false: '#E2E8F0', true: colors.primary }}
                    thumbColor="#FFFFFF"
                  />
                </View>
              </View>
            </View>
          </View>
        </View>

        {/* Security Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>SECURITY</Text>
          <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {renderSettingItem({
              icon: 'lock',
              label: 'Change Password',
              onPress: () => { }
            })}
            {renderSettingItem({
              icon: 'fingerprint',
              label: 'Biometric Login',
              isLast: true,
              rightElement: (
                <Switch
                  value={biometric}
                  onValueChange={setBiometric}
                  trackColor={{ false: '#E2E8F0', true: colors.primary }}
                  thumbColor="#FFFFFF"
                />
              )
            })}
          </View>
        </View>

        {/* Support Section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>SUPPORT & LEGAL</Text>
          <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {renderSettingItem({ icon: 'help', label: 'Help Center', onPress: () => { } })}
            {renderSettingItem({ icon: 'description', label: 'Privacy Policy', onPress: () => { } })}
            {renderSettingItem({ icon: 'gavel', label: 'Terms of Service', onPress: () => { }, isLast: true })}
          </View>
        </View>

        {/* Logout Section */}
        <View style={[styles.section, { paddingTop: 16 }]}>
          <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
              <MaterialIcons name="logout" size={22} color={colors.error} />
              <Text style={[styles.logoutText, { color: colors.error }]}>Log Out</Text>
            </TouchableOpacity>
          </View>
          <Text style={[styles.versionText, { color: colors.textSecondary }]}>InvestAI v2.4.0 • Built for Smart Investing</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 80,
  },
  backText: {
    fontSize: 17,
    marginLeft: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '700',
  },
  headerSpacer: {
    width: 80,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  profileSection: {
    alignItems: 'center',
    paddingTop: 32,
    paddingBottom: 24,
  },
  avatarWrapper: {
    position: 'relative',
    marginBottom: 16,
  },
  avatar: {
    width: 96,
    height: 96,
    borderRadius: 48,
    borderWidth: 4,
  },
  cameraBtn: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
  userName: {
    fontSize: 24,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  userEmail: {
    fontSize: 14,
    fontWeight: '500',
    marginTop: 4,
  },
  section: {
    paddingHorizontal: 16,
    marginTop: 24,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    marginLeft: 8,
    marginBottom: 8,
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 8,
        boxShadow: '0 2 8 rgba(0, 0, 0, 0.05)',
      },
      android: {
        elevation: 2,
      },
    }),
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  settingLabel: {
    flex: 1,
    fontSize: 15,
    fontWeight: '600',
  },
  selector: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  selectorText: {
    fontSize: 15,
    fontWeight: '500',
  },
  expandableSection: {
    paddingTop: 16,
  },
  subHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  subContent: {
    paddingLeft: 64, // iconContainer (36) + marginRight (12) + paddingHorizontal (16)
    paddingRight: 16,
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(226, 232, 240, 0.4)',
  },
  toggleLabel: {
    fontSize: 15,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    gap: 8,
  },
  logoutText: {
    fontSize: 17,
    fontWeight: '700',
  },
  versionText: {
    textAlign: 'center',
    fontSize: 12,
    marginTop: 16,
  },
});
