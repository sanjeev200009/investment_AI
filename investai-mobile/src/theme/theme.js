// src/theme/theme.js
export const lightPalette = {
  primary: '#0052FF',
  primaryDark: '#0036A3',
  primaryLight: '#3D82FF',
  accent: '#00B4D8',
  bgApp: '#F9FAFB',
  bgCard: '#FFFFFF',
  textPrimary: '#111827',
  textSecond: '#4B5563',
  textMuted: '#6B7280',
  divider: '#E5E7EB',
  gradient: ['#FFFFFF', '#F1F5F9'],
  curved: '#0052FF',
  swipeBtn: '#0052FF',
  swipeInner: '#FFFFFF',
  coinGradient: ['#D4AF37', '#FFDF00', '#FFFACD'],
};

export const darkPalette = {
  primary: '#0052FF',
  primaryDark: '#020202',
  primaryLight: '#0A0A0A',
  accent: '#161616',
  bgApp: '#0A0A0A',
  bgCard: '#161616',
  textPrimary: '#FFFFFF',
  textSecond: '#E0E0E0',
  textMuted: 'rgba(255, 255, 255, 0.7)',
  divider: '#262626',
  gradient: ['#0A0A0A', '#161616', '#262626'],
  curved: '#0A0A0A',
  swipeBtn: 'rgba(255, 255, 255, 0.1)',
  swipeInner: '#0052FF',
  coinGradient: ['#92400E', '#FACC15', '#FEF9C3'],
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
