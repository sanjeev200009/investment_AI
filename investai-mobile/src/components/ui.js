// src/components/ui.js
//
// The v2 "Soft pastel" building blocks. Every screen composes these instead of
// styling its own buttons and cards, so the whole app keeps one look:
//
//   <Screen>           gradient ground + safe area (+ optional scroll/refresh)
//   <Header>           back circle, title, right-side circles
//   <CircleButton>     56px white circle icon button (optional badge)
//   <IconCircle>       outlined circle holding an icon (decorative)
//   <PillButton>       black (primary) or white (secondary) full-round button
//   <Chip>             small rounded label or filter (selectable)
//   <Card>             white glass card, radius 32
//   <StackCard>        pastel card that tucks under the one above it
//   <BigNumber>        large light number with smaller decimals
//   <ChangePill>       lime/coral/neutral pill with sign, for price changes
//   <Title>, <Label>   type styles
//   <Field>            full-round text input with a hidden-but-read label
//   <EmptyState>       icon + message (+ action) for empty / error states
import React from 'react';
import {
  View, Text, TextInput, StyleSheet, ScrollView, RefreshControl, ActivityIndicator, StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { MaterialIcons } from '@expo/vector-icons';
import TouchableTick from './TouchableTick';
import { palette, fonts, radii, sizes, changeTone } from '../theme/tokens';

const ACCENTS = {
  lime: { bg: palette.lime, ink: palette.limeInk },
  yellow: { bg: palette.yellow, ink: palette.yellowInk },
  lavender: { bg: palette.lavender, ink: palette.lavenderInk },
  coral: { bg: palette.coral, ink: palette.coralInk },
  white: { bg: '#FFFFFF', ink: palette.ink },
};
export const accent = (name) => ACCENTS[name] || ACCENTS.white;
export const ACCENT_CYCLE = ['lime', 'yellow', 'lavender', 'coral'];

// ── Layout ───────────────────────────────────────────────────────────────────

export function Screen({
  children, scroll = true, refreshing, onRefresh, contentStyle, footer, edges = ['top'],
}) {
  const body = scroll ? (
    <ScrollView
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={[styles.content, contentStyle]}
      refreshControl={onRefresh
        ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={palette.ink} />
        : undefined}
    >
      {children}
    </ScrollView>
  ) : <View style={[styles.content, { flex: 1 }, contentStyle]}>{children}</View>;

  return (
    <LinearGradient
      colors={palette.gradient}
      locations={palette.gradientStops}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={{ flex: 1 }}
    >
      <StatusBar barStyle="dark-content" backgroundColor="transparent" translucent />
      <SafeAreaView style={{ flex: 1 }} edges={edges}>
        {body}
        {footer}
      </SafeAreaView>
    </LinearGradient>
  );
}

export function Header({ title, subtitle, onBack, right, backLabel = 'Back' }) {
  return (
    <View style={styles.header}>
      {onBack ? <CircleButton icon="arrow-back" onPress={onBack} label={backLabel} /> : null}
      <View style={{ flex: 1, paddingLeft: onBack ? 6 : 4 }}>
        {title ? <Text style={styles.headerTitle} numberOfLines={1}>{title}</Text> : null}
        {subtitle ? <Text style={styles.caption} numberOfLines={1}>{subtitle}</Text> : null}
      </View>
      {right}
    </View>
  );
}

// ── Buttons ──────────────────────────────────────────────────────────────────

export function CircleButton({ icon, onPress, label, badge, tone = 'white', size = sizes.circle, disabled, iconColor }) {
  const a = accent(tone);
  return (
    <TouchableTick
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={size < sizes.touch ? { top: 8, bottom: 8, left: 8, right: 8 } : undefined}
      style={[styles.circle, { width: size, height: size, backgroundColor: tone === 'white' ? palette.glass : a.bg, opacity: disabled ? 0.45 : 1 }]}
    >
      <MaterialIcons name={icon} size={Math.round(size * 0.38)} color={iconColor || a.ink} />
      {badge ? (
        <View style={styles.badge}><Text style={styles.badgeText}>{badge > 99 ? '99+' : badge}</Text></View>
      ) : null}
    </TouchableTick>
  );
}

export function IconCircle({ icon, color = palette.ink, size = sizes.circleSm, borderColor = palette.outline, children }) {
  return (
    <View style={[styles.iconCircle, { width: size, height: size, borderColor }]}>
      {children || <MaterialIcons name={icon} size={Math.round(size * 0.4)} color={color} />}
    </View>
  );
}

export function PillButton({ title, onPress, icon, variant = 'primary', loading, disabled, style, label }) {
  const primary = variant === 'primary';
  const off = disabled || loading;
  return (
    <TouchableTick
      onPress={onPress}
      disabled={off}
      accessibilityRole="button"
      accessibilityLabel={label || title}
      accessibilityState={{ disabled: !!off, busy: !!loading }}
      style={[styles.pill, primary ? styles.pillPrimary : styles.pillSecondary, off && { opacity: 0.5 }, style]}
    >
      {loading ? (
        <ActivityIndicator color={primary ? '#FFFFFF' : palette.ink} />
      ) : (
        <>
          {icon ? <MaterialIcons name={icon} size={20} color={primary ? '#FFFFFF' : palette.ink} /> : null}
          <Text style={[styles.pillText, { color: primary ? '#FFFFFF' : palette.ink }]}>{title}</Text>
        </>
      )}
    </TouchableTick>
  );
}

export function Chip({ label, selected, onPress, tone, icon }) {
  const a = tone ? accent(tone) : null;
  const bg = selected ? palette.ink : a ? a.bg : palette.glassSoft;
  const fg = selected ? '#FFFFFF' : a ? a.ink : palette.ink;
  const inner = (
    <>
      {icon ? <MaterialIcons name={icon} size={14} color={fg} /> : null}
      <Text style={[styles.chipText, { color: fg }]}>{label}</Text>
    </>
  );
  if (!onPress) return <View style={[styles.chip, { backgroundColor: bg }]}>{inner}</View>;
  return (
    <TouchableTick
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      style={[styles.chip, { backgroundColor: bg, minHeight: 44 }]}
    >
      {inner}
    </TouchableTick>
  );
}

// ── Surfaces ─────────────────────────────────────────────────────────────────

export function Card({ children, style, tone, onPress, label }) {
  const bg = tone ? accent(tone).bg : 'rgba(255,255,255,0.88)';
  if (onPress) {
    return (
      <TouchableTick onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={[styles.card, { backgroundColor: bg }, style]}>
        {children}
      </TouchableTick>
    );
  }
  return <View style={[styles.card, { backgroundColor: bg }, style]}>{children}</View>;
}

/** Pastel card whose top tucks under the previous one (the reference's stack).
 *  Pass `first` on the first card of a stack. */
export function StackCard({ tone = 'lime', first, last, children, onPress, label, style }) {
  const a = accent(tone);
  const s = [styles.stack, { backgroundColor: a.bg, marginTop: first ? 0 : -22, paddingBottom: last ? 24 : 44 }, style];
  if (onPress) {
    return <TouchableTick onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={s}>{children}</TouchableTick>;
  }
  return <View style={s}>{children}</View>;
}

// ── Type ─────────────────────────────────────────────────────────────────────

/** 21,307.90 → "21,307" large + ".90" smaller and lighter. */
export function BigNumber({ value, digits = 2, prefix, size = 64, color = palette.ink }) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return <Text style={[styles.big, { fontSize: size, color }]}>—</Text>;
  }
  const [int, dec] = Number(value)
    .toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    .split('.');
  return (
    <Text style={[styles.big, { fontSize: size, color }]} accessibilityLabel={`${prefix || ''} ${int}${dec ? '.' + dec : ''}`}>
      {prefix ? <Text style={[styles.bigSmall, { fontSize: size * 0.38 }]}>{prefix} </Text> : null}
      {int}
      {dec ? <Text style={[styles.bigSmall, { fontSize: size * 0.5 }]}>.{dec}</Text> : null}
    </Text>
  );
}

/** Price change as a filled pill: ▲ 0.50 · +0.25% */
export function ChangePill({ change, pct, suffix }) {
  const t = changeTone(pct ?? change);
  const parts = [];
  if (Number.isFinite(Number(change))) parts.push(`${t.arrow ? t.arrow + ' ' : ''}${Math.abs(Number(change)).toFixed(2)}`);
  if (Number.isFinite(Number(pct))) parts.push(`${t.sign}${Math.abs(Number(pct)).toFixed(2)}%`);
  const text = parts.length ? parts.join(' · ') : '—';
  return (
    <View style={[styles.changePill, { backgroundColor: t.background }]}>
      <Text style={[styles.changeText, { color: t.ink }]}>{text}{suffix ? ` · ${suffix}` : ''}</Text>
    </View>
  );
}

export const Title = ({ children, style, ...props }) => <Text accessibilityRole="header" style={[styles.title, style]} {...props}>{children}</Text>;
export const Heading = ({ children, style, ...props }) => <Text accessibilityRole="header" style={[styles.heading, style]} {...props}>{children}</Text>;
export const Label = ({ children, style, ...props }) => <Text style={[styles.caption, style]} {...props}>{children}</Text>;
export const Body = ({ children, style, ...props }) => <Text style={[styles.body, style]} {...props}>{children}</Text>;

// ── Inputs & states ──────────────────────────────────────────────────────────

export function Field({ label, error, style, inputStyle, ...props }) {
  return (
    <View style={[{ gap: 6 }, style]}>
      {label ? <Text style={styles.fieldLabel}>{label}</Text> : null}
      <TextInput
        placeholderTextColor={palette.faint}
        accessibilityLabel={props.accessibilityLabel || label || props.placeholder}
        style={[styles.field, error && { borderColor: palette.error, borderWidth: 1.5 }, inputStyle]}
        {...props}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  );
}

export function EmptyState({ icon = 'inbox', title, message, action, onAction, tone = 'lavender' }) {
  const a = accent(tone);
  return (
    <Card tone={tone} style={{ alignItems: 'flex-start', gap: 10 }}>
      <IconCircle icon={icon} color={a.ink} borderColor="rgba(0,0,0,0.15)" />
      {title ? <Text style={[styles.heading, { color: a.ink }]}>{title}</Text> : null}
      {message ? <Text style={[styles.body, { color: a.ink }]}>{message}</Text> : null}
      {action ? <PillButton title={action} onPress={onAction} style={{ alignSelf: 'stretch', marginTop: 4 }} /> : null}
    </Card>
  );
}

export const Loading = () => <ActivityIndicator style={{ marginVertical: 32 }} color={palette.ink} />;

const text = { color: palette.ink, fontFamily: fonts.regular };

const styles = StyleSheet.create({
  content: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 120, gap: 24 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: sizes.circle },
  headerTitle: { ...text, fontSize: 21 },
  circle: { borderRadius: radii.full, alignItems: 'center', justifyContent: 'center' },
  badge: {
    position: 'absolute', top: 4, right: 4, minWidth: 18, height: 18, paddingHorizontal: 4,
    borderRadius: radii.full, backgroundColor: palette.badge, alignItems: 'center', justifyContent: 'center',
  },
  badgeText: { color: '#FFFFFF', fontSize: 10, fontFamily: fonts.bold },
  iconCircle: { borderRadius: radii.full, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  pill: {
    height: sizes.cta, borderRadius: radii.full, flexDirection: 'row', gap: 10,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24,
  },
  pillPrimary: { backgroundColor: palette.ink },
  pillSecondary: { backgroundColor: '#FFFFFF' },
  pillText: { fontFamily: fonts.medium, fontSize: 16 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
    borderRadius: radii.full, paddingHorizontal: 14, paddingVertical: 8,
  },
  chipText: { fontFamily: fonts.medium, fontSize: 13 },
  card: { borderRadius: radii.xl, padding: 20 },
  stack: {
    borderTopLeftRadius: radii.xxl, borderTopRightRadius: radii.xxl,
    borderBottomLeftRadius: radii.xxl, borderBottomRightRadius: radii.xxl,
    paddingHorizontal: 22, paddingTop: 22,
  },
  big: { ...text, fontFamily: fonts.regular, letterSpacing: -2, fontVariant: ['tabular-nums'] },
  bigSmall: { fontFamily: fonts.light, color: palette.muted, letterSpacing: -1 },
  changePill: { alignSelf: 'flex-start', borderRadius: radii.full, paddingHorizontal: 12, paddingVertical: 6 },
  changeText: { fontFamily: fonts.medium, fontSize: 14, fontVariant: ['tabular-nums'] },
  title: { ...text, fontSize: 36, letterSpacing: -1, lineHeight: 40 },
  heading: { ...text, fontSize: 20 },
  body: { ...text, fontSize: 16, lineHeight: 23 },
  caption: { ...text, fontSize: 13, color: palette.muted },
  fieldLabel: { ...text, fontFamily: fonts.medium, fontSize: 13, color: palette.muted, paddingLeft: 18 },
  field: {
    height: sizes.control, borderRadius: radii.full, backgroundColor: 'rgba(255,255,255,0.92)',
    paddingHorizontal: 22, fontSize: 16, fontFamily: fonts.regular, color: palette.ink,
  },
  fieldError: { ...text, fontSize: 13, color: palette.error, paddingLeft: 18 },
});
