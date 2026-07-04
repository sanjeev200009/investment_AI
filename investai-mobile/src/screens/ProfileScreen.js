import TouchableTick from '../components/TouchableTick';
import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image, SafeAreaView, Switch, Platform, StatusBar, Modal, TextInput, ActivityIndicator } from 'react-native';
import { useAppTheme } from '../hooks/useAppTheme';
import { MaterialIcons } from '@expo/vector-icons';
import { useAuthStore } from '../store/authStore';
import AppHeader from '../components/AppHeader';
import { useAuth, useUser } from '@clerk/clerk-expo';
import * as ImagePicker from 'expo-image-picker';

export default function ProfileScreen({ navigation }) {
    const theme = useAppTheme();
    const { user, logout, isEducationEnabled, setEducationEnabled } = useAuthStore();
    const { signOut } = useAuth();
    const { user: clerkUser } = useUser();
    const isDark = theme.isDark;

    // Adaptive colors based on theme.tokens
    const colors = {
        primary: theme.colors.primary,
        background: theme.colors.background,
        surface: theme.isDark ? '#1E293B80' : '#FFFFFF',
        textPrimary: theme.colors.textPrimary,
        textSecondary: theme.colors.textSecondary,
        border: theme.colors.border,
        error: '#EF4444',
        iconBg: theme.isDark ? 'rgba(0, 82, 255, 0.1)' : '#EFF6FF',
    };

    const [notifications, setNotifications] = useState({
        priceAlerts: true,
        news: true,
    });

    const [biometric, setBiometric] = useState(true);
    
    // Profile Editing State
    const [editModalVisible, setEditModalVisible] = useState(false);
    const [firstName, setFirstName] = useState(clerkUser?.firstName || '');
    const [lastName, setLastName] = useState(clerkUser?.lastName || '');
    const [isSaving, setIsSaving] = useState(false);
    const [isUploadingImage, setIsUploadingImage] = useState(false);

    const handleLogout = async () => {
        await logout();   // clear Zustand store + AsyncStorage
        await signOut();  // end the Clerk session → triggers <SignedOut> → redirects to auth
    };

    const pickImage = async () => {
        try {
            const result = await ImagePicker.launchImageLibraryAsync({
                mediaTypes: ImagePicker.MediaTypeOptions.Images,
                allowsEditing: true,
                aspect: [1, 1],
                quality: 0.5,
                base64: true,
            });

            if (!result.canceled && result.assets[0].base64) {
                setIsUploadingImage(true);
                const base64Image = `data:image/jpeg;base64,${result.assets[0].base64}`;
                await clerkUser?.setProfileImage({ file: base64Image });
            }
        } catch (error) {
            console.error("Error uploading image:", error);
        } finally {
            setIsUploadingImage(false);
        }
    };

    const saveProfile = async () => {
        try {
            setIsSaving(true);
            await clerkUser?.update({
                firstName,
                lastName
            });
            setEditModalVisible(false);
        } catch (error) {
            console.error("Error updating profile:", error);
        } finally {
            setIsSaving(false);
        }
    };

    const openEditModal = () => {
        setFirstName(clerkUser?.firstName || '');
        setLastName(clerkUser?.lastName || '');
        setEditModalVisible(true);
    };

    const renderSettingItem = ({ icon, label, rightElement, onPress, isLast }) => (
        <TouchableTick
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
        </TouchableTick>
    );

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
            <StatusBar barStyle={isDark ? 'light-content' : 'dark-content'} />

            <AppHeader
                title="Profile & Settings"
                onBack={navigation.canGoBack() ? () => navigation.goBack() : null}
            />

            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
                {/* User Profile Section */}
                <View style={styles.profileSection}>
                    <View style={styles.avatarWrapper}>
                        {isUploadingImage ? (
                            <View style={[styles.avatar, { borderColor: isDark ? colors.border : '#FFFFFF', justifyContent: 'center', alignItems: 'center', backgroundColor: colors.surface }]}>
                                <ActivityIndicator color={colors.primary} />
                            </View>
                        ) : (
                            <Image
                                source={{ uri: clerkUser?.imageUrl || "https://ui-avatars.com/api/?name=User&background=random" }}
                                style={[styles.avatar, { borderColor: isDark ? colors.border : '#FFFFFF' }]}
                            />
                        )}
                        <TouchableTick onPress={pickImage} style={[styles.cameraBtn, { backgroundColor: colors.primary, borderColor: isDark ? colors.background : '#FFFFFF' }]}>
                            <MaterialIcons name="photo-camera" size={18} color="#FFFFFF" />
                        </TouchableTick>
                    </View>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                        <Text style={[styles.userName, { color: colors.textPrimary }]}>{clerkUser?.fullName || 'User'}</Text>
                        <TouchableTick onPress={openEditModal} style={{ padding: 4 }}>
                            <MaterialIcons name="edit" size={18} color={colors.primary} />
                        </TouchableTick>
                    </View>
                    <Text style={[styles.userEmail, { color: colors.textSecondary }]}>{clerkUser?.primaryEmailAddress?.emailAddress || 'email@example.com'}</Text>
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
                                    <Text style={[styles.toggleLabel, { color: colors.textSecondary }]}>Education Section</Text>
                                    <Switch
                                        value={isEducationEnabled}
                                        onValueChange={setEducationEnabled}
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
                        <TouchableTick style={styles.logoutBtn} onPress={handleLogout}>
                            <MaterialIcons name="logout" size={22} color={colors.error} />
                            <Text style={[styles.logoutText, { color: colors.error }]}>Log Out</Text>
                        </TouchableTick>
                    </View>
                    <Text style={[styles.versionText, { color: colors.textSecondary }]}>InvestAI v2.4.0 • Built for Smart Investing</Text>
                </View>
            </ScrollView>

            {/* Edit Profile Modal */}
            <Modal visible={editModalVisible} animationType="slide" transparent={true}>
                <View style={styles.modalOverlay}>
                    <View style={[styles.modalContent, { backgroundColor: colors.background, borderColor: colors.border }]}>
                        <View style={styles.modalHeader}>
                            <Text style={[styles.modalTitle, { color: colors.textPrimary }]}>Edit Profile</Text>
                            <TouchableTick onPress={() => setEditModalVisible(false)} style={styles.closeModalBtn}>
                                <MaterialIcons name="close" size={24} color={colors.textSecondary} />
                            </TouchableTick>
                        </View>
                        
                        <View style={styles.inputGroup}>
                            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>First Name</Text>
                            <TextInput
                                style={[styles.textInput, { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.surface }]}
                                value={firstName}
                                onChangeText={setFirstName}
                                placeholder="Enter first name"
                                placeholderTextColor={colors.textSecondary}
                            />
                        </View>

                        <View style={styles.inputGroup}>
                            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Last Name</Text>
                            <TextInput
                                style={[styles.textInput, { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.surface }]}
                                value={lastName}
                                onChangeText={setLastName}
                                placeholder="Enter last name"
                                placeholderTextColor={colors.textSecondary}
                            />
                        </View>

                        <TouchableTick 
                            style={[styles.saveBtn, { backgroundColor: colors.primary, opacity: isSaving ? 0.7 : 1 }]} 
                            onPress={saveProfile}
                            disabled={isSaving}
                        >
                            {isSaving ? (
                                <ActivityIndicator color="#FFFFFF" />
                            ) : (
                                <Text style={styles.saveBtnText}>Save Changes</Text>
                            )}
                        </TouchableTick>
                    </View>
                </View>
            </Modal>
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
        paddingHorizontal: 20,
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
                shadowOffset: { width: 0, height: 10 },
                shadowOpacity: 0.18,
                shadowRadius: 8,
            },
            android: {
                elevation: 10,
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
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.5)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        borderWidth: 1,
        borderBottomWidth: 0,
        padding: 24,
        paddingBottom: Platform.OS === 'ios' ? 40 : 24,
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 24,
    },
    modalTitle: {
        fontSize: 20,
        fontWeight: '700',
    },
    closeModalBtn: {
        padding: 4,
    },
    inputGroup: {
        marginBottom: 16,
    },
    inputLabel: {
        fontSize: 14,
        fontWeight: '500',
        marginBottom: 8,
    },
    textInput: {
        borderWidth: 1,
        borderRadius: 12,
        paddingHorizontal: 16,
        paddingVertical: 12,
        fontSize: 16,
    },
    saveBtn: {
        borderRadius: 12,
        paddingVertical: 16,
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: 16,
    },
    saveBtnText: {
        color: '#FFFFFF',
        fontSize: 16,
        fontWeight: '700',
    }
});
