// src/components/ActionFeedbackModal.js
//
// Success / error / info feedback after an action, v2 "Soft pastel": a white
// radius-32 sheet with a pastel icon circle (lime success, coral error,
// lavender info) and, when it does not auto-close, a black Done button.
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, Modal, Animated } from 'react-native';
import TouchableTick from './TouchableTick';
import { IconCircle, PillButton, accent } from './ui';
import { palette, fonts, radii } from '../theme/tokens';
import { useT } from '../store/languageStore';

const TYPES = {
    success: { icon: 'check', tone: 'lime' },
    error: { icon: 'error-outline', tone: 'coral' },
    info: { icon: 'info-outline', tone: 'lavender' },
};

const ActionFeedbackModal = ({
    visible,
    onClose,
    title,
    message,
    type = 'success', // success, error, info
    autoClose = true,
    duration = 2000,
}) => {
    const { t } = useT();
    const opacity = new Animated.Value(0);
    const scale = new Animated.Value(0.8);

    useEffect(() => {
        if (visible) {
            Animated.parallel([
                Animated.timing(opacity, {
                    toValue: 1,
                    duration: 300,
                    useNativeDriver: true,
                }),
                Animated.spring(scale, {
                    toValue: 1,
                    friction: 8,
                    useNativeDriver: true,
                }),
            ]).start();

            if (autoClose) {
                const timer = setTimeout(() => {
                    handleClose();
                }, duration);
                return () => clearTimeout(timer);
            }
        }
    }, [visible]);

    const handleClose = () => {
        Animated.parallel([
            Animated.timing(opacity, {
                toValue: 0,
                duration: 200,
                useNativeDriver: true,
            }),
            Animated.timing(scale, {
                toValue: 0.8,
                duration: 200,
                useNativeDriver: true,
            }),
        ]).start(() => {
            onClose && onClose();
        });
    };

    const kind = TYPES[type] || TYPES.success;
    const a = accent(kind.tone);

    return (
        <Modal
            transparent
            visible={visible}
            animationType="none"
            onRequestClose={handleClose}
        >
            <View style={styles.overlay}>
                <Animated.View style={[styles.backdrop, { opacity }]}>
                    <TouchableTick
                        style={styles.flex1}
                        onPress={handleClose}
                        accessibilityRole="button"
                        accessibilityLabel={t('feedback_done')}
                    />
                </Animated.View>

                <Animated.View
                    accessibilityLiveRegion="polite"
                    style={[styles.sheet, { opacity, transform: [{ scale }] }]}
                >
                    <View style={[styles.iconFill, { backgroundColor: a.bg }]}>
                        <IconCircle icon={kind.icon} color={a.ink} borderColor="rgba(0,0,0,0.15)" size={64} />
                    </View>
                    <Text style={styles.title}>{title ?? t('feedback_default_title')}</Text>
                    <Text style={styles.message}>{message ?? t('feedback_default_message')}</Text>

                    {!autoClose && (
                        <PillButton title={t('feedback_done')} onPress={handleClose} style={styles.done} />
                    )}
                </Animated.View>
            </View>
        </Modal>
    );
};

const styles = StyleSheet.create({
    overlay: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 20 },
    backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(15,17,21,0.4)' },
    flex1: { flex: 1 },
    sheet: {
        width: '100%', maxWidth: 380, padding: 28, borderRadius: radii.xl,
        backgroundColor: '#FFFFFF', alignItems: 'center', gap: 12,
    },
    iconFill: { borderRadius: radii.full, padding: 10, marginBottom: 6 },
    title: { color: palette.ink, fontFamily: fonts.medium, fontSize: 22, textAlign: 'center' },
    message: { color: palette.muted, fontFamily: fonts.regular, fontSize: 16, lineHeight: 23, textAlign: 'center' },
    done: { alignSelf: 'stretch', marginTop: 12 },
});

export default ActionFeedbackModal;
