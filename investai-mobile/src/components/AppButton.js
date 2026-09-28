// src/components/AppButton.js — v2 full-round pill. Kept for older call sites;
// new code uses PillButton from ./ui. Same props as before.
import React from 'react';
import { PillButton } from './ui';

const AppButton = ({ title, onPress, variant = 'primary', loading = false, disabled = false, style, icon }) => (
    <PillButton
        title={title}
        onPress={onPress}
        variant={variant === 'secondary' ? 'secondary' : 'primary'}
        loading={loading}
        disabled={disabled}
        style={[{ alignSelf: 'stretch' }, style]}
        // `icon` used to be a rendered element; PillButton takes an icon name,
        // so element icons are dropped rather than mis-rendered.
        icon={typeof icon === 'string' ? icon : undefined}
    />
);

export default AppButton;
