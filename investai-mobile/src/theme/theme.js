// src/theme/theme.js
export const lightPalette = {
  primary: '#023e8a', // French Blue
  primaryDark: '#03045e', // Deep Twilight
  primaryLight: '#0077b6', // Bright Teal Blue
  accent: '#00b4d8', // Turquoise Surf
  bgApp: '#caf0f8', // Light Cyan
  bgCard: '#FFFFFF',
  textPrimary: '#03045e',
  textSecond: '#023e8a',
  textMuted: '#0077b6',
  divider: '#90e0ef',
  gradient: ['#FFFFFF', '#F1F5F9'],
  curved: '#023e8a',
  swipeBtn: '#023e8a',
  swipeInner: '#FFFFFF',
  coinGradient: ['#D4AF37', '#FFDF00', '#FFFACD'],
};

export const darkPalette = {
  primary: '#1976D2', // Blue for buttons
  primaryDark: '#040814', // Navy Deep
  primaryLight: '#0A1931', // Navy Royal
  accent: '#152A4A', // Lighter Navy
  bgApp: '#040814',
  bgCard: '#0A1931',
  textPrimary: '#FFFFFF',
  textSecond: '#E0E0E0',
  textMuted: 'rgba(255, 255, 255, 0.7)',
  divider: 'rgba(255, 255, 255, 0.1)',
  gradient: ['#040814', '#0A1931', '#152A4A'],
  curved: '#060B1A',
  swipeBtn: 'rgba(0, 0, 0, 0.4)',
  swipeInner: '#1976D2',
  coinGradient: ['#92400E', '#FACC15', '#FEF9C3'], // Yellow-600 via yellow-400 to yellow-200
};

export const colors = (scheme) => scheme === 'dark' ? darkPalette : lightPalette;

export const typography = (scheme) => {
  const c = colors(scheme);
  return {
    screenHeader: { fontSize: 22, fontWeight: '800', color: '#FFFFFF', fontFamily: 'Roboto_800ExtraBold' },
    sectionHead: { fontSize: 18, fontWeight: '700', color: c.textPrimary, fontFamily: 'Roboto_700Bold' },
    subheading: { fontSize: 15, fontWeight: '500', color: c.primaryLight, fontFamily: 'Roboto_500Medium' },
    priceL: { fontSize: 28, fontWeight: '700', fontFamily: 'monospace' },
    body: { fontSize: 14, fontWeight: '400', color: c.textSecond },
    caption: { fontSize: 12, fontWeight: '400', color: c.textMuted },
    button: { fontSize: 16, fontWeight: '700', color: '#FFFFFF', fontFamily: 'Roboto_700Bold' },
  };
};

export const spacing = {
  screenPad: 16,
  cardRadius: 12,
  buttonH: 52,
  touchMin: 48,
};

export const shadows = {
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
  },
};
