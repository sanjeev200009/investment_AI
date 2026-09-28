// src/components/AppHeader.js — v2 header. Kept for older call sites; new
// screens use Header from ./ui directly. `title`, `onBack`, `rightAction` and
// `children` (a custom title block) behave as before.
import React from 'react';
import { View } from 'react-native';
import { Header } from './ui';

const AppHeader = ({ title, onBack, rightAction, children, style }) => (
    <View style={[{ paddingHorizontal: 20, paddingTop: 8 }, style]}>
        {children ? (
            <Header onBack={onBack} right={rightAction} title={null} />
        ) : (
            <Header title={title} onBack={onBack} right={rightAction} />
        )}
        {children || null}
    </View>
);

export default AppHeader;
