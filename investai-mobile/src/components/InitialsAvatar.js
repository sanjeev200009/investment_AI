// src/components/InitialsAvatar.js
//
// Rendered locally. The screens used to load
// https://ui-avatars.com/api/?name=<full name>, which sent every user's full
// name to a third-party service on each screen view.
import React from 'react';
import { View, Text } from 'react-native';

export const initialsOf = (name) =>
  (name || 'Investor')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('');

export default function InitialsAvatar({ name, size = 40, style, background = '#FF9F87' }) {
  return (
    <View
      accessibilityLabel={`Profile: ${name || 'Investor'}`}
      style={[{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: background,
        alignItems: 'center',
        justifyContent: 'center',
      }, style]}
    >
      <Text style={{ color: background === '#FF9F87' ? '#3B1D14' : '#FFFFFF', fontFamily: 'Satoshi-Medium', fontSize: size * 0.36 }}>
        {initialsOf(name)}
      </Text>
    </View>
  );
}
