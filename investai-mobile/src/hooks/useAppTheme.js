// src/hooks/useAppTheme.js
import { useColorScheme } from 'react-native';
import { getTheme } from '../theme/tokens';

/**
 * Custom hook to get the current theme based on the system color scheme.
 * Returns the theme object containing colors, typography, spacing, etc.
 */
export const useAppTheme = () => {
    const colorScheme = useColorScheme();
    return getTheme(colorScheme || 'light');
};
