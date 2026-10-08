// src/screens/ProfileScreen.js
//
// Profile & settings, v2 "Soft pastel": large initials avatar, settings grouped
// in white glass cards with full-round rows, language as chips, coral log-out pill.
import TouchableTick from '../components/TouchableTick';
import React, { useState } from 'react';
import { View, Text, StyleSheet, Modal, Alert } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import appConfig from '../../app.json';
import InitialsAvatar from '../components/InitialsAvatar';
import {
  Screen, Header, CircleButton, IconCircle, PillButton, Chip, Card, Heading, Label, Field,
} from '../components/ui';
import { useAuthStore } from '../store/authStore';
import { useLanguageStore, useT } from '../store/languageStore';
import { LANGUAGES } from '../i18n/translations';
import { authApi } from '../api/authApi';
import { replayTour } from '../components/Tour';
import { palette, fonts, radii, sizes } from '../theme/tokens';

export default function ProfileScreen({ navigation }) {
    const { user, logout, updateProfile, deleteAccount } = useAuthStore();
    // Language preference (I-15): the selector below is the real toggle. It
    // switches the UI immediately, persists to AsyncStorage, and saves to
    // user_profiles.language — which is also what the AI agent reads to decide
    // which language to answer in.
    const { t } = useT();
    const language = useLanguageStore(state => state.language);
    const level = useLanguageStore(state => state.level);
    const setLevel = useLanguageStore(state => state.setLevel);
    const setLanguage = useLanguageStore(state => state.setLanguage);

    // The store's user comes from GET /auth/me, i.e. our own `users` row.
    const displayName = user?.full_name || t('profile_default_name');
    const displayEmail = user?.email || '';

    // Profile Editing State. `users.full_name` is one column, so the modal
    // edits one field.
    const [editModalVisible, setEditModalVisible] = useState(false);
    const [fullName, setFullName] = useState(displayName);
    const [isSaving, setIsSaving] = useState(false);

    const handleLogout = () => {
        Alert.alert(t('profile_logout_title'), t('profile_logout_confirm'), [
            { text: t('cancel'), style: 'cancel' },
            // The store clears local state and revokes the session server-side;
            // AppNavigator drops to the auth stack when isAuthenticated flips.
            { text: t('profile_logout_title'), style: 'destructive', onPress: () => logout() },
        ]);
    };

    // Password changes go through the verified reset flow (emailed code), which
    // lives on the sign-in screens.
    const handleChangePassword = () => {
        Alert.alert(
            t('profile_change_password'),
            t('profile_change_password_body'),
            [
                { text: t('cancel'), style: 'cancel' },
                { text: t('profile_continue'), onPress: () => logout() },
            ],
        );
    };

    const handleDeleteAccount = () => {
        Alert.alert(t('profile_delete_account'), t('profile_delete_body'), [
            { text: t('cancel'), style: 'cancel' },
            {
                text: t('profile_delete_account'),
                style: 'destructive',
                // On success the store signs out locally and AppNavigator drops
                // to the auth stack; on failure nothing local changes.
                onPress: async () => {
                    try {
                        await deleteAccount();
                    } catch (error) {
                        Alert.alert(t('profile_error_title'), error?.response
                            ? (error.response.data?.detail || t('profile_delete_error'))
                            : t('auth_network_error'));
                    }
                },
            },
        ]);
    };

    const saveProfile = async () => {
        const trimmed = fullName.trim();
        if (trimmed.length < 2) {
            Alert.alert(t('profile_invalid_name_title'), t('profile_invalid_name_body'));
            return;
        }
        try {
            setIsSaving(true);
            const updated = await authApi.updateProfile(trimmed);
            updateProfile({ full_name: updated.full_name });
            setEditModalVisible(false);
        } catch (error) {
            const msg = error?.response?.data?.detail
                || t('profile_save_error');
            Alert.alert(t('profile_error_title'), msg);
        } finally {
            setIsSaving(false);
        }
    };

    const openEditModal = () => {
        setFullName(displayName);
        setEditModalVisible(true);
    };

    const Row = ({ icon, label, sub, right, onPress, danger }) => (
        <TouchableTick style={[styles.row, danger && styles.rowDanger]} onPress={onPress} disabled={!onPress} accessibilityRole="button" accessibilityLabel={label}>
            <IconCircle icon={icon} color={danger ? palette.coralInk : palette.ink} />
            <View style={{ flex: 1, gap: 2 }}>
                <Text style={[styles.rowLabel, danger && { color: palette.coralInk }]}>{label}</Text>
                {sub ? <Label>{sub}</Label> : null}
            </View>
            {right}
            <MaterialIcons name="chevron-right" size={24} color={palette.faint} />
        </TouchableTick>
    );

    const Divider = () => <View style={styles.divider} />;

    return (
        <Screen>
            <Header
                title={t('profile_title')}
                onBack={navigation.canGoBack() ? () => navigation.goBack() : null}
                backLabel={t('account_back')}
            />

            {/* Profile head */}
            <View style={styles.head}>
                <InitialsAvatar name={displayName} size={112} background={palette.coral} />
                <View style={styles.nameRow}>
                    <Text style={styles.name} numberOfLines={2}>{displayName}</Text>
                    <CircleButton icon="edit" size={44} label={t('profile_edit_name_a11y')} onPress={openEditModal} />
                </View>
                {displayEmail ? <Label>{displayEmail}</Label> : null}
            </View>

            {/* Preferences */}
            <View style={styles.section}>
                <Label style={styles.sectionTitle}>{t('profile_section_preferences')}</Label>
                <Card style={styles.group}>
                    <View style={styles.langBlock}>
                        <View style={styles.langHead}>
                            <IconCircle icon="language" />
                            <Text style={styles.rowLabel}>{t('profile_language')}</Text>
                        </View>
                        {/* The three codes here, the translations file and the
                            backend's /me/language must agree — LANGUAGES is the
                            single source imported for all three uses. */}
                        <View style={styles.chipRow}>
                            {LANGUAGES.map(({ code, label }) => (
                                <TouchableTick
                                    key={code}
                                    onPress={() => setLanguage(code)}
                                    accessibilityRole="button"
                                    accessibilityLabel={label}
                                    accessibilityState={{ selected: language === code }}
                                    style={styles.chipHit}
                                >
                                    <Chip label={label} selected={language === code} />
                                </TouchableTick>
                            ))}
                        </View>
                    </View>
                    <Divider />
                    <View style={styles.langBlock}>
                        <View style={styles.langHead}>
                            <IconCircle icon="school" />
                            <Text style={styles.rowLabel}>{t('profile_word_level')}</Text>
                        </View>
                        <View style={styles.chipRow}>
                            {['beginner', 'intermediate', 'expert'].map(code => (
                                <TouchableTick
                                    key={code}
                                    onPress={() => setLevel(code)}
                                    accessibilityRole="button"
                                    accessibilityLabel={t(`level_${code}`)}
                                    accessibilityState={{ selected: level === code }}
                                    style={styles.chipHit}
                                >
                                    <Chip label={t(`level_${code}`)} selected={level === code} />
                                </TouchableTick>
                            ))}
                        </View>
                    </View>
                    <Divider />
                    <Row
                        icon="notifications-none"
                        label={t('profile_notifications')}
                        sub={t('profile_price_alert_rules')}
                        right={<Text style={styles.manage}>{t('profile_manage')}</Text>}
                        onPress={() => navigation.navigate('Rules')}
                    />
                    <Divider />
                    <Row
                        icon="assignment"
                        label={t('profile_retake_assessment')}
                        onPress={() => navigation.navigate('RetakeAssessment')}
                    />
                </Card>
            </View>

            {/* Security */}
            <View style={styles.section}>
                <Label style={styles.sectionTitle}>{t('profile_section_security')}</Label>
                <Card style={styles.group}>
                    <Row icon="lock-outline" label={t('profile_change_password')} onPress={handleChangePassword} />
                    <Divider />
                    <Row icon="delete-forever" label={t('profile_delete_account')} onPress={handleDeleteAccount} danger />
                </Card>
            </View>

            {/* Support & legal */}
            <View style={styles.section}>
                <Label style={styles.sectionTitle}>{t('profile_section_support')}</Label>
                <Card style={styles.group}>
                    <Row
                        icon="tour"
                        label={t('profile_show_tour')}
                        sub={t('profile_show_tour_sub')}
                        onPress={() => { replayTour(); if (navigation.canGoBack()) navigation.popToTop(); }}
                    />
                    <Divider />
                    <Row icon="description" label={t('legal_privacy_title')} onPress={() => navigation.navigate('Legal', { doc: 'privacy' })} />
                    <Divider />
                    <Row icon="gavel" label={t('legal_terms_title')} onPress={() => navigation.navigate('Legal', { doc: 'terms' })} />
                </Card>
            </View>

            {/* Log out */}
            <View style={{ gap: 14 }}>
                <TouchableTick style={styles.logout} onPress={handleLogout} accessibilityRole="button" accessibilityLabel={t('profile_logout_title')}>
                    <MaterialIcons name="logout" size={20} color={palette.coralInk} />
                    <Text style={styles.logoutText}>{t('profile_logout_title')}</Text>
                </TouchableTick>
                <Label style={{ textAlign: 'center', color: palette.faint }}>
                    {t('profile_version').replace('{version}', appConfig.expo.version)}
                </Label>
            </View>

            {/* Edit Profile Modal */}
            <Modal visible={editModalVisible} animationType="slide" transparent={true} onRequestClose={() => setEditModalVisible(false)}>
                <View style={styles.modalOverlay}>
                    <View style={styles.sheet}>
                        <View style={styles.sheetHead}>
                            <Heading style={{ flex: 1 }}>{t('profile_edit_title')}</Heading>
                            <CircleButton icon="close" label={t('profile_close_a11y')} onPress={() => setEditModalVisible(false)} />
                        </View>
                        <Field
                            label={t('profile_full_name')}
                            value={fullName}
                            onChangeText={setFullName}
                            placeholder={t('profile_full_name_placeholder')}
                            autoCapitalize="words"
                        />
                        <PillButton title={t('profile_save_changes')} onPress={saveProfile} loading={isSaving} />
                    </View>
                </View>
            </Modal>
        </Screen>
    );
}

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
    head: { alignItems: 'center', gap: 10, paddingTop: 8 },
    nameRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 52, maxWidth: '100%' },
    name: { ...text, fontSize: 28, letterSpacing: -0.6, textAlign: 'center', flexShrink: 1 },
    section: { gap: 10 },
    sectionTitle: { paddingLeft: 12, letterSpacing: 1, fontFamily: fonts.medium },
    group: { padding: 8 },
    row: {
        flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 64,
        paddingHorizontal: 10, paddingVertical: 8, borderRadius: radii.full,
    },
    rowDanger: { backgroundColor: palette.coral },
    rowLabel: { ...text, fontFamily: fonts.medium, fontSize: 16 },
    manage: { ...text, fontFamily: fonts.medium, fontSize: 14, color: palette.muted },
    divider: { height: 1, backgroundColor: palette.hairline, marginHorizontal: 16 },
    langBlock: { paddingHorizontal: 10, paddingVertical: 8, gap: 8 },
    langHead: { flexDirection: 'row', alignItems: 'center', gap: 14 },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 8, paddingLeft: 60 },
    chipHit: { minHeight: sizes.touch, justifyContent: 'center' },
    logout: {
        height: sizes.cta, borderRadius: radii.full, backgroundColor: palette.coral,
        flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    },
    logoutText: { fontFamily: fonts.medium, fontSize: 16, color: palette.coralInk },
    modalOverlay: { flex: 1, backgroundColor: 'rgba(15,17,21,0.45)', justifyContent: 'flex-end' },
    sheet: {
        backgroundColor: '#F3F3FA', borderTopLeftRadius: radii.xxl, borderTopRightRadius: radii.xxl,
        padding: 20, paddingBottom: 40, gap: 16,
    },
    sheetHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
});
