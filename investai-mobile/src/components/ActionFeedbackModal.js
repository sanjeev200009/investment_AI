// src/components/ActionFeedbackModal.js
import React, { useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    Modal,
    Animated,
    TouchableOpacity
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';

/**
 * A reusable modal for providing visual feedback (Success/Error/Loading) 
 * for front-end actions to simulate a full app experience.
 */
const ActionFeedbackModal = ({ 
    visible, 
    onClose, 
    title = "Success", 
    message = "Your action was completed.",
    type = "success", // success, error, info
    autoClose = true,
    duration = 2000
}) => {
    const theme = useAppTheme();
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
                })
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
            })
        ]).start(() => {
            onClose && onClose();
        });
    };

    const getIcon = () => {
        switch(type) {
            case 'error': return { name: 'error-outline', color: '#EF4444' };
            case 'info': return { name: 'info-outline', color: '#3B82F6' };
            default: return { name: 'check-circle-outline', color: '#10B981' };
        }
    };

    const icon = getIcon();

    return (
        <Modal
            transparent
            visible={visible}
            animationType="none"
            onRequestClose={handleClose}
        >
            <View style={styles.overlay}>
                <Animated.View style={[
                    styles.backdrop, 
                    { opacity: opacity, backgroundColor: 'rgba(0,0,0,0.4)' }
                ]}>
                    <TouchableOpacity style={styles.flex1} onPress={handleClose} />
                </Animated.View>

                <Animated.View style={[
                    styles.modalContainer,
                    { 
                        opacity: opacity,
                        transform: [{ scale: scale }],
                        backgroundColor: theme.colors.surface
                    }
                ]}>
                    <View style={[styles.iconWrapper, { backgroundColor: icon.color + '15' }]}>
                        <MaterialIcons name={icon.name} size={48} color={icon.color} />
                    </View>
                    <Text style={[styles.title, { color: theme.colors.textPrimary }]}>{title}</Text>
                    <Text style={[styles.message, { color: theme.colors.textSecondary }]}>{message}</Text>
                    
                    {!autoClose && (
                        <TouchableOpacity 
                            style={[styles.closeBtn, { backgroundColor: theme.colors.primary }]}
                            onPress={handleClose}
                        >
                            <Text style={styles.closeBtnText}>Done</Text>
                        </TouchableOpacity>
                    )}
                </Animated.View>
            </View>
        </Modal>
    );
};

const styles = StyleSheet.create({
    overlay: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    backdrop: {
        ...StyleSheet.absoluteFillObject,
    },
    flex1: {
        flex: 1,
    },
    modalContainer: {
        width: '80%',
        padding: 32,
        borderRadius: 24,
        alignItems: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.1,
        shadowRadius: 20,
        elevation: 10,
    },
    iconWrapper: {
        width: 80,
        height: 80,
        borderRadius: 40,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 20,
    },
    title: {
        fontSize: 22,
        fontWeight: '800',
        marginBottom: 12,
        textAlign: 'center',
    },
    message: {
        fontSize: 16,
        textAlign: 'center',
        lineHeight: 24,
        marginBottom: 8,
    },
    closeBtn: {
        marginTop: 24,
        paddingHorizontal: 32,
        paddingVertical: 12,
        borderRadius: 12,
    },
    closeBtnText: {
        color: '#FFFFFF',
        fontSize: 16,
        fontWeight: '700',
    }
});

export default ActionFeedbackModal;
