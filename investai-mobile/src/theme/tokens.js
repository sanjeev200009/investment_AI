// src/theme/tokens.js

export const palette = {
    // Brand Colors
    primary: {
        main: '#0052FF',
        light: '#60A5FA',
        dark: '#0A192F',
        contrastText: '#FFFFFF',
    },

    // Neutral Colors (Light Theme)
    light: {
        background: '#F9FAFB',
        surface: '#FFFFFF',
        field: '#F9FAFB',
        border: '#E5E7EB',
        textPrimary: '#111827',
        textSecondary: '#4B5563',
        divider: '#E5E7EB',
    },

    // Neutral Colors (Dark Theme)
    dark: {
        background: '#0A0A0A',
        surface: '#161616',
        field: '#1E1E1E',
        border: '#262626',
        textPrimary: '#FFFFFF',
        textSecondary: '#9CA3AF',
        divider: '#262626',
    },

    // Semantic Colors
    success: '#10B981',
    error: '#EF4444',
    warning: '#F59E0B',
    info: '#3B82F6',
};

export const typography = {
    fontFamily: Platform => Platform.OS === 'ios' ? 'System' : 'Roboto',

    sizes: {
        h1: 36,
        h2: 28,
        h3: 24,
        h4: 20,
        body1: 16,
        body2: 15,
        caption: 13,
        button: 18,
    },

    weights: {
        bold: '800',
        semiBold: '700',
        medium: '600',
        regular: '400',
    },
};

export const spacing = {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    xxl: 32,
    xxxl: 48,
};

export const radii = {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    xxl: 24,
    full: 9999,
};

export const shadows = {
    light: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.1,
        shadowRadius: 8,
        elevation: 3,
        boxShadow: '0 4 8 rgba(0, 0, 0, 0.1)',
    },
    dark: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.3,
        shadowRadius: 20,
        elevation: 8,
        boxShadow: '0 10 20 rgba(0, 0, 0, 0.3)',
    },
};

export const getTheme = (mode) => {
    const isDark = mode === 'dark';
    const colors = isDark ? palette.dark : palette.light;

    return {
        isDark,
        colors: {
            ...colors,
            primary: palette.primary.main,
            success: palette.success,
            error: palette.error,
            warning: palette.warning,
            info: palette.info,
            gradient: isDark ? [palette.primary.dark, palette.primary.main] : [palette.primary.light, '#3B82F6'],
        },
        typography,
        spacing,
        radii,
        shadows: isDark ? shadows.dark : shadows.light,
    };
};
