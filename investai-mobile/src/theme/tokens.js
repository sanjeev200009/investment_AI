// src/theme/tokens.js
//
// InvestAI v2 "Soft pastel". Mirrors the v2 page of the design canvas:
// a mint-to-lavender gradient ground, white glass surfaces, near-black ink for
// text and the one primary action per screen, and four pastel accents used as
// whole card fills (never as thin text colours). Everything is fully rounded.
//
// Meaning of the accents is fixed across the app:
//   lime      gains, "done", positive state
//   coral     losses, errors, destructive
//   yellow    watchlist / attention
//   lavender  news, learning, information
// Gains and losses always carry a sign or arrow as well as colour.

export const palette = {
    ink: '#0F1115',
    muted: '#4C525B',       // secondary text, 7.4:1 on white
    faint: '#6B7078',       // captions, 4.9:1 on white

    lime: '#8BF28A',     limeInk: '#0F3A12',
    yellow: '#FFF27A',   yellowInk: '#3A3200',
    lavender: '#D8C7F4', lavenderInk: '#3B2C57',
    coral: '#FF9F87',    coralInk: '#3B1D14',
    mint: '#B6EFD8',

    badge: '#FF6B6B',
    glass: 'rgba(255,255,255,0.8)',
    glassSoft: 'rgba(255,255,255,0.55)',
    hairline: 'rgba(15,17,21,0.12)',
    outline: 'rgba(15,17,21,0.18)',

    // Background gradient, top-left to bottom-right.
    gradient: ['#B6EFD8', '#D9F4EA', '#E6E7F8', '#F3F3FA'],
    gradientStops: [0, 0.32, 0.7, 1],

    // ── Legacy names kept so older call sites keep compiling ────────────────
    evergreen: '#0F3A12',
    evergreenSoft: '#8BF28A',
    brick: '#3B1D14',
    brickSoft: '#FF9F87',
    primary: { main: '#0F1115', light: '#EEF0F5', dark: '#000000', contrastText: '#FFFFFF' },

    light: {
        background: '#EEF3F2',   // flat fallback where the gradient cannot be drawn
        surface: '#FFFFFF',
        field: '#FFFFFF',
        fieldSubtle: '#EEF0F5',
        border: 'rgba(15,17,21,0.12)',
        divider: 'rgba(15,17,21,0.08)',
        textPrimary: '#0F1115',
        textSecondary: '#4C525B',
        textTertiary: '#6B7078',
        iconMuted: '#6B7078',
    },
    dark: {
        background: '#0B0D10', surface: '#15181D', field: '#15181D', fieldSubtle: '#1E2229',
        border: '#2A2F37', divider: '#22262D', textPrimary: '#F1F2F5', textSecondary: '#A7ADB6',
        textTertiary: '#8C929B', iconMuted: '#8C929B',
    },

    success: '#0F3A12',
    error: '#B3261E',
    warning: '#3A3200',
    info: '#3B2C57',
};

export const fonts = {
    light: 'Satoshi-Light',
    regular: 'Satoshi-Regular',
    medium: 'Satoshi-Medium',
    bold: 'Satoshi-Bold',
    black: 'Satoshi-Black',
};

export const typography = {
    fontFamily: () => fonts.regular,
    fonts,
    sizes: {
        hero: 64,     // the one big number per screen (integer part)
        heroDecimals: 32,
        figure: 40,
        h1: 34,       // screen titles ("Price rules", "Learn")
        h2: 24,
        h3: 20,
        h4: 18,
        heading: 20,  // section headings
        body1: 16,
        body2: 14,
        caption: 12,
        button: 16,
    },
    weights: { bold: '700', semiBold: '600', medium: '500', regular: '400', light: '300' },
    tabular: { fontVariant: ['tabular-nums'] },
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, xxxl: 32, huge: 48 };

export const radii = {
    sm: 14,
    md: 22,       // small tiles
    lg: 28,
    xl: 32,       // cards
    xxl: 36,      // stacked cards (top corners)
    full: 9999,   // buttons, inputs, chips, circles
};

export const sizes = {
    circle: 56,       // header circle buttons
    circleSm: 46,     // outline icon circles
    control: 60,      // inputs
    cta: 62,          // primary pill button
    touch: 44,        // minimum touch target
};

export const shadows = {
    light: {}, // v2 is flat: separation comes from glass and colour, not shadow
    raised: {
        shadowColor: '#0F1115', shadowOffset: { width: 0, height: 12 },
        shadowOpacity: 0.08, shadowRadius: 30, elevation: 4,
    },
    dark: {},
};

export const motion = { fast: 150, base: 200, pressScale: 0.97 };

/**
 * Colours and sign for a change value. `null` / non-finite = no prior close.
 * Returns fill (background), ink (text on that fill), sign and arrow.
 */
export const changeTone = (value) => {
    const neutral = {
        background: '#EEF0F5', color: palette.muted, ink: palette.muted, sign: '', arrow: '',
    };
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return neutral;
    const n = Number(value);
    if (n > 0) return { background: palette.lime, color: palette.limeInk, ink: palette.limeInk, sign: '+', arrow: '▲' };
    if (n < 0) return { background: palette.coral, color: palette.coralInk, ink: palette.coralInk, sign: '−', arrow: '▼' };
    return neutral;
};

export const getTheme = (mode) => {
    const isDark = mode === 'dark';
    const colors = isDark ? palette.dark : palette.light;
    return {
        isDark,
        colors: {
            ...colors,
            ink: palette.ink,
            primary: palette.ink,
            primarySoft: '#EEF0F5',
            success: palette.success,
            error: palette.error,
            errorSoft: palette.coral,
            warning: palette.warning,
            info: palette.info,
            gradient: palette.gradient,
        },
        palette,
        typography,
        spacing,
        radii,
        sizes,
        motion,
        shadows: isDark ? shadows.dark : shadows.light,
        raised: shadows.raised,
    };
};
