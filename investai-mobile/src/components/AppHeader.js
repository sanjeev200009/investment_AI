// src/components/AppHeader.js
import React from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    Platform,
    StatusBar
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';

/**
 * Reusable Header component for navigation screens.
 * Handles back navigation, title, and right-side actions.
 */
const AppHeader = ({
    title,
    onBack,
    rightAction,
    transparent = false,
    style
}) => {
    const theme = useAppTheme();

    return (
        <View style={[
            styles.container,
            {
                backgroundColor: transparent ? 'transparent' : theme.colors.surface,
                borderBottomColor: transparent ? 'transparent' : theme.colors.divider,
                borderBottomWidth: transparent ? 0 : 1,
                paddingTop: Platform.OS === 'ios' ? 44 : StatusBar.currentHeight,
            },
            style
        ]}>
            <View style={styles.content}>
                <View style={styles.leftContainer}>
                    {onBack && (
                        <TouchableOpacity
                            onPress={onBack}
                            style={[styles.backButton, { backgroundColor: transparent ? 'rgba(255, 255, 255, 0.1)' : 'transparent' }]}
                        >
                            <MaterialIcons
                                name="arrow-back-ios"
                                size={22}
                                color={transparent ? '#FFFFFF' : theme.colors.textPrimary}
                            />
                        </TouchableOpacity>
                    )}
                </View>

                <View style={styles.titleContainer}>
                    {title && (
                        <Text style={[
                            styles.title,
                            { color: transparent ? '#FFFFFF' : theme.colors.textPrimary, fontSize: theme.typography.sizes.h4 }
                        ]}>
                            {title}
                        </Text>
                    )}
                </View>

                <View style={styles.rightContainer}>
                    {rightAction}
                </View>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        width: '100%',
        zIndex: 100,
    },
    content: {
        height: 64,
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 16,
    },
    leftContainer: {
        flex: 1,
        alignItems: 'flex-start',
    },
    titleContainer: {
        flex: 3,
        alignItems: 'center',
    },
    rightContainer: {
        flex: 1,
        alignItems: 'flex-end',
    },
    title: {
        fontWeight: '700',
    },
    backButton: {
        width: 44,
        height: 44,
        borderRadius: 12,
        justifyContent: 'center',
        alignItems: 'center',
        paddingLeft: 8,
    }
});

export default AppHeader;
