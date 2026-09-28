// src/components/AppInput.js — v2 full-round input with optional leading icon.
// Same props as before (label, error, icon, style, ...TextInput props).
import React from 'react';
import { View, TextInput, Text, StyleSheet } from 'react-native';
import { palette, fonts, radii, sizes } from '../theme/tokens';

const AppInput = ({ label, error, icon, style, ...props }) => (
    <View style={[styles.container, style]}>
        {label ? <Text style={styles.label}>{label}</Text> : null}
        <View style={[styles.wrapper, error && styles.wrapperError]}>
            {icon ? <View style={styles.icon}>{icon}</View> : null}
            <TextInput
                placeholderTextColor={palette.faint}
                accessibilityLabel={props.accessibilityLabel || label || props.placeholder}
                style={styles.input}
                {...props}
            />
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
);

const styles = StyleSheet.create({
    container: { width: '100%', gap: 6 },
    label: { fontFamily: fonts.medium, fontSize: 13, color: palette.muted, paddingLeft: 18 },
    wrapper: {
        height: sizes.control, borderRadius: radii.full, backgroundColor: 'rgba(255,255,255,0.92)',
        flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20,
        borderWidth: 1.5, borderColor: 'transparent',
    },
    wrapperError: { borderColor: palette.error },
    icon: { marginRight: 10 },
    input: { flex: 1, fontSize: 16, fontFamily: fonts.regular, color: palette.ink },
    error: { fontFamily: fonts.regular, fontSize: 13, color: palette.error, paddingLeft: 18 },
});

export default AppInput;
