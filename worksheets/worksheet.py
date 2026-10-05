#!/usr/bin/env python3
"""worksheet.py -- fillable, printable exercise worksheets as PDFs, with a print-size audit.

    python worksheet.py --data DIR --out DIR            # build every sheet, then audit them
    python worksheet.py --data DIR --out DIR --audit    # audit only
    python worksheet.py --data DIR --out DIR --font-regular X.ttf --font-bold Y.ttf --font-italic Z.ttf

A student can type into the blue boxes and save, or print the sheet and write by hand: both
work, because every answer space is sized for HANDWRITING first.

THE CONTENT lives in --data, in either of two forms:
  * `packets_data.json`: one JSON object with "W" (required) and, optionally, "HELP", "GLOSS"
    and any of the settings below under the same names. Content stays out of code this way;
    `example/` in the published repo is one.
  * `packets_data.py` (+ an optional `packets_help.py`): the same names as Python, for content
    that is easier to write with a helper function or a loop.
`W` lists the sheets and their exercises; `HELP` is an English line under an exercise's
instruction, `GLOSS` glosses words in its questions; both are keyed by the exercise's `ref`.
One sheet per entry of `W`:

    W = [(title, span, dates, [exercise, ...]), ...]
    exercise = {"ref": "ex. 1", "instr": "Quis est?", "items": [...], "box": None, "note": None}

Item kinds: ("q", text) a question with a two-line answer · ("short", text) a one-word answer
at the right · ("cloze", "text with ___ gaps") numbered fields · ("vf", statement) vērum/falsum
plus a correction line · ("order", text) a box for a number · ("match", [stems], [options]) a
letter box beside each option · ("choice", stem, [options]) checkboxes · ("table", [left],
[right]) idem/contrārium columns · ("image", "<source>_<page>.png", [boxes], mode) pictures
cropped from a scanned PDF named in SOURCES ("example" mode shows the first as the model).

SETTINGS a data file (or the caller of build()) may give, with their defaults: SUBTITLE ("")
and REF_LABEL ("") for the sheet header and each exercise's reference line; INTRO (a line
telling the student how to fill the sheet in); SOURCES ({}: {key: {"pdf": path, "flip":
{pages} | "odd" | None, "offset": int}}, the scans that "image" items crop from); FONTS
(Palatino on Windows); CLEAN_GLOB (None: which old PDFs in --out to delete first); filename
(title, span) -> the PDF's name.

PRINT SIZES -- the rules this file enforces, and audit() measures every built PDF against them:
  * body text >= 12 pt, help/gloss >= 11 pt (worksheet guidance: 12 pt body for readability in print;
    nothing a student must read below 11 pt).
  * a handwritten answer line >= 24 pt tall (wide-ruled paper is 11/32" = 24.75 pt; college 9/32" =
    20.25 pt is the floor for adolescents, so we use wide).
  * a sentence answer gets TWO lines (>= 48 pt); a one-word answer >= 2.25" (162 pt) wide.
  * a letter / number box >= 24 x 24 pt; a checkbox >= 14 pt square.
  * no exercise heading, and no question, is split from its answer space by a page break: every block
    is MEASURED before it is drawn and moved whole to the next page if it does not fit.

FONTS must cover the macron vowels (ā ē ī ō ū ȳ); the PDF's built-in fonts do not. Needs
PyMuPDF and Pillow (`pip install pymupdf pillow`).

Written for the toolkit's Latin III packets (editions/packets_h7/, 2026-10-04), whose content
is a textbook's exercises and stays private; made general the same day so the engine could be
published (docs/WORK_ORDER_tools-tidy.md).
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

import pymupdf as f
from PIL import Image

try:                                   # macrons in the report, on a Windows terminal
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

#: Set by build(). Module globals, so the drawing code below reads them as it always did.
FONT: dict = {}
FO: dict = {}
OUT: Path = Path(".")
SRC: dict = {}
HELP: dict = {}
GLOSS: dict = {}
CFG: dict = {}

DEFAULT_FONTS = {"r": "C:/Windows/Fonts/pala.ttf", "b": "C:/Windows/Fonts/palab.ttf",
                 "i": "C:/Windows/Fonts/palai.ttf"}
DEFAULT_INTRO = ("Type in the blue boxes and save, or print and write by hand. Whenever you write "
                 "Latin: short and simple is perfect, and almost everything you need is already in "
                 "the story. Borrow it!")
PW, PH, M = 612, 792, 50
X1 = PW - M
BODY, LEAD = 12, 16.5
SMALL, SLEAD = 11, 14.5
LINE_H = 24          # one handwritten line
SENT_H = 50          # a sentence answer: two lines
BOX = 26             # letter / number / ordo box
CHK = 15             # checkbox
SHORT_W = 170        # one-word answer field
GAP = 6
RED = (0.45, 0.1, 0.05)
GREY = (0.3, 0.3, 0.3)
FIELD_FILL = (0.94, 0.96, 1.0)


def wrap(text, width, style="r", size=BODY):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if FO[style].text_length(t, size) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


class Doc:
    def __init__(self, title):
        self.d = f.open(); self.n = 0; self.title = title; self.p = None
        self.new_page()

    def new_page(self):
        self.p = self.d.new_page(width=PW, height=PH)
        for k, v in FONT.items():
            self.p.insert_font(fontname="P" + k, fontfile=v)
        self.y = M
        self.p.insert_text((M, PH - 28), f"{self.title} · page {self.d.page_count}",
                           fontname="Pi", fontsize=9, color=(0.4, 0.4, 0.4))

    def fits(self, h):
        return self.y + h <= PH - M

    def need(self, h):
        if not self.fits(h):
            self.new_page()

    def text(self, text, x=M, width=None, style="r", size=BODY, color=(0, 0, 0), lead=LEAD):
        for ln in wrap(text, width or (X1 - x), style, size):
            self.p.insert_text((x, self.y + size), ln, fontname="P" + style, fontsize=size, color=color)
            self.y += lead

    def field(self, rect, name, kind="text", multiline=False, choices=None):
        w = f.Widget()
        w.field_name = f"{name}_{self.n}"
        w.rect = f.Rect(rect)
        w.border_color = (0.5, 0.56, 0.72); w.border_width = 0.7
        w.fill_color = FIELD_FILL
        if kind == "check":
            w.field_type = f.PDF_WIDGET_TYPE_CHECKBOX
        elif kind == "combo":
            w.field_type = f.PDF_WIDGET_TYPE_COMBOBOX; w.choice_values = choices; w.field_value = choices[0]
            w.text_fontsize = 12
        else:
            w.field_type = f.PDF_WIDGET_TYPE_TEXT
            w.text_fontsize = 0 if multiline else 12
            if multiline:
                w.field_flags |= f.PDF_TX_FIELD_IS_MULTILINE
        self.p.add_widget(w)
        self.n += 1


def th(text, width, style="r", size=BODY, lead=LEAD):
    """height of wrapped text"""
    return lead * len(wrap(text, width, style, size))


# ------------------------------------------------------------------ item blocks: (height, draw)
IND = M + 16           # item indent
SUB = M + 34           # answer indent


def blk_short(D, txt, name):
    w = X1 - IND - SHORT_W - 10
    h = max(th(txt, w), LINE_H) + GAP
    def draw():
        y0 = D.y
        D.text(txt, x=IND, width=w)
        lines = len(wrap(txt, w))
        D.field((X1 - SHORT_W, y0 + LEAD * lines - LINE_H + 4, X1, y0 + LEAD * lines + 4), name)
        D.y = max(D.y, y0 + LINE_H) + GAP
    return h, draw


def blk_sentence(D, txt, name):
    h = th(txt, X1 - IND) + SENT_H + GAP + 2
    def draw():
        D.text(txt, x=IND)
        D.field((SUB, D.y + 2, X1, D.y + 2 + SENT_H), name, multiline=True)
        D.y += SENT_H + GAP + 2
    return h, draw


def blk_cloze(D, txt, name):
    n = txt.count("___")
    if n == 1:
        return blk_short(D, txt.replace("___", "_______"), name)
    parts = txt.split("___")
    shown = "".join(p + (f" ({i + 1}) ______" if i < n else "") for i, p in enumerate(parts))
    per = 2
    rows = (n + per - 1) // per
    h = th(shown, X1 - IND) + rows * (LINE_H + GAP) + GAP
    def draw():
        D.text(shown, x=IND)
        colw = (X1 - SUB) / per
        for i in range(n):
            r, c = divmod(i, per)
            y = D.y + 4 + r * (LINE_H + GAP)
            x = SUB + c * colw
            D.p.insert_text((x, y + 17), f"({i + 1})", fontname="Pr", fontsize=SMALL)
            D.field((x + 26, y, x + colw - 10, y + LINE_H), name)
        D.y += rows * (LINE_H + GAP) + GAP
    return h, draw


def blk_vf(D, txt, name):
    w = X1 - IND - 70
    h = max(th(txt, w), BOX) + LINE_H + 2 * GAP
    def draw():
        y0 = D.y
        D.text(txt, x=IND, width=w)
        D.field((X1 - 56, y0, X1, y0 + BOX), name + "vf", kind="combo", choices=[" ", "V", "F"])
        D.y = max(D.y, y0 + BOX) + 3
        D.p.insert_text((SUB, D.y + 16), "sī falsum:", fontname="Pi", fontsize=SMALL, color=GREY)
        D.field((SUB + 58, D.y, X1, D.y + LINE_H), name + "cor")
        D.y += LINE_H + GAP + 3
    return h, draw


def blk_boxline(D, txt, name, x_text=IND + BOX + 8):
    """a letter/number box at the left of a line of text (match options, ordering)."""
    w = X1 - x_text
    h = max(th(txt, w), BOX) + 4
    def draw():
        y0 = D.y
        D.field((IND, y0, IND + BOX, y0 + BOX), name)
        D.y += (BOX - LEAD) / 2
        D.text(txt, x=x_text, width=w)
        D.y = max(D.y, y0 + BOX) + 4
    return h, draw


def blk_lines(D, lines, x=IND, style="r"):
    h = sum(th(t, X1 - x, style) for t in lines) + 4
    def draw():
        for t in lines:
            D.text(t, x=x, style=style)
        D.y += 4
    return h, draw


def blk_choice(D, stem, opts, name):
    h = (th(stem, X1 - IND) if stem else 0) + sum(max(th(o, X1 - SUB - 22), CHK + 6) for o in opts) + GAP
    def draw():
        if stem:
            D.text(stem, x=IND)
        for o in opts:
            y0 = D.y
            D.field((SUB, y0 + 2, SUB + CHK, y0 + 2 + CHK), name, kind="check")
            D.text(o, x=SUB + 22, width=X1 - SUB - 22)
            D.y = max(D.y, y0 + CHK + 6)
        D.y += GAP
    return h, draw


def blk_table_row(D, l, r, name):
    half = (X1 - IND) / 2
    h = LINE_H + GAP
    def draw():
        for c, t in enumerate((l, r)):
            if t:
                x = IND + c * half
                D.p.insert_text((x, D.y + 17), t, fontname="Pr", fontsize=BODY)
                lw = FO["r"].text_length(t, BODY) + 6
                D.field((x + lw, D.y, x + half - 12, D.y + LINE_H), name)
        D.y += LINE_H + GAP
    return h, draw


def crop(png, box):
    """re-render the source page at 300 dpi and crop (boxes were measured at 200 dpi)."""
    key, idx = png.split("_")[0], int(png.split("_")[1].split(".")[0])
    src = SRC[key]
    pg = f.open(src["pdf"])[idx - src.get("offset", 0)]
    pix = pg.get_pixmap(dpi=300)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    rule = src.get("flip")                     # pages scanned upside down
    flip = (idx % 2 == 1) if rule == "odd" else bool(rule) and idx in rule
    if flip:
        im = im.rotate(180)
    return im.crop(tuple(int(v * 1.5) for v in box))


def blk_picture(D, im, label, name, mode, example_text=None):
    """one picture, 2.9" wide, with its answer space beside it."""
    PWID = 210
    ph = min(PWID * im.height / im.width, 160)
    pw = ph * im.width / im.height
    h = max(ph, SENT_H + BOX) + 14
    def draw():
        y0 = D.y
        tmp = OUT / f"_crop_{D.n}.png"; im.save(tmp)
        D.p.insert_image(f.Rect(IND, y0, IND + pw, y0 + ph), filename=str(tmp)); tmp.unlink()
        D.p.insert_text((IND, y0 + ph + 12), label, fontname="Pb", fontsize=SMALL)
        x = IND + PWID + 14
        if example_text:
            D.y = y0
            D.text(example_text, x=x, style="i")
        elif mode == "order":
            D.p.insert_text((x, y0 + 17), "ōrdō:", fontname="Pi", fontsize=SMALL)
            D.field((x + 36, y0, x + 36 + BOX, y0 + BOX), name + "o")
            D.field((x, y0 + BOX + 6, X1, y0 + BOX + 6 + SENT_H), name, multiline=True)
        else:
            D.field((x, y0, X1, y0 + SENT_H), name, multiline=True)
        D.y = y0 + h
    return h, draw


def together(blocks):
    """several blocks that must stay on one page (a match's stems AND its options; a whole table)."""
    def draw():
        for _, d in blocks:
            d()
    return sum(h for h, _ in blocks), draw


def blocks_for(D, e, k):
    """the exercise as a list of (height, draw) blocks; [0] is the heading (+ help, gloss, box)."""
    base = f"e{k}"
    has_example = any(it[0] == "image" and it[3] == "example" for it in e["items"])
    head = [f"{k}. {e['instr']}"]
    def draw_head():
        D.y += 8
        D.text(head[0], style="b", size=13, lead=17)
        D.text(f"({CFG['REF_LABEL'] + ' ' if CFG['REF_LABEL'] else ''}{e['ref']})", style="i", size=10,
               color=(0.45, 0.45, 0.45), lead=13)
        if HELP.get(e["ref"]):
            D.text("Help: " + HELP[e["ref"]], x=IND, style="i", size=SMALL, color=GREY, lead=SLEAD)
        if GLOSS.get(e["ref"]):
            D.y += 2
            D.text("Glossae: " + GLOSS[e["ref"]], x=IND, size=SMALL, color=(0.15, 0.3, 0.15), lead=SLEAD)
        if e.get("note") and not has_example:
            D.y += 2
            D.text(e["note"], x=IND, style="i", size=SMALL, lead=SLEAD)
        if e.get("box"):
            lines = wrap(e["box"], X1 - IND - 24, "r", SMALL)
            bh = SLEAD * len(lines) + 10
            D.p.draw_rect(f.Rect(IND, D.y + 2, X1, D.y + 2 + bh), color=None, fill=(0.98, 0.88, 0.78))
            D.y += 7
            D.text(e["box"], x=IND + 10, width=X1 - IND - 24, size=SMALL, lead=SLEAD)
            D.y += 6
        D.y += 4
    hh = 8 + 17 + 13
    if HELP.get(e["ref"]):
        hh += th("Help: " + HELP[e["ref"]], X1 - IND, "i", SMALL, SLEAD)
    if GLOSS.get(e["ref"]):
        hh += 2 + th("Glossae: " + GLOSS[e["ref"]], X1 - IND, "r", SMALL, SLEAD)
    if e.get("note") and not has_example:
        hh += 2 + th(e["note"], X1 - IND, "i", SMALL, SLEAD)
    if e.get("box"):
        hh += SLEAD * len(wrap(e["box"], X1 - IND - 24, "r", SMALL)) + 13
    hh += 4
    out = [(hh, draw_head)]
    for j, it in enumerate(e["items"]):
        kind, name = it[0], f"{base}_{j}"
        if kind == "short":
            out.append(blk_short(D, it[1], name))
        elif kind == "q":
            out.append(blk_sentence(D, it[1], name))
        elif kind == "cloze":
            out.append(blk_cloze(D, it[1], name))
        elif kind == "vf":
            out.append(blk_vf(D, it[1], name))
        elif kind == "order":
            out.append(blk_boxline(D, it[1], name))
        elif kind == "match":
            stems, opts = it[1], it[2]
            grp = [blk_lines(D, stems)] if stems else []
            grp += [blk_boxline(D, o, f"{name}_{i}") for i, o in enumerate(opts)]
            out.append(together(grp))
        elif kind == "choice":
            out.append(blk_choice(D, it[1], it[2], name))
        elif kind == "table":
            left, right = it[1], it[2]
            half = (X1 - IND) / 2
            hdr = (LEAD + 2, lambda: (D.p.insert_text((IND, D.y + 12), "idem (=)", fontname="Pb", fontsize=SMALL),
                                     D.p.insert_text((IND + half, D.y + 12), "contrārium (≠)", fontname="Pb", fontsize=SMALL),
                                     setattr(D, "y", D.y + LEAD + 2)))
            out.append(together([hdr] + [blk_table_row(D, left[r] if r < len(left) else "", right[r] if r < len(right) else "",
                                                      f"{name}_{r}") for r in range(max(len(left), len(right)))]))
        elif kind == "image":
            _, png, boxes, mode = it
            ims = [crop(png, b) for b in boxes]
            if mode == "example":
                out.append(blk_picture(D, ims[0], "exemplum", name, mode, example_text=e.get("note", "")))
                ims = ims[1:]
            for i, im in enumerate(ims):
                out.append(blk_picture(D, im, f"{chr(97 + i)}.", f"{name}_{i}", mode))
    return out


def render_week(title, span, dates, exs):
    D = Doc(f"{title}: {span}" + (f" · {CFG['SUBTITLE']}" if CFG["SUBTITLE"] else ""))
    D.text(f"{title}: {span}", style="b", size=18, color=RED, lead=24)
    D.text(dates, style="i", size=SMALL, lead=SLEAD)
    D.y += 4
    D.p.insert_text((M, D.y + 17), "Nōmen:", fontname="Pr", fontsize=BODY)
    D.field((M + 50, D.y, M + 320, D.y + LINE_H), "nomen")
    D.y += LINE_H + 8
    if CFG["INTRO"]:
        D.text(CFG["INTRO"], style="i", size=SMALL, color=GREY, lead=SLEAD)
    D.y += 4
    for k, e in enumerate(exs, 1):
        bl = blocks_for(D, e, k)
        # keep the heading with its first answer block (and the first two, when they are short)
        total = sum(h for h, _ in bl)
        body = PH - 2 * M
        # An exercise that fits on one page is kept WHOLE (a student should not flip pages to see the
        # word box or the headlines an item refers to). A longer one keeps its heading with its first
        # answers, and every item stays with its own answer space.
        if total <= body and (e.get("box") or total <= 0.6 * body):
            D.need(total)
        else:
            D.need(bl[0][0] + bl[1][0] + (bl[2][0] if len(bl) > 2 and bl[1][0] < 40 else 0))
        for h, draw in bl:
            D.need(h)
            draw()
    return D


def audit(paths):
    """measure every built PDF against the print rules in the docstring."""
    bad = 0
    for p in paths:
        d = f.open(p)
        sizes, issues = [], []
        for pg in d:
            for b in pg.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    for s in l["spans"]:
                        if s["text"].strip() and pg.rect.height - s["bbox"][3] > 40:   # not the footer
                            sizes.append(round(s["size"], 1))
            for w in pg.widgets():
                r = w.rect
                if w.field_type == f.PDF_WIDGET_TYPE_CHECKBOX:
                    if min(r.width, r.height) < 14: issues.append(f"p{pg.number+1} checkbox {r.width:.0f}x{r.height:.0f}")
                elif r.height < 23.5: issues.append(f"p{pg.number+1} field {w.field_name} {r.height:.0f}pt tall")
                elif r.width < 24: issues.append(f"p{pg.number+1} field {w.field_name} {r.width:.0f}pt wide")
            for img in pg.get_image_info():
                bw, bh = img["bbox"][2] - img["bbox"][0], img["bbox"][3] - img["bbox"][1]
                if max(bw, bh) < 150: issues.append(f"p{pg.number+1} picture only {bw:.0f}x{bh:.0f}pt")
        small = sorted({s for s in sizes if s < 11})
        n_small = sum(1 for s in sizes if s < 11)
        status = "OK" if not issues and n_small <= sum(1 for s in sizes if s == 9.5) else "CHECK"
        print(f"  {Path(p).name:42s} text sizes {min(sizes)}-{max(sizes)} pt (below 11: {small} = book-reference lines)"
              f"  fields/boxes: {'all within rules' if not issues else issues[:4]}")
        bad += bool(issues)
    return bad


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True     # never leave __pycache__ in a data folder (it may be closed)
    spec.loader.exec_module(mod)
    return mod


def _filename(title: str, span: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "-", f"{title} - {span}") + ".pdf"


def build(data: Path, out: Path, audit_only: bool = False, **settings) -> int:
    """Build every sheet in `data`'s packets_data.W into `out`, then audit. `settings` override
    the data file's own (SUBTITLE, REF_LABEL, INTRO, SOURCES, FONTS, CLEAN_GLOB, filename)."""
    global FONT, FO, OUT, SRC, HELP, GLOSS, CFG
    data, OUT = Path(data), Path(out)
    if (data / "packets_data.json").exists():
        import json
        import types
        raw = json.loads((data / "packets_data.json").read_text(encoding="utf-8"))
        for src in raw.get("SOURCES", {}).values():      # a scan's path is relative to the data folder
            src["pdf"] = data / src["pdf"]
            if isinstance(src.get("flip"), list):
                src["flip"] = set(src["flip"])
        D_ = H_ = types.SimpleNamespace(**raw)
    elif (data / "packets_data.py").exists():
        D_ = _load(data / "packets_data.py", "packets_data")
        H_ = _load(data / "packets_help.py", "packets_help") if (data / "packets_help.py").exists() else None
    else:
        raise SystemExit(f"no packets_data.json or packets_data.py in {data} (see this file's docstring)")
    get = lambda k, d: settings.get(k, getattr(D_, k, d))          # noqa: E731
    CFG = {"SUBTITLE": get("SUBTITLE", ""), "REF_LABEL": get("REF_LABEL", ""),
           "INTRO": get("INTRO", DEFAULT_INTRO)}
    FONT = dict(get("FONTS", DEFAULT_FONTS))
    missing = [p for p in FONT.values() if not Path(p).exists()]
    if missing:
        raise SystemExit(f"font file(s) not found: {', '.join(missing)}\n  Give TTFs that cover the "
                         f"macron vowels: --font-regular/--font-bold/--font-italic, or FONTS in packets_data.py.")
    FO = {k: f.Font(fontfile=v) for k, v in FONT.items()}
    SRC = get("SOURCES", {})
    HELP = getattr(H_, "HELP", {}) if H_ else {}
    GLOSS = getattr(H_, "GLOSS", {}) if H_ else {}
    clean_glob = get("CLEAN_GLOB", None)
    name_of = get("filename", _filename)

    OUT.mkdir(parents=True, exist_ok=True)
    written = [OUT / name_of(t, s) for t, s, _, _ in D_.W]
    if not audit_only:
        if clean_glob:
            for old in OUT.glob(clean_glob):
                old.unlink()
        for (title, span, dates, exs), path in zip(D_.W, written):
            D = render_week(title, span, dates, exs)
            D.d.save(path, garbage=3, deflate=True)
            print(f"  {path.name:42s} {D.d.page_count} pp  {D.n} fields  {len(exs)} exercises")
    print("PRINT AUDIT")
    return 1 if audit(sorted(OUT.glob(clean_glob)) if clean_glob else [p for p in written if p.exists()]) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True, help="folder holding packets_data.py (+ packets_help.py)")
    ap.add_argument("--out", type=Path, required=True, help="folder the PDFs are written to")
    ap.add_argument("--audit", action="store_true", help="audit the PDFs already in --out; build nothing")
    for k, n in (("r", "regular"), ("b", "bold"), ("i", "italic")):
        ap.add_argument(f"--font-{n}", dest=f"font_{k}", help=f"{n} TTF covering the macron vowels")
    a = ap.parse_args()
    fonts = {k: getattr(a, f"font_{k}") for k in "rbi" if getattr(a, f"font_{k}")}
    extra = {"FONTS": {**DEFAULT_FONTS, **fonts}} if fonts else {}
    return build(a.data, a.out, audit_only=a.audit, **extra)


if __name__ == "__main__":
    sys.exit(main())
