#!/usr/bin/env node
/*
 * crossword.js -- engine JSON in, a printable crossword out.
 *
 *   node renderers/crossword.js <in.json> <out.html>
 *
 * Per renderers/README: the JSON is the only contract. Which words, which clues and which
 * form the student is asked for are all decided in engine/export_crossword.py. Nothing here
 * reaches into the store.
 *
 * MACRONS -- the one design decision worth reading (owner, 2026-09-09)
 * -------------------------------------------------------------------
 *   "what we don't want is vertical/horizontal collisions between macronized/unmacronized
 *    forms. Animālia should not share its middle a with canis. We want to subtly reinforce
 *    that the letters are *different* and that the difference is *real*. But students are
 *    not going to be required to produce them themselves."
 *
 * So there are two passes and the ORDER is load-bearing:
 *
 *   1. LAYOUT crosses on `answer`, which is macronized. `Ā` and `A` are different
 *      characters, so the generator will never place one over the other. Verified against
 *      the trial-01 set: 19 crossings, 0 mismatches.
 *   2. RENDER draws `bare` in the puzzle and the fillable version -- the student writes A --
 *      and the macronized letter in the printed ANSWER KEY (owner, 2026-09-11).
 *
 * Doing it the other way -- lay out bare, decorate after -- would let `canis` and `animālia`
 * share a cell that then has to be both long and short, and whichever word drew second would
 * silently win.
 *
 * NOTHING MARKS THE LONG CELLS IN THE GRID. An earlier version drew a small rule above the
 * writing space; the owner cut it, 2026-09-09 ("cute idea, but no"). The macron distinction
 * still governs the LAYOUT -- that is the part that was asked for -- and the macronized forms
 * are shown in the word bank, the key list, and the answer-key GRID itself, where the student
 * reads rather than writes.
 */
'use strict';

const fs = require('fs');
const path = require('path');

// The library dumps a word/score table to stdout on require AND on every call. Muzzle it --
// this program's stdout is a progress line, and a vendored 0.1.1 package should not be able
// to corrupt it.
const _log = console.log;
console.log = () => {};
const clg = require('crossword-layout-generator');
console.log = _log;

const LONG = 'ĀĒĪŌŪȲ';
const isLong = (ch) => LONG.includes(ch);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// A tiny seeded PRNG. THE LAYOUT MUST BE REPRODUCIBLE: the generator's packing depends on
// input order, so an unseeded shuffle means the same JSON prints a different puzzle every
// run -- you could not reprint a lost handout, and no check of this output could be trusted
// twice. `--seed` varies it deliberately (a second version for a retake).
function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a * 1664525 + 1013904223) >>> 0; return a / 4294967296; };
}

// Any one attempt can leave a word unplaced -- measured over 500 runs: ~9% of attempts for
// an all-ASCII set, ~33% for trial-01, ~52% for a set with long vowels word-initially, since
// a macronized vowel crosses only its own kind and so offers fewer hooks. Retrying is the
// whole answer; 24 puts the odds of total failure below one in a million even for the hard
// case.
const ATTEMPTS = 24;

function layout(words, seed) {
  const quiet = (fn) => { console.log = () => {}; try { return fn(); } finally { console.log = _log; } };
  // The generator is cheap and its packing varies with input order; take the tightest grid
  // that places EVERY word. A puzzle missing a quiz word is not a puzzle.
  let best = null;
  const rand = rng(seed);
  for (let i = 0; i < ATTEMPTS; i++) {
    // FRESH OBJECTS EVERY ATTEMPT. generateLayout MUTATES its input -- it writes startx,
    // starty, orientation and position onto the objects you hand it and returns that same
    // array as `result`. Re-calling it with those objects feeds stale positions back in and
    // the layouts go strange. It cost an afternoon and a wrong published number here: a
    // harness that reused them measured "99.8% of macronized layouts are invalid" and the
    // real figure, with fresh copies, is zero. `.slice()` is NOT enough -- it copies the
    // array, not the objects.
    const shuffled = words.map((w) => ({ answer: w.answer, clue: w.clue }));
    if (i > 0) {                       // Fisher-Yates on the seeded stream
      for (let j = shuffled.length - 1; j > 0; j--) {
        const k = Math.floor(rand() * (j + 1));
        [shuffled[j], shuffled[k]] = [shuffled[k], shuffled[j]];
      }
    }
    const L = quiet(() => clg.generateLayout(shuffled));
    const missing = L.result.filter((r) => r.orientation === 'none');
    if (missing.length) continue;
    const area = L.cols * L.rows;
    if (!best || area < best.area) best = { L, area };
  }
  if (!best) {
    const L = quiet(() => clg.generateLayout(words.map((w) => ({ answer: w.answer, clue: w.clue }))));
    const missing = L.result.filter((r) => r.orientation === 'none').map((r) => r.answer);
    throw new Error(`could not place every word in ${ATTEMPTS} attempts; unplaced: ${missing.join(', ')}`);
  }
  return best.L;
}

function cells(L) {
  // (x,y) -> {letter, long}. Built from the placements, and it ASSERTS agreement rather than
  // letting the last writer win -- that assertion is what proves the macron rule held.
  const m = new Map();
  for (const r of L.result) {
    if (r.orientation === 'none') continue;
    for (let i = 0; i < r.answer.length; i++) {
      const x = r.startx - 1 + (r.orientation === 'across' ? i : 0);
      const y = r.starty - 1 + (r.orientation === 'down' ? i : 0);
      const k = `${x},${y}`, ch = r.answer[i];
      if (m.has(k) && m.get(k).ch !== ch) {
        throw new Error(`cell ${k} is both ${m.get(k).ch} and ${ch} (${r.answer}) -- ` +
          'a long vowel was crossed with a short one. The layout ran on `bare`, not `answer`.');
      }
      m.set(k, { ch, long: isLong(ch) });
    }
  }
  return m;
}

// THE GRID IS SVG, NOT A TABLE, AND THAT IS A PRINT FIX (owner, 2026-09-09: "print preview
// shows missing lines in all versions, print-to-pdf only in the Answer Key").
//
// `border-collapse: collapse` shares one border between two cells, and at print scale the
// browser rounds each shared edge independently -- so lines land on or off a device pixel
// more or less at random and some simply vanish. It is not fixable by thickening the border;
// the rounding is the mechanism. Backgrounds are also dropped by default in print, which is
// why the two grids behaved differently.
//
// SVG has neither problem: the geometry is stated in real units, the printer rasterises it at
// device resolution, and nothing is shared between cells. `shape-rendering="crispEdges"`
// keeps the strokes from being antialiased into greyness.
const MM = 8;            // nominal cell, millimetres
const MAX_W = 170;       // usable width of a portrait page with sane margins

// Standard crossword numbering, computed from the grid rather than taken from the library.
// EXOLVE NUMBERS THE GRID ITSELF and we cannot override it, so the clue numbers we emit have
// to be the ones it will derive. Computing them here and asserting they match the library's
// `position` keeps the printed sheet and the online version on the same numbering -- and if
// they ever diverge, the print sheet is the one that was wrong.
function numbering(L, grid) {
  const at = (x, y) => grid.has(`${x},${y}`);
  const num = new Map();
  let n = 0;
  for (let y = 0; y < L.rows; y++) {
    for (let x = 0; x < L.cols; x++) {
      if (!at(x, y)) continue;
      const startsAcross = !at(x - 1, y) && at(x + 1, y);
      const startsDown = !at(x, y - 1) && at(x, y + 1);
      if (startsAcross || startsDown) num.set(`${x},${y}`, ++n);
    }
  }
  return num;
}

function checkNumbering(L, num) {
  // Every placed word must HAVE a number. That is the invariant; agreement with the
  // library's own `position` is NOT, and must not be asserted.
  //
  // THE LIBRARY NUMBERS IN PLACEMENT ORDER, NOT READING ORDER -- it counts words as it
  // places them, so the first word it happens to seat is 1 wherever it lands. Real
  // crosswords number cells left-to-right, top-to-bottom. Printed sheets built before
  // 2026-09-09 carried the library's numbering, which is why clue 4 sat at the top of the
  // grid and clue 1 in the middle: not wrong exactly, but not what a solver expects, and
  // Exolve derives reading-order numbers itself and cannot be overridden. So the grid's
  // numbering is now the single source for the sheet AND the fillable version.
  const missing = [];
  for (const r of L.result) {
    if (r.orientation === 'none') continue;
    if (!num.has(`${r.startx - 1},${r.starty - 1}`)) missing.push(r.answer);
  }
  return missing;
}

function gridSVG(L, grid, num, { solved }) {
  const sw = 0.3;                                  // stroke, mm
  // PAD THE VIEWBOX BY HALF A STROKE ON EVERY SIDE. An SVG stroke straddles its path, so the
  // outermost cells paint from -sw/2 to +sw/2 either side of the grid's bounding box -- and a
  // viewBox set to the bounding box exactly clips that outer half away. The result is a
  // half-thickness outer border that reads as MISSING in print (owner spotted it on
  // TIBIPLACET, 2026-09-09: a ten-cell unbroken run at the very bottom edge, which is where a
  // half-width line is most obvious). It was never an overlap with the answer-key list.
  const pad = sw / 2;
  const cell = Math.min(MM, (MAX_W - sw) / L.cols);   // shrink to fit, never grow
  const gw = L.cols * cell, gh = L.rows * cell;
  const w = (gw + sw).toFixed(2), h = (gh + sw).toFixed(2);
  let out = '';
  for (let y = 0; y < L.rows; y++) {
    for (let x = 0; x < L.cols; x++) {
      const c = grid.get(`${x},${y}`);
      if (!c) continue;
      const px = (x * cell), py = (y * cell);
      out += `<rect x="${px.toFixed(2)}" y="${py.toFixed(2)}" ` +
             `width="${cell.toFixed(2)}" height="${cell.toFixed(2)}" ` +
             `fill="#fff" stroke="#111" stroke-width="${sw}"/>`;
      const n = num.get(`${x},${y}`);
      if (n) {
        out += `<text x="${(px + cell * 0.09).toFixed(2)}" y="${(py + cell * 0.30).toFixed(2)}" ` +
               `font-size="${(cell * 0.26).toFixed(2)}" fill="#555">${n}</text>`;
      }
      if (solved) {
        // THE KEY CARRIES THE MACRON (owner, 2026-09-11). The student writes bare letters and
        // is not asked to produce one; the teacher's key shows the real spelling, which is
        // the one place on the sheet the long vowel is taught rather than merely avoided.
        // Safe for the same reason as everything else here: layout crossed on the macronized
        // form, so a long-vowel cell is long in BOTH words that pass through it. The
        // fillable version stays bare -- there the student types, and Exolve checks.
        out += `<text x="${(px + cell / 2).toFixed(2)}" y="${(py + cell * 0.82).toFixed(2)}" ` +
               `font-size="${(cell * 0.55).toFixed(2)}" text-anchor="middle" ` +
               `font-weight="600" fill="#111">${esc(c.ch)}</text>`;
      }
    }
  }
  return `<svg class="grid" xmlns="http://www.w3.org/2000/svg" ` +
    `viewBox="${(-pad).toFixed(2)} ${(-pad).toFixed(2)} ${w} ${h}" ` +
    `width="${w}mm" height="${h}mm" shape-rendering="crispEdges" ` +
    `font-family="Tahoma, Verdana, sans-serif">${out}</svg>`;
}

function clueList(L, words, dir, num) {
  const byAnswer = new Map(words.map((w) => [w.answer, w]));
  const rows = L.result
    .filter((r) => r.orientation === dir)
    .map((r) => ({ r, n: num.get(`${r.startx - 1},${r.starty - 1}`) }))
    .sort((a, b) => a.n - b.n)
    .map(({ r, n }) => {
      const w = byAnswer.get(r.answer) || {};
      return `<li><b>${n}.</b> ${esc(w.clue || r.clue)} ` +
        `<span class="len">(${r.answer.length})</span></li>`;
    });
  return `<h3>${dir === 'across' ? 'Across' : 'Down'}</h3><ul class="clues">${rows.join('')}</ul>`;
}

function render(data, L, grid, num) {
  const bank = data.words.slice()
    .sort((a, b) => a.display.localeCompare(b.display, 'la'))
    .map((w) => `<span class="bankword">${esc(w.display)}</span>`).join('');
  const key = data.words.slice()
    .sort((a, b) => a.display.localeCompare(b.display, 'la'))
    .map((w) => `<li><b>${esc(w.display)}</b> — ${esc(w.clue)}</li>`).join('');

  return `<title>${esc(data.title)}</title>
<style>
  :root { --ink:#111; --rule:#111; --soft:#767676; }
  body { font: 12pt/1.45 Tahoma, Verdana, sans-serif; color: var(--ink); margin: 0; padding: 22px; background:#fff; }
  h1 { font-size: 17pt; margin: 0 0 2px; }
  .sub { color: var(--soft); font-size: 10pt; margin: 0 0 14px; }
  .grid { display: block; margin: 0 auto 16px; max-width: 100%; height: auto; }
  .cols { column-count: 2; column-gap: 26px; }
  .clues { list-style: none; padding: 0; margin: 0 0 10px; }
  .clues li { margin: 0 0 4px; break-inside: avoid; font-size: 10.5pt; }
  .len { color: var(--soft); }
  h3 { font-size: 11pt; margin: 8px 0 5px; break-after: avoid; }
  .bank { border: 1px solid #bbb; padding: 8px 10px; margin: 12px 0; break-inside: avoid; }
  .bank h3 { margin-top: 0; }
  .bankword { display: inline-block; margin: 0 12px 4px 0; }
  .note { font-size: 9.5pt; color: var(--soft); margin: 8px 0 0; }
  .page { break-before: page; }
  @page { size: portrait; margin: 12mm; }
  @media print {
    body { padding: 0; }
    .noprint { display: none; }
    /* the grid is stroked vector, so nothing here depends on background printing */
    .grid { break-inside: avoid; }
  }
</style>
<h1>${esc(data.title)}</h1>
<p class="sub">${data.words.length} words${data.set ? ` · ${esc(data.set)}` : ''}</p>
${gridSVG(L, grid, num, { solved: false })}
<div class="cols">${clueList(L, data.words, 'across', num)}${clueList(L, data.words, 'down', num)}</div>
<div class="bank"><h3>Word bank</h3>${bank}</div>
<div class="page"><h1>Answer key — ${esc(data.title)}</h1>
${gridSVG(L, grid, num, { solved: true })}
<ol class="clues cols">${key}</ol></div>`;
}

// ---------------------------------------------------------------- the fillable version
// Exolve (MIT, vendored in renderers/vendor) turns a plain-text spec into an interactive
// crossword. The CSS and JS are INLINED so the file a student receives works offline with
// nothing to fetch -- these get emailed and uploaded, not served.
//
// THE SOLUTION LETTERS ARE BARE. Owner, 2026-09-09: students are not required to produce
// macrons. Online that matters more than on paper -- a macron in the grid would mean typing
// one on a normal keyboard. It is safe for exactly the reason the printed version is: the
// LAYOUT already crossed on the macronized form, so no long vowel ever shares a cell with a
// short one and collapsing them cannot create a contradiction.
function exolveHTML(data, L, grid, num) {
  const bare = (ch) => ch.normalize('NFD').replace(/[̀-ͯ]/g, '');
  const rows = [];
  for (let y = 0; y < L.rows; y++) {
    let row = '';
    for (let x = 0; x < L.cols; x++) {
      const c = grid.get(`${x},${y}`);
      row += c ? bare(c.ch) : '.';
    }
    rows.push('    ' + row);
  }
  const byAnswer = new Map(data.words.map((w) => [w.answer, w]));
  const clues = (dir) => L.result
    .filter((r) => r.orientation === dir)
    .map((r) => ({ r, n: num.get(`${r.startx - 1},${r.starty - 1}`) }))
    .sort((a, b) => a.n - b.n)
    .map(({ r, n }) => {
      const w = byAnswer.get(r.answer) || {};
      // The annotation after the parenthesis is revealed on "Reveal" -- so that is where the
      // MACRONIZED form goes. The student types bare letters and is then shown the spelling
      // the class actually uses, which is the only place the distinction can be taught here.
      const clue = (w.clue || '').replace(/\s+/g, ' ').trim();
      return `    ${n} ${clue} (${r.answer.length}) ${w.display || ''}`;
    }).join('\n');

  const spec = [
    'exolve-begin',
    `  exolve-id: ${(data.corpus || 'latin')}-${(data.set || 'crossword')}`,
    `  exolve-title: ${data.title}`,
    // A FREEFORM grid is mostly empty, and Exolve's default paints the empty area solid
    // black -- correct for a dense cryptic, wrong here, where two thirds of the grid would
    // be a black slab. White background plus a stroke on each light cell (below) matches the
    // printed sheet, which is the point: the two versions should look like the same puzzle.
    '  exolve-option: color-background:white',
    `  exolve-width: ${L.cols}`,
    `  exolve-height: ${L.rows}`,
    '  exolve-grid:',
    ...rows,
    '  exolve-across:',
    clues('across'),
    '  exolve-down:',
    clues('down'),
    'exolve-end',
  ].join('\n');

  const css = fs.readFileSync(path.join(__dirname, 'vendor', 'exolve-m.css'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, 'vendor', 'exolve-m.js'), 'utf8');
  return `<!DOCTYPE html>
<html lang="la"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${esc(data.title)}</title>
<style>${css}</style>
<style>
  /* Cells only -- the lone background rect is a direct child of the svg, the cells sit
     inside a <g> each. Stroking the background too would draw a box round the whole
     bounding area, including the empty parts. */
  .xlv-grid g rect { stroke: #111; stroke-width: 0.6; }
  body { font-family: Tahoma, Verdana, sans-serif; margin: 0 auto; max-width: 60em; padding: 12px; }
</style>
<script>${js}</script>
</head><body>
<script>createExolve(${JSON.stringify(spec)});</script>
</body></html>`;
}

function main() {
  const [inp, outp, seedArg] = process.argv.slice(2);
  if (!inp || !outp) {
    console.error('usage: node renderers/crossword.js <in.json> <out.html> [seed]');
    return 1;
  }
  const seed = Number(seedArg || 1);
  const data = JSON.parse(fs.readFileSync(inp, 'utf8'));
  const L = layout(data.words.map((w) => ({ clue: w.clue, answer: w.answer })), seed);
  const grid = cells(L);
  const num = numbering(L, grid);
  const misnumbered = checkNumbering(L, num);
  if (misnumbered.length) {
    throw new Error('grid numbering disagrees with the layout library:\n  ' +
      misnumbered.join('\n  '));
  }
  fs.mkdirSync(path.dirname(path.resolve(outp)), { recursive: true });
  fs.writeFileSync(outp, render(data, L, grid, num), 'utf8');
  const fillable = outp.replace(/\.html?$/i, '') + '.fillable.html';
  fs.writeFileSync(fillable, exolveHTML(data, L, grid, num), 'utf8');
  const longCells = [...grid.values()].filter((c) => c.long).length;
  console.log(`  ${data.words.length} words · grid ${L.cols}x${L.rows} · ` +
    `${longCells} long-vowel cell(s) · seed ${seed}`);
  console.log(`    print    -> ${outp}`);
  console.log(`    fillable -> ${fillable}`);
  return 0;
}

process.exitCode = main();
