// swyk_docx.js -- a SWYK (Show What You Know) reading quiz, as a Word file.
//
//   node renderers/swyk_docx.js quiz.json OUT.docx
//
// The data comes from editions/swyk/quiz.py, which chooses everything; this only draws it.
// The layout is the owner's LaTeX quiz template (v3.0), page for page:
//   1. the story (Shantell Sans, large), guess words underlined, then a Nota Bene gloss box
//   2. a blank back, so the questions start on a fresh sheet when printed double-sided
//   3. Part 1 Key Words (each in its story sentence) . Part 2 Guessing Meaning . Part 3 Main
//      Idea & Supporting Details . Part 4 Inferential
//   4. Part 5 the rubric, on its own page with narrower margins
//   5. the Honor Code (signed) and the ungraded feedback questions
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, BorderStyle, Header, PageBreak,
  Table, TableRow, TableCell, WidthType, TableLayoutType, ShadingType, UnderlineType,
  convertInchesToTwip, TabStopType,
} = require("docx");

const Q = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const OUT = process.argv[3];

// The template's fonts. Both are free (Google Fonts); if a machine lacks one, Word substitutes.
const STORY_FONT = "Shantell Sans", BODY_FONT = "Atkinson Hyperlegible";
const SYMBOL_FONT = "Segoe UI Symbol";
const IN = convertInchesToTwip;

const run = (text, o = {}) => new TextRun({
  text, font: o.font || BODY_FONT, size: o.size || 24, bold: !!o.bold, italics: !!o.italics,
  underline: o.underline ? { type: o.underline } : undefined, border: o.border,
});
const para = (children, o = {}) => new Paragraph({
  children, alignment: o.align, keepNext: !!o.keepNext, keepLines: !!o.keepLines,
  pageBreakBefore: !!o.pageBreakBefore, indent: o.indent, tabStops: o.tabStops,
  spacing: { before: o.before || 0, after: o.after === undefined ? 80 : o.after, line: o.line },
});
const gap = (inches) => para([run("")], { after: IN(inches) });
const heading = (text, o = {}) => para([run(text, { bold: true, size: 30 })],
  { before: o.pageBreakBefore ? 0 : 240, after: 120, keepNext: true, pageBreakBefore: !!o.pageBreakBefore });
const instruction = (children) => para(children, { after: 120, keepNext: true });
const it = (text) => run(text, { italics: true, size: 21 });
const nameLine = (size = 24) => [run("Nōmen mihi est: ", { size }), run(" ".repeat(40), { size, underline: UnderlineType.SINGLE })];

// ---------------------------------------------------------------- page 1: the story
const story = [
  para(nameLine(), { after: 360 }),
  ...Q.story.map((runs) => para(runs.map((r) => run(r.text, {
    font: STORY_FONT, size: 2 * (Q.story_size || 15), underline: r.guess ? UnderlineType.SINGLE : undefined,
  })), { after: 200, line: 300 })),
];
if (Q.glosses.length) {
  story.push(para([run("")], { before: 480, after: 120 }));
  story.push(para([run("Nōtā Bene:", { bold: true, size: 21 })], { after: 60, keepNext: true }));
  for (const g of Q.glosses) {
    story.push(para([run("•  "), run(g.term, { bold: true, size: 21 }), run(`: ${g.gloss}`, { size: 21 })],
      { after: 20, indent: { left: IN(0.25) } }));
  }
}

// ---------------------------------------------------------------- the questions
const numbered = (n, children, o = {}) => para([run(`${n}.  `, { bold: true }), ...children],
  { keepNext: true, after: 80, indent: { left: IN(0.35), hanging: IN(0.35) }, ...o });

const qs = [];
qs.push(heading("Part 1: Key Word Recognition"));
qs.push(instruction([it("Based on the story and your prior knowledge, give the English meaning of the word in "
  + "bold, as it is used in this sentence from the story.")]));
Q.key_words.forEach((k, i) => {
  qs.push(numbered(i + 1, k.sentence.map((s) => run(s.text, { font: STORY_FONT, bold: !!s.key, size: 24 }))));
  qs.push(para([run(`${k.form}: `, { bold: true }), run(" ".repeat(60), { underline: UnderlineType.SINGLE })],
    { after: 280, indent: { left: IN(0.35) } }));
});

qs.push(heading("Part 2: Guessing Meaning from Context"));
qs.push(instruction([it("The underlined words are new. Based on etymology and context, what do you think they "
  + "mean? Explain your reasoning.")]));
Q.guesses.forEach((g, i) => {
  const [before, after] = g.prompt.split("{w}");
  qs.push(numbered(i + 1, [run(before), run(g.word, { underline: UnderlineType.SINGLE }), run(after || "")]));
  qs.push(para([run("“" + g.sentence + "”", { font: STORY_FONT, italics: true, size: 22 })],
    { after: IN(g.space), indent: { left: IN(0.35) } }));
});

// Part 3's highlighting instructions, each drawn the way it asks to be marked.
const markRun = (mark) => {
  const [verb, ...rest] = mark.split(" ");
  const tail = " " + rest.join(" ");
  if (verb === "Draw" && rest[0] === "a" && rest[1] === "box")
    return [run("Draw a ", { italics: true, size: 21 }),
            run("box", { italics: true, size: 21, border: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } }),
            it(" " + rest.slice(2).join(" "))];
  if (verb === "Circle")
    return [run("◯ ", { font: SYMBOL_FONT, size: 21 }), it(mark)];
  if (verb === "Underline")
    return [run("Underline", { italics: true, size: 21, underline: UnderlineType.SINGLE }), it(tail)];
  if (verb === "Draw" && rest[0] === "a" && rest[1] === "squiggly")
    return [it("Draw a "), run("squiggly line", { italics: true, size: 21, underline: UnderlineType.WAVE }),
            it(" " + rest.slice(3).join(" "))];
  return [it(mark)];
};

qs.push(heading("Part 3: Main Idea & Supporting Details"));
// The instruction comes from quiz.py: it differs by whether the detail standard is taught per
// question (Latin I-II) or given once here (Latin III).
qs.push(instruction([it(Q.part3_instruction)]));
Q.main.forEach((m, i) => {
  // Two tiers, visibly, where the quiz has them: the main-idea question, then the invitation to detail.
  qs.push(numbered(i + 1, [run(m.q)]));
  if (m.detail)
    qs.push(para([run("In as much detail as possible: ", { bold: true, size: 22 }), run(m.detail, { size: 22 })],
      { keepNext: true, after: 60, indent: { left: IN(0.35) } }));
  qs.push(para(markRun(m.mark), { after: IN(m.space), indent: { left: IN(0.35) } }));
});

// Its own page (owner, 2026-09-30): a paragraph needs the room, and the space left under Part 3
// was not enough. The page break is the space -- the rubric section starts the next page.
qs.push(heading("Part 4: Inferential Comprehension", { pageBreakBefore: true }));
qs.push(instruction([it("Answer in one thoughtful paragraph.")]));
Q.inference.forEach((q, i) => {
  qs.push(numbered(i + 1, [run(q.q)]));
  qs.push(para([run(q.instruction, { italics: true, bold: true, size: 21 })],
    { after: IN(q.space), indent: { left: IN(0.35) } }));
});

// ---------------------------------------------------------------- the rubric
const R = Q.rubric;
const PAGE_W = 12240, RUBRIC_MARGIN = IN(0.5);
const TW = PAGE_W - 2 * RUBRIC_MARGIN, SKILL_W = IN(1.45), CELL_W = Math.floor((TW - SKILL_W) / 5);
const cellP = (children, o = {}) => new Paragraph({ children, alignment: o.align, spacing: { before: 20, after: 20 } });
const small = (text, o = {}) => run(text, { size: o.size || 16, bold: o.bold, italics: o.italics });
const cell = (children, w, o = {}) => new TableCell({
  children: Array.isArray(children) ? children : [children], width: { size: w, type: WidthType.DXA },
  columnSpan: o.span, shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: "auto" } : undefined,
  margins: { top: 40, bottom: 40, left: 70, right: 70 },
});
const rows = [];
for (const sec of R.sections) {
  rows.push(new TableRow({ children: [cell(cellP([small(sec.title, { bold: true, size: 18 })], { align: AlignmentType.CENTER }), TW, { span: 6, fill: "E8E8E8" })] }));
  rows.push(new TableRow({ tableHeader: false, children: [
    cell(cellP([small("Skill", { bold: true })]), SKILL_W),
    ...R.levels.map((l) => cell(cellP([small(l, { bold: true })], { align: AlignmentType.CENTER }), CELL_W)),
  ] }));
  for (const r of sec.rows) {
    const skill = [cellP([small(r.skill, { bold: true })])];
    if (r.sub) skill.push(cellP([small(r.sub, { italics: true })]));
    rows.push(new TableRow({ cantSplit: true, children: [
      cell(skill, SKILL_W), ...r.cells.map((c) => cell(cellP([small(c)]), CELL_W)),
    ] }));
  }
}
const rubric = [
  heading("Part 5: Self-Assessment"),
  instruction([it("Now that you’ve finished, rate your understanding of the story by circling ONE descriptor in each row.")]),
  new Table({ rows, width: { size: TW, type: WidthType.DXA }, layout: TableLayoutType.FIXED,
              columnWidths: [SKILL_W, ...Array(5).fill(CELL_W)] }),
];

// ---------------------------------------------------------------- honor code + feedback
const line = " ".repeat(52);
const last = [
  heading("Honor Code Statement"),
  para([run(Q.honor)], { after: 360, line: 320 }),
  para([run("Signature: "), run(line, { underline: UnderlineType.SINGLE }), run("    Date: "),
        run(" ".repeat(22), { underline: UnderlineType.SINGLE })], { after: 600 }),
  para([it(Q.feedback.intro)], { after: 240 }),
  ...Q.feedback.questions.map((f) => para([run(f, { bold: true })], { after: IN(1.1), keepNext: true })),
];

// ---------------------------------------------------------------- assembly
const letter = (margin) => ({ page: { size: { width: PAGE_W, height: 15840 },
  margin: { top: margin, bottom: margin, left: margin, right: margin, header: IN(0.4) } } });
const nameHeader = new Header({ children: [para(nameLine(21), { align: AlignmentType.RIGHT })] });
const empty = new Header({ children: [para([run("")])] });

const sections = [{ properties: letter(IN(1)), headers: { default: empty }, children: story }];
if (Q.blank_back) sections.push({ properties: letter(IN(1)), headers: { default: empty }, children: [para([run("")])] });
sections.push({ properties: letter(IN(1)), headers: { default: nameHeader }, children: qs });
sections.push({ properties: letter(RUBRIC_MARGIN), headers: { default: nameHeader }, children: rubric });
sections.push({ properties: letter(IN(1)), headers: { default: nameHeader }, children: last });

Packer.toBuffer(new Document({ sections })).then((buf) => {
  try {
    fs.writeFileSync(OUT, buf);
  } catch (e) {
    if (e.code !== "EBUSY" && e.code !== "EPERM") throw e;
    // Windows locks a .docx that Word/OnlyOffice has open. Say so, instead of a stack trace.
    console.error(`${OUT} is open in another program -- close it and build again, or pass --out.`);
    process.exit(3);
  }
});
