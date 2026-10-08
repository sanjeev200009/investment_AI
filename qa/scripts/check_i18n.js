#!/usr/bin/env node
// i18n completeness check for investai-mobile.
// Usage: node qa/scripts/check_i18n.js [--json]
// Exit code 1 if any t('key') used in src/ is missing from English.
//
// translations.js is an ES module that only exports translate(); its tables are
// private. We copy src/i18n to a temp dir, add .js extensions + an export of the
// merged tables, and import that copy. App source is never modified.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..', '..');
const SRC = path.join(ROOT, 'investai-mobile', 'src');
const I18N = path.join(SRC, 'i18n');

function copyI18n() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-i18n-'));
  fs.writeFileSync(path.join(tmp, 'package.json'), '{"type":"module"}');
  const walk = (dir) => {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      const abs = path.join(dir, f.name);
      if (f.isDirectory()) { walk(abs); continue; }
      if (!f.name.endsWith('.js')) continue;
      let code = fs.readFileSync(abs, 'utf8')
        .replace(/(from\s+['"])(\.{1,2}\/[^'"]+?)(['"])/g, (m, a, p, b) => (p.endsWith('.js') ? m : a + p + '.js' + b));
      if (abs === path.join(I18N, 'translations.js')) code += '\nexport const __QA_TABLES = TRANSLATIONS;\n';
      const out = path.join(tmp, path.relative(I18N, abs));
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.writeFileSync(out, code);
    }
  };
  walk(I18N);
  return tmp;
}

function srcFiles(dir, acc = []) {
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, f.name);
    if (f.isDirectory()) { if (f.name !== 'i18n') srcFiles(abs, acc); }
    else if (/\.(js|jsx|ts|tsx)$/.test(f.name)) acc.push(abs);
  }
  return acc;
}

// Balanced-paren argument of each t( ... ) call.
function tCalls(code) {
  const out = [];
  const re = /(?<![\w.$])t\(/g;
  let m;
  while ((m = re.exec(code))) {
    let depth = 1, i = m.index + 2;
    while (i < code.length && depth) { if (code[i] === '(') depth++; else if (code[i] === ')') depth--; i++; }
    out.push({ arg: code.slice(m.index + 2, i - 1), line: code.slice(0, m.index).split('\n').length });
  }
  return out;
}

const LITERAL = /(['"])([a-z][a-z0-9_]*)\1/g;
// A literal compared with ===/!== inside t(...) is a condition, not a key.
const isComparison = (arg, idx) => {
  const after = arg.slice(idx).replace(/^(['"])[^'"]*\1/, '');
  return /[!=]==\s*$/.test(arg.slice(0, idx)) || /^\s*[!=]==/.test(after);
};
const TEMPLATE =/`([^`]*\$\{[^`]*)`/g;
// Keys held in data and translated later via t(c.labelKey), t(item), t(key) ...
const DATA_KEY = /\b(?:labelKey|titleKey|bodyKey|title|body|heading|text)\s*:\s*(['"])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\1/g;
const KEY_ARRAY = /\b[A-Z_]*KEYS?\b\s*=\s*([[{][\s\S]*?[\]}])\s*;/g;

const hasScript = (s, lang) => (lang === 'si' ? /[඀-෿]/ : /[஀-௿]/).test(s);
// Values that are legitimately identical in every language.
const NEUTRAL = (v) => !/[A-Za-z]{2,}/.test(v.replace(/\{[^}]*\}/g, '')) || /^(AI|InvestAI|ASPI|S&P SL20|CSE|OK|P\/E|EPS)$/.test(v.trim());

(async () => {
  const tmp = copyI18n();
  const { __QA_TABLES: T } = await import(pathToFileURL(path.join(tmp, 'translations.js')).href);
  fs.rmSync(tmp, { recursive: true, force: true });
  const en = T.en;
  const enKeys = Object.keys(en);
  const report = { counts: {}, missing: {}, empty: {}, identicalToEnglish: {}, noNativeScript: {}, extraKeys: {} };

  for (const lang of ['si', 'ta']) {
    const tbl = T[lang];
    report.missing[lang] = enKeys.filter((k) => !(k in tbl));
    report.empty[lang] = enKeys.filter((k) => k in tbl && String(tbl[k]).trim() === '');
    report.identicalToEnglish[lang] = enKeys.filter((k) => k in tbl && tbl[k] === en[k] && !NEUTRAL(String(en[k])));
    report.noNativeScript[lang] = enKeys.filter((k) => k in tbl && tbl[k] !== en[k] && !hasScript(String(tbl[k]), lang) && !NEUTRAL(String(tbl[k])));
    report.extraKeys[lang] = Object.keys(tbl).filter((k) => !(k in en));
    report.counts[lang] = Object.keys(tbl).length;
  }
  report.counts.en = enKeys.length;
  report.counts.en_empty = enKeys.filter((k) => String(en[k]).trim() === '');

  // Keys referenced from src/
  const used = new Map(); // key -> [file:line]
  const dynamic = [];
  const add = (k, where) => { if (!used.has(k)) used.set(k, []); used.get(k).push(where); };
  for (const file of srcFiles(SRC)) {
    const code = fs.readFileSync(file, 'utf8');
    const rel = path.relative(ROOT, file).replace(/\\/g, '/');
    for (const { arg, line } of tCalls(code)) {
      for (const lm of arg.matchAll(LITERAL)) if (!isComparison(arg, lm.index)) add(lm[2], `${rel}:${line}`);
      for (const tm of arg.matchAll(TEMPLATE)) {
        const pattern = tm[1];
        const rx = new RegExp('^' + pattern.split(/\$\{[^}]*\}/).map((s) => s.replace(/[.*+?^$()|[\]\\]/g, '\\$&')).join('[a-z0-9_]+') + '$');
        dynamic.push({ where: `${rel}:${line}`, pattern: '`' + pattern + '`', matchingEnKeys: enKeys.filter((k) => rx.test(k)).length });
      }
    }
    const lineOf = (idx) => code.slice(0, idx).split('\n').length;
    for (const dm of code.matchAll(DATA_KEY)) add(dm[2], `${rel}:${lineOf(dm.index)} (data)`);
    if (/(?<![\w.$])t\(/.test(code)) for (const am of code.matchAll(KEY_ARRAY)) for (const lm of am[1].matchAll(LITERAL)) {
      if (lm[2].includes('_')) add(lm[2], `${rel}:${lineOf(am.index)} (KEYS const)`);
    }
  }
  report.usedKeyCount = used.size;
  report.usedButMissingInEnglish = [...used].filter(([k]) => !(k in en)).map(([k, w]) => ({ key: k, where: w }));
  report.dynamicKeyPatterns = dynamic;
  report.unusedEnglishKeys = enKeys.filter((k) => !used.has(k)).length; // approximate: dynamic keys count as unused

  if (process.argv.includes('--json')) { console.log(JSON.stringify(report, null, 2)); }
  else {
    const c = report.counts;
    console.log(`Keys: en=${c.en} si=${c.si} ta=${c.ta} | empty en values: ${c.en_empty.length}`);
    for (const lang of ['si', 'ta']) {
      console.log(`\n[${lang}] missing (falls back to English): ${report.missing[lang].length}`);
      console.log('  ' + report.missing[lang].join(', '));
      console.log(`[${lang}] empty: ${report.empty[lang].length} ${report.empty[lang].join(', ')}`);
      console.log(`[${lang}] identical to English: ${report.identicalToEnglish[lang].length}`);
      for (const k of report.identicalToEnglish[lang]) console.log(`  ${k} = ${JSON.stringify(en[k])}`);
      console.log(`[${lang}] translated but no ${lang === 'si' ? 'Sinhala' : 'Tamil'} script: ${report.noNativeScript[lang].length}`);
      for (const k of report.noNativeScript[lang]) console.log(`  ${k} = ${JSON.stringify(T[lang][k])}`);
      console.log(`[${lang}] keys not in English (dead): ${report.extraKeys[lang].length} ${report.extraKeys[lang].join(', ')}`);
    }
    console.log(`\nKeys referenced in src/: ${report.usedKeyCount}; English keys never referenced literally: ${report.unusedEnglishKeys}`);
    console.log(`Used in src/ but missing in English: ${report.usedButMissingInEnglish.length}`);
    for (const u of report.usedButMissingInEnglish) console.log(`  ${u.key}  <- ${u.where.join(', ')}`);
    console.log(`Dynamic t(\`...\`) patterns: ${dynamic.length}`);
    for (const d of dynamic) console.log(`  ${d.where} ${d.pattern} -> ${d.matchingEnKeys} matching en keys`);
  }
  process.exitCode = report.usedButMissingInEnglish.length ? 1 : 0;
})().catch((e) => { console.error(e); process.exitCode = 2; });
