// src/components/Markdown.js
//
// The small slice of Markdown the assistant actually writes: # / ## / ###
// headings, **bold**, *italic*, `code`, bullet and numbered lists (one nested
// level), paragraphs and simple | pipe | tables. Anything else shows as plain
// text. Safe to re-render on every streamed token: a marker that has not been
// closed yet (a half-streamed "**") is hidden instead of flashing on screen.
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { palette, fonts, radii } from '../theme/tokens';

const LIST = /^(\s*)([-*+•]|\d+[.)])\s+(.*)$/;
const HEADING = /^(#{1,6})\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const INLINE = /(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\*[^*\s][^*\n]*\*|_[^_\s][^_\n]*_)/g;

const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());

// Lines → blocks. Exported for the self-check below.
export function parseBlocks(src) {
  const lines = String(src || '').replace(/\r/g, '').split('\n');
  const blocks = [];
  let para = [];
  const flush = () => { if (para.length) { blocks.push({ type: 'p', text: para.join(' ') }); para = []; } };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) { flush(); continue; }
    let m;
    if ((m = line.match(HEADING))) {
      flush();
      blocks.push({ type: 'h', level: m[1].length, text: m[2].replace(/#+\s*$/, '') });
    } else if ((m = line.match(LIST))) {
      flush();
      const ordered = /\d/.test(m[2]);
      blocks.push({ type: 'li', level: m[1].replace(/\t/g, '  ').length >= 2 ? 1 : 0, marker: ordered ? m[2].replace(')', '.') : '•', text: m[3] });
    } else if (line.trim().startsWith('|') && (TABLE_SEP.test(lines[i + 1] || '') || blocks[blocks.length - 1]?.type === 'table')) {
      flush();
      const last = blocks[blocks.length - 1];
      if (last?.type === 'table') last.rows.push(cells(line));
      else { blocks.push({ type: 'table', header: cells(line), rows: [] }); i++; }
    } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      flush();
      blocks.push({ type: 'hr' });
    } else {
      para.push(line.trim());
    }
  }
  flush();
  return blocks;
}

// Text → [{ text, bold, italic, code }].
export function parseInline(text) {
  const out = [];
  for (const part of String(text).split(INLINE)) {
    if (!part) continue;
    if (/^(\*\*|__).+\1$/.test(part)) out.push({ text: part.slice(2, -2), bold: true });
    else if (/^`.+`$/.test(part)) out.push({ text: part.slice(1, -1), code: true });
    else if (/^([*_]).+\1$/.test(part)) out.push({ text: part.slice(1, -1), italic: true });
    // An unclosed marker (mid-stream or malformed) is dropped, not shown.
    else out.push({ text: part.replace(/\*\*|__|`/g, '').replace(/(^|\s)\*(?=\S)/g, '$1') });
  }
  return out;
}

function Inline({ text, style }) {
  return (
    <Text style={style} selectable>
      {parseInline(text).map((s, i) => (
        <Text key={i} style={s.bold ? styles.bold : s.italic ? styles.italic : s.code ? styles.code : null}>{s.text}</Text>
      ))}
    </Text>
  );
}

function Markdown({ text, color = palette.ink }) {
  const base = [styles.body, { color }];
  return (
    <View style={styles.root}>
      {parseBlocks(text).map((b, i) => {
        switch (b.type) {
          case 'h':
            return <Inline key={i} text={b.text} style={[base, b.level === 1 ? styles.h1 : b.level === 2 ? styles.h2 : styles.h3]} />;
          case 'li':
            return (
              <View key={i} style={[styles.li, b.level ? styles.liNested : null]}>
                <Text style={[base, styles.marker]}>{b.level && b.marker === '•' ? '◦' : b.marker}</Text>
                <Inline text={b.text} style={[base, { flex: 1 }]} />
              </View>
            );
          case 'table':
            return (
              <View key={i} style={styles.table}>
                {[b.header, ...b.rows].map((row, r) => (
                  <View key={r} style={[styles.tr, r === 0 && styles.th, r > 0 && styles.trLine]}>
                    {b.header.map((_, c) => (
                      <Inline key={c} text={row[c] || ''} style={[base, styles.td, r === 0 && styles.bold]} />
                    ))}
                  </View>
                ))}
              </View>
            );
          case 'hr':
            return <View key={i} style={styles.hr} />;
          default:
            return <Inline key={i} text={b.text} style={base} />;
        }
      })}
    </View>
  );
}

export default React.memo(Markdown);

const styles = StyleSheet.create({
  root: { gap: 8 },
  body: { fontFamily: fonts.regular, fontSize: 16, lineHeight: 24 },
  h1: { fontFamily: fonts.medium, fontSize: 21, lineHeight: 28, marginTop: 4 },
  h2: { fontFamily: fonts.medium, fontSize: 18, lineHeight: 25, marginTop: 4 },
  h3: { fontFamily: fonts.bold, fontSize: 16, lineHeight: 24 },
  bold: { fontFamily: fonts.bold },
  italic: { fontStyle: 'italic' },
  code: { fontFamily: fonts.medium, backgroundColor: palette.lavender, color: palette.lavenderInk },
  li: { flexDirection: 'row', gap: 8, paddingLeft: 4 },
  liNested: { paddingLeft: 24 },
  marker: { minWidth: 14, fontFamily: fonts.medium },
  table: { borderRadius: radii.sm, overflow: 'hidden', backgroundColor: 'rgba(15,17,21,0.03)' },
  tr: { flexDirection: 'row' },
  th: { backgroundColor: palette.lavender },
  trLine: { borderTopWidth: 1, borderTopColor: palette.hairline },
  td: { flex: 1, fontSize: 14, lineHeight: 20, paddingHorizontal: 8, paddingVertical: 6 },
  hr: { height: 1, backgroundColor: palette.hairline, marginVertical: 4 },
});
