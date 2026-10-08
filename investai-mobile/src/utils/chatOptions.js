// The assistant asks a follow-up question when it needs more detail, ending its
// message with one line "OPTIONS: a | b | c" (see SYSTEM_PROMPT in
// investai-backend/app/services/agent/memory.py). This splits that line off so
// the text shows normally and the choices become tap-to-answer chips.

const MARK = 'OPTIONS:';

export function splitOptions(text) {
  const raw = text || '';
  const lines = raw.replace(/\s+$/, '').split('\n');
  const last = (lines[lines.length - 1] || '').trim();
  // Complete line: "OPTIONS: a | b" (any case; tolerate markdown bold/bullets).
  const m = last.replace(/^[-*\s]*\**/, '').match(/^options\s*:\**\s*(.*)$/i);
  if (m) {
    const options = m[1].split('|').map(s => s.replace(/\*+/g, '').trim()).filter(Boolean).slice(0, 4);
    return { body: lines.slice(0, -1).join('\n').replace(/\s+$/, ''), options };
  }
  // Still streaming "OPTI…": hide the half-written marker instead of flashing it.
  if (last.length && last.length < MARK.length && MARK.startsWith(last.toUpperCase())) {
    return { body: lines.slice(0, -1).join('\n').replace(/\s+$/, ''), options: [] };
  }
  return { body: raw, options: [] };
}
