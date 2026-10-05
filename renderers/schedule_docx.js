// schedule_docx.js -- a course schedule in the Mythology schedule's format (syllabus_docx.js), from a
// hand-written plan JSON rather than syllabus.py's solve. For a class whose weeks are a RULED plan
// (latin-iii, plan H7) and which has no second-semester units yet. Styles are copied, not shared:
// change both if the look changes.
//   node renderers/schedule_docx.js editions/schedules/latin-iii-fall-2026.json editions/schedules/LatinIII-Schedule-Fall-2026.docx
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  PageOrientation, convertInchesToTwip,
} = require("docx");

const DATA = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const OUT = process.argv[3];

// ---- palette / metrics -------------------------------------------------
const INK = "1A1A1A", MUTED = "5A5A5A", RULE = "BFBFBF";
const HEADBG = "E8E4DC", BREAKBG = "F2EFE9", SHORTBG = "FBF7EE";
const ACCENT = "7A3B12", DUEBG = "F6EDE0";   // major work: warm, and unmistakably not a week
// Google Docs has neither Cambria nor Calibri and substitutes silently on import,
// which re-wraps columns whose widths were computed against Calibri's metrics.
// Georgia and Arial are both in Google Docs' default list AND on Windows, so the
// file renders the same in Docs, Word and ONLYOFFICE.
const SERIF = "Georgia", SANS = "Arial";

const TOTAL = 9360;                      // Letter, 1" margins
// Four columns now: the recurring vocabulary cycle has left the table entirely (it is
// stated once in the preamble as routine), and major work has its own full-width row.
const COLS = [780, 2180, 1500, 4900];
if (COLS.reduce((a, b) => a + b, 0) !== TOTAL) throw new Error("columns must sum to " + TOTAL);

const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtDates = (ds) => {
  const parts = ds.map((s) => s.split("-").map(Number));
  let out = [], lastM = null;
  for (const [, m, d] of parts) {
    out.push((m === lastM ? "" : MONTH[m - 1] + " ") + d);
    lastM = m;
  }
  return out.join(" · ");
};

// ---- small builders ----------------------------------------------------
const run = (text, o = {}) => new TextRun({
  text, font: o.font || SANS, size: o.size || 19,
  bold: !!o.bold, italics: !!o.italics, color: o.color || INK,
});
const para = (text, o = {}) => new Paragraph({
  alignment: o.align, spacing: { before: o.before || 0, after: o.after === undefined ? 40 : o.after },
  indent: o.indent, children: Array.isArray(text) ? text : [run(text, o)],
});
const cell = (children, o = {}) => new TableCell({
  width: { size: o.w, type: WidthType.DXA },
  columnSpan: o.span,
  shading: o.bg ? { type: ShadingType.CLEAR, fill: o.bg, color: "auto" } : undefined,
  margins: { top: 70, bottom: 70, left: 110, right: 110 },
  verticalAlign: "top",
  children,
});
const noBorders = {
  top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
  left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
  insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE },
};
const tableBorders = {
  top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
  left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
  insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
  insideVertical: { style: BorderStyle.NONE },
};

// ---- the Semester 1 table ---------------------------------------------
const HEADS = ["Week", "Meetings", "Class time", "Latin read"];
const rows = [
  new TableRow({
    tableHeader: true,
    children: HEADS.map((h, i) =>
      cell([para(h, { bold: true, size: 17, color: MUTED })], { w: COLS[i], bg: HEADBG })),
  }),
];

for (const c of DATA.chunks) {
  // Two deliberate lines, not one that wraps: "3 classes · 170 min" is wider than the
  // column and breaks after "170", stranding "min" on its own.
  const time = `${c.dates.length} class${c.dates.length > 1 ? "es" : ""}`;
  let readingRuns;
  if (c.reading) {
    readingRuns = [run(c.reading, { font: SERIF, size: 19 })];
  } else if (c.kind === "background") {
    readingRuns = [run("Background — ", { italics: true, color: MUTED }),
    run(c.note, { bold: true })];
  } else {
    readingRuns = [run("No new Latin", { italics: true, color: MUTED })];
  }
  const bg = c.short ? SHORTBG : undefined;

  rows.push(new TableRow({
    children: [
      cell([para(String(c.chunk), { bold: true, color: MUTED })], { w: COLS[0], bg }),
      cell([para(fmtDates(c.dates))], { w: COLS[1], bg }),
      cell([para(time, { size: 17, color: MUTED, after: 0 }),
      para(`${c.minutes} min`, { size: 17, color: MUTED, after: 0 }),
      ...(c.minutes_note ? [para(c.minutes_note, { size: 15, italics: true, color: MUTED, after: 0 })]
        : c.short ? [para("short week", { size: 15, italics: true, color: MUTED, after: 0 })] : [])],
        { w: COLS[2], bg }),
      // A background week names WHAT IS READ IN TRANSLATION, one text per line. Students
      // otherwise have no way to know the week has reading in it at all.
      // The support reader's divisions, under the line numbers. Students hold two books
      // and the week should be named in both; the Class time column already sets the
      // precedent that a cell here may carry two lines.
      cell([para(readingRuns, { after: (c.background || []).length || c.support ? 24 : 40 }),
      ...(c.support ? [para(c.support, { size: 17, color: MUTED, after: 0 })] : []),
      ...(c.background || []).map((t, i) => para([
        run("• ", { color: MUTED }), run(t, { font: SERIF, size: 18 }),
      ], { after: i === c.background.length - 1 ? 0 : 20 }))],
        { w: COLS[3], bg }),
    ],
  }));

  // MAJOR WORK GETS ITS OWN FULL-WIDTH ROW. It is the only thing in the table that does
  // not recur, so it should not have to compete for width with a date and a citation.
  for (const m of c.major) {
    // Short label: the preamble names it in full, and "ANNOTATION DEEP-DIVE" plus the
    // longest subject overran the 6.5" band in Arial, which is wider than Calibri was.
    const label = m.kind === "deep-dive" ? "DEEP-DIVE" : m.label.toUpperCase();
    rows.push(new TableRow({
      children: [cell([
        para([
          run("▸  ", { color: ACCENT, bold: true, size: 20 }),
          run(label, { bold: true, size: 19, color: ACCENT }),
          ...(m.subject ? [run(" · ", { color: MUTED }), run(m.subject, { bold: true, size: 19 })] : []),
          // A quiz is SAT, not handed in, so it is not "due" -- it just has a date.
          // A project is ASSIGNED and then DUE; a quiz is simply sat. The verb comes from
          // the plan, because "due" is wrong for most of what lands in this band.
          run(" — " + (m.verb !== undefined ? (m.verb ? m.verb + " " : "")
            : (m.kind === "quiz" ? "" : "due ")) + m.due_label, { size: 17, color: MUTED }),
        ], { after: 0 }),
      ], { w: TOTAL, span: 4, bg: DUEBG })],
    }));
  }

  if (c.gap_after) {
    rows.push(new TableRow({
      children: [cell([para(c.gap_after.toUpperCase(),
        { size: 15, bold: true, color: MUTED, align: AlignmentType.CENTER, after: 0 })],
        { w: TOTAL, span: 4, bg: BREAKBG })],
    }));
  }
}

const sem1Table = new Table({
  columnWidths: COLS, width: { size: TOTAL, type: WidthType.DXA },
  borders: tableBorders, rows,
});

const doc = new Document({
  creator: "Latin Vocab Toolkit — renderers/schedule_docx.js",
  title: DATA.title,
  styles: { default: { document: { run: { font: SANS, size: 19, color: INK } } } },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840, orientation: PageOrientation.PORTRAIT },
        margin: {
          top: convertInchesToTwip(0.85), bottom: convertInchesToTwip(0.85),
          left: convertInchesToTwip(1), right: convertInchesToTwip(1),
        },
      },
    },
    children: [
      para("Course Schedule", { font: SERIF, size: 32, bold: true, after: 60 }),
      para(DATA.preamble, { italics: true, color: MUTED, after: 200 }),
      para(DATA.heading, { font: SERIF, size: 26, bold: true, after: 120 }),
      sem1Table,
      para("", { after: 120 }),
      para(DATA.summary, { size: 17, color: MUTED, after: 40 }),
    ],
  }],
});

Packer.toBuffer(doc).then((b) => {
  try {
    fs.writeFileSync(OUT, b);
    console.log("wrote " + OUT);
  } catch (e) {
    if (e.code !== "EBUSY" && e.code !== "EPERM") throw e;
    const alt = OUT.replace(/\.docx$/i, "") + " (new).docx";
    fs.writeFileSync(alt, b);
    console.log("!! " + OUT + " is OPEN and was left untouched; wrote " + alt);
  }
});
