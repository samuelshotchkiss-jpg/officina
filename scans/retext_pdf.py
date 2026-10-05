#!/usr/bin/env python3
"""retext_pdf.py -- replace a scan's OCR text layer with a hand transcription, in place.

    python macronizer/retext_pdf.py <scan.pdf> --text clean.txt [--cit clean.cit]
    python macronizer/retext_pdf.py <scan.pdf> --text clean.txt --out fixed.pdf --apply

WHAT THIS IS FOR. A scanned reader carries an invisible OCR text layer, which is what makes it
searchable -- and on macronized Latin that layer is wrong in exactly the places that matter.
Measured on Capitulum IX: 11% of tokens unknown to Morpheus against Cloelia's 2%, 17% of lines
carrying `ã ů ë ä Ü` where the book prints a macron. `senātů` and `senātū` differ by one pixel
and by the entire quantity distinction.

So: keep the scan, keep the OCR's GEOMETRY, throw away its characters, and put the
transcription in their place. The book you own becomes searchable for what it actually says.

THE ALIGNMENT WORKS FOR ONE REASON, AND IT IS THE PROJECT'S OWN LESSON MADE MECHANICAL
--------------------------------------------------------------------------------------
OCR's LETTERS are mostly right; its DIACRITICS are what is wrong. Fold the diacritics away and
the two word sequences are nearly identical, which is precisely the signal a sequence matcher
needs. `docs/memory` puts it as *OCR is a locator, not a transcriber* -- this is that sentence
as code: the scan says WHERE, the transcription says WHAT.

Measured on Lectio I (5 pages, 260 transcribed words): **244 placed, 93.8%** -- 226 exact, 12
spanned across a line break, 6 split out of a merged OCR word. The 16 left are reported by
citation, and every one is a place where OCR damage changed the letter SKELETON rather than a
diacritic (`pūblicæ` folds to `publicae`, `exercitūù` to `exercituu`), which is the one thing
this alignment cannot see through.

WHAT IT DOES NOT DO, DELIBERATELY
---------------------------------
**No geometry heuristics.** An earlier attempt split the marginal gloss column from the running
text by clustering x-positions, and it cannot work: recto and verso mirror the columns, some
pages are single-column, and a "line" in the text layer is really a run of spans. This aligns
the word SEQUENCE instead and lets the margin fall out as unmatched -- the gloss box, the page
header and the printed line numbers are simply words the transcription does not contain, and a
sequence matcher skips them for free. Nothing here needs to know what a column is.

**No page mapping.** The transcription usually covers only the narrative pages -- Capitulum IX
is six of seventeen, the rest being `Rem tenē!` exercises. Rather than being told which, the
whole PDF's words are aligned against the whole transcription at once; an exercise page simply
matches nothing. Each OCR word carries its own page, so the matched ones know where they live.

THE FOUR THINGS THAT DO NOT ALIGN ONE-TO-ONE, all seen on real pages
--------------------------------------------------------------------
  a word broken over a line  `rēg-` + `num,`  -> one transcribed word, TWO boxes: span them
  a merged OCR word          `plēbēiðsdīvidēbātur.` -> two transcribed words, ONE box: split it
  margin text mid-word       `impe-` · *administrāre = curāre* · `rium`   -> skipped, then span
  a genuinely lost word      the scan is damaged   -> REPORTED, never invented

`--apply` refuses when the match rate falls below `--min-rate` (default 0.90), because a text
layer that is 60% right is worse than one that is 0% right: it looks searchable and silently is
not. The rate is printed per page either way.

**THE RATE COUNTS ONLY WORDS FOUND ON AN OCR BOX**, never ones inferred from a neighbour, and
that distinction is load-bearing rather than tidy. Running Lectio III's transcription against
Lectio I's scan produces **7 real matches and 233 guesses** -- and an earlier version of this
file called that 100% placed and wrote the file. Inference fills a hole; it must never be
allowed to fill a hollow.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
import unicodedata
from pathlib import Path

try:
    import fitz                                  # PyMuPDF
except ImportError:                              # pragma: no cover
    raise SystemExit(
        "this needs PyMuPDF:  .venv/Scripts/python -m pip install -r requirements.txt")


# --------------------------------------------------------------------------- folding

def fold(w: str) -> str:
    """A word reduced to what OCR and a transcription can be expected to AGREE on.

    Strips every combining mark (so `senātů`, `senātū` and `senatu` are one string), folds
    j->i and v->u as the store does everywhere else, and drops punctuation. What survives is
    the letter skeleton -- which is the part OCR usually gets right, and the reason this
    alignment is cheap.
    """
    w = unicodedata.normalize("NFD", w)
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    w = w.lower().replace("j", "i").replace("v", "u")
    # the ligature and the two OCR confusions that survive decomposition
    w = w.replace("æ", "ae").replace("œ", "oe").replace("ß", "ss")
    return re.sub(r"[^a-z]", "", w)



# --------------------------------------------------------------------------- inputs

def pdf_words(doc) -> list[dict]:
    """Every OCR word in the document, in reading order, with its page and box."""
    out = []
    for pno in range(doc.page_count):
        for x0, y0, x1, y1, w, *_ in doc[pno].get_text("words"):
            out.append({"page": pno, "rect": fitz.Rect(x0, y0, x1, y1), "text": w})
    return out


def read_transcription(text_path: Path, cit_path: Path | None) -> list[dict]:
    """Every transcribed word, in reading order, tagged with the line it came from.

    The citation is carried through so a later step can say WHICH line a placement belongs to
    -- the printed line number is the true human citation (CODEX §III.20) and the only handle a
    reader has on a prose page.
    """
    lines = text_path.read_text(encoding="utf-8").splitlines()
    cits = (cit_path.read_text(encoding="utf-8").splitlines() if cit_path else [])
    if cits and len(cits) != len(lines):
        raise SystemExit(
            f"{text_path.name} has {len(lines)} lines but {cit_path.name} has {len(cits)} "
            f"citations. They are parallel files; one line, one citation.")
    out = []
    for i, line in enumerate(lines):
        cit = cits[i] if cits else f"{text_path.stem}:{i}"
        for w in line.split():
            out.append({"text": w, "cit": cit, "line": i, "i": len(out)})
    return out


# --------------------------------------------------------------------------- alignment

def align(ocr: list[dict], mine: list[dict]) -> tuple[list[dict], list[dict]]:
    """Give each transcribed word a box. Returns (placed, unplaced).

    `placed` rows carry {text, cit, page, rect, how} where `how` names which of the four cases
    below produced the box -- kept because a run that is 95% `exact` and a run that is 95%
    `span` are not equally trustworthy, and the report should be able to say so.
    """
    ocr_keys = [fold(w["text"]) for w in ocr]
    my_keys = [fold(w["text"]) for w in mine]
    placed: list[dict] = []
    unplaced: list[dict] = []

    sm = difflib.SequenceMatcher(a=ocr_keys, b=my_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                o, m = ocr[i1 + k], mine[j1 + k]
                placed.append({**m, "page": o["page"], "rect": o["rect"], "how": "exact"})
        elif tag == "delete":
            continue                    # OCR-only: the gloss box, a header, a line number
        elif tag == "insert":
            unplaced.extend(mine[j1:j2])
        else:                           # replace -- the interesting cases
            got, lost = _reconcile(ocr[i1:i2], ocr_keys[i1:i2], mine[j1:j2], my_keys[j1:j2])
            placed.extend(got)
            unplaced.extend(lost)
    return placed, unplaced


def _reconcile(o_rows, o_keys, m_rows, m_keys) -> tuple[list[dict], list[dict]]:
    """One mismatched run. Try to explain it as joins and splits before giving up.

    Greedy and deliberately simple: walk both sides together, and at each step ask whether some
    number of OCR words concatenate to one of mine (a word broken over a line break), or one
    OCR word concatenates to some number of mine (a merge the OCR made). Anything left is
    reported rather than guessed at -- CODEX §III.18.
    """
    placed, lost = [], []
    i = j = 0
    while j < len(m_rows):
        if i >= len(o_rows):
            lost.extend(m_rows[j:])
            break
        # (a) N OCR words -> 1 of mine. `rēg-` + `num,` -> `rēgnum,`
        #
        # PREFIX-GUIDED, WITH BOUNDED SKIPS, and the skips are the whole reason this case
        # earns its keep. The margin gloss is interleaved INTO the running text by the OCR's
        # reading order, so a broken word routinely has junk sitting inside it:
        #     `magis­` · `maae` · `ARES”` · `trātūs`      -> magistrātūs
        #     `impe­`  · `administrāre = curāre,`        -> imperium
        # A run that demanded consecutive words gave up on both. Instead: keep only the OCR
        # words that EXTEND the prefix we are building, and step over at most a few that do
        # not. Bounded, because an unbounded search would eventually "find" any word.
        want = m_keys[j]
        acc, used, skipped, n = "", [], 0, 0
        while i + n < len(o_rows) and n < 12 and skipped <= 3 and len(acc) < len(want):
            k = o_keys[i + n]
            if k and want.startswith(acc + k):
                acc += k
                used.append(i + n)
            elif used:
                skipped += 1            # junk INSIDE the word: step over it
            elif k:
                break                   # nothing started yet and this is not our word
            n += 1
            if acc == want and used:
                r = fitz.Rect(o_rows[used[0]]["rect"])
                for u in used[1:]:
                    r |= o_rows[u]["rect"]
                placed.append({**m_rows[j], "page": o_rows[used[0]]["page"], "rect": r,
                               "how": "exact" if len(used) == 1 else "span"})
                i = used[-1] + 1
                j += 1
                break
        else:
            acc = None
        if acc is not None and acc == want:
            continue
        acc = None
        # (b) 1 OCR word -> M of mine. `plēbēiðsdīvidēbātur.` -> two words: split the box.
        acc, m = "", 0
        while j + m < len(m_rows) and m < 6:
            acc += m_keys[j + m]
            m += 1
            if acc == o_keys[i]:
                box = o_rows[i]["rect"]
                span = box.x1 - box.x0
                pos = 0
                for k in range(m):
                    ln = len(m_keys[j + k]) or 1
                    x0 = box.x0 + span * pos / max(1, len(acc))
                    x1 = box.x0 + span * (pos + ln) / max(1, len(acc))
                    placed.append({**m_rows[j + k], "page": o_rows[i]["page"],
                                   "rect": fitz.Rect(x0, box.y0, x1, box.y1), "how": "split"})
                    pos += ln
                i += 1
                j += m
                break
        else:
            acc = None
        if acc is not None:
            continue
        # (c) neither: this OCR word is not ours (margin text mid-word). Step over it.
        if i < len(o_rows) - 1 or len(o_rows) > len(m_rows):
            i += 1
            continue
        lost.append(m_rows[j])
        j += 1
    return placed, lost


# --------------------------------------------------------------------------- the gap filler

MAX_GAP = 3          # how far a word may look for a placed neighbour. See infer_boxes.


def infer_boxes(placed: list[dict], unplaced: list[dict]) -> tuple[list[dict], list[dict]]:
    """Give a word with no box one derived from its NEIGHBOURS. Returns (inferred, still_lost).

    THE CASE THIS EXISTS FOR is narrow and worth naming: OCR damage that changed a word's
    letter SKELETON rather than a diacritic -- `pūblicæ` folding to `publicae` against a
    transcribed `publica`, `exercitūù` to `exercituu`. The fold cannot see through those, so the
    word matches nothing; but the words on either side of it matched fine, and the hole between
    their boxes is where it goes.

    IT IS BOUNDED, AND THE BOUND IS THE POINT. A word will only borrow position from a placed
    word within `MAX_GAP` of it in the transcription. Without that, a page the alignment simply
    failed on would have every word "placed" by interpolation from two survivors a hundred words
    apart -- which is inventing geometry and would sail past `--min-rate` while producing a text
    layer that highlights nonsense. Inference is for a hole, not for a hollow.

    Everything it produces is marked `how="gap"` so the report can separate found from inferred.
    A reader trusting a highlight deserves to know which it is.
    """
    at = {w["i"]: w for w in placed}
    inferred, lost = [], []
    for w in sorted(unplaced, key=lambda r: r["i"]):
        prev = next((at[k] for k in range(w["i"] - 1, w["i"] - 1 - MAX_GAP, -1) if k in at), None)
        nxt = next((at[k] for k in range(w["i"] + 1, w["i"] + 1 + MAX_GAP) if k in at), None)
        rect = _between(prev, nxt, w["text"])
        if rect is None:
            lost.append(w)
        else:
            page = (prev or nxt)["page"]
            inferred.append({**w, "page": page, "rect": rect, "how": "gap"})
            # AN INFERRED BOX MAY NOT ANCHOR ANOTHER INFERENCE. Letting it (`at[w["i"]] = ...`)
            # made MAX_GAP vacuous: each guess became evidence for the next, so a page the
            # alignment had entirely failed on still reported 100% placed. Caught by running
            # Lectio III's transcription against Lectio I's scan -- 7 real matches, 233 guesses,
            # and it wrote the file. A guard that cascades is not a guard.
    return inferred, lost


def _between(prev, nxt, text) -> "fitz.Rect | None":
    """The box for a word sitting between two placed ones, or None."""
    same_line = (prev and nxt and prev["page"] == nxt["page"]
                 and min(prev["rect"].y1, nxt["rect"].y1)
                 - max(prev["rect"].y0, nxt["rect"].y0) > 0)
    if same_line and nxt["rect"].x0 - prev["rect"].x1 > 1:
        r, rn = prev["rect"], nxt["rect"]
        # Inset the hole slightly at both ends -- see the note on `pad` below: a box that
        # touches its neighbours extracts as one run-on word.
        per = r.width / max(1, len(prev["text"]))
        pad = min(max(2.0, per * 0.8), (rn.x0 - r.x1) / 3)
        return fitz.Rect(r.x1 + pad, min(r.y0, rn.y0), rn.x0 - pad, max(r.y1, rn.y1))
    # not a gap on one line -- lay it beside whichever neighbour we have, at that
    # neighbour's own scale, which is the only width evidence available.
    anchor, after = (prev, True) if prev else (nxt, False)
    if anchor is None:
        return None
    r = anchor["rect"]
    per = r.width / max(1, len(anchor["text"]))
    w = max(2.0, per * len(text))
    # A HAIR OF SEPARATION, because extraction infers word breaks from GEOMETRY: a box that
    # starts exactly where its neighbour ends comes back out as `rēspūblica'.In` -- searchable,
    # but not copyable as prose. One character-width of gap is enough to restore the space.
    pad = max(0.5, per * 0.5)
    return (fitz.Rect(r.x1 + pad, r.y0, r.x1 + pad + w, r.y1) if after
            else fitz.Rect(r.x0 - w - pad, r.y0, r.x0 - pad, r.y1))


# --------------------------------------------------------------------------- report

def report(doc, placed, unplaced, mine) -> float:
    by_page: dict[int, int] = {}
    how: dict[str, int] = {}
    for p in placed:
        by_page[p["page"]] = by_page.get(p["page"], 0) + 1
        how[p["how"]] = how.get(p["how"], 0) + 1
    found = sum(v for k, v in how.items() if k != "gap")
    rate = found / len(mine) if mine else 0.0

    print(f"  transcribed words        {len(mine):>6}")
    print(f"  FOUND on an OCR box      {found:>6}  ({rate:6.1%})   <- what --min-rate gates")
    print(f"  inferred from neighbours {how.get('gap', 0):>6}")
    print(f"    " + "  ".join(f"{k}={v}" for k, v in sorted(how.items())))
    print(f"  NOT placed               {len(unplaced):>6}")
    print()
    print(f"  per page ({doc.page_count} in the PDF; a page with 0 is one the "
          f"transcription does not cover):")
    for pno in range(doc.page_count):
        n = by_page.get(pno, 0)
        bar = "#" * min(40, n // 4)
        print(f"    p{pno:<3} {n:>5}  {bar}")
    if unplaced:
        print()
        print("  words with no box (reported, never invented):")
        for w in unplaced[:15]:
            print(f"     {w['cit']:<18} {w['text']!r}")
        if len(unplaced) > 15:
            print(f"     ... and {len(unplaced) - 15} more")
    return rate


# --------------------------------------------------------------------------- writing

DEFAULT_FONT = "tahoma.ttf"      # covers every macron INCLUDING ȳ -- see load_font


def load_font(name: str | None):
    """A font whose glyph set covers macronized Latin. Returns (fitz.Font, label).

    ȳ (U+0233) IS THE ONE THAT SEPARATES THEM, and this project has paid for that before: the
    typeset reader's font hunt found Verdana and Trebuchet lacking it and Tahoma carrying it.
    Checked here rather than assumed, because a missing glyph in an INVISIBLE layer fails
    silently -- the text simply is not searchable for that word, and nothing looks wrong.
    """
    import os
    tests = {"ā": 0x101, "ē": 0x113, "ī": 0x12B, "ō": 0x14D, "ū": 0x16B, "ȳ": 0x233}
    cands = [name] if name else [
        os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", DEFAULT_FONT),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in cands:
        if c and Path(c).exists():
            f = fitz.Font(fontfile=c)
            missing = [k for k, v in tests.items() if not f.has_glyph(v)]
            if missing and name:
                print(f"  ⚠ {Path(c).name} has no glyph for {' '.join(missing)}; those words "
                      f"will not be searchable.")
            if not missing:
                return f, Path(c).name
    f = fitz.Font("helv")
    print("  ⚠ falling back to base-14 Helvetica, which has no ȳ. Pass --font <ttf> if the "
          "text needs one.")
    return f, "helv"


def write_layer(doc, placed, font, label) -> int:
    """Strip the OCR text and lay the transcription over the same boxes. Returns words written.

    THE STRIP IS NARROW ON PURPOSE. `PDF_REDACT_TEXT_REMOVE_INVISIBLE` removes only text that
    was already invisible -- which is precisely the OCR layer, and nothing else on the page: the
    scan is an IMAGE, so it cannot be touched by a text redaction, and images and line art are
    explicitly told to stay. A broad redaction here would eat the book.
    """
    by_page: dict[int, list] = {}
    for w in placed:
        by_page.setdefault(w["page"], []).append(w)

    written = 0
    for pno, words in sorted(by_page.items()):
        page = doc[pno]
        page.add_redact_annot(page.rect)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                              graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                              text=fitz.PDF_REDACT_TEXT_REMOVE_INVISIBLE)
        tw = fitz.TextWriter(page.rect)
        for w in words:
            r, txt = w["rect"], w["text"]
            unit = font.text_length(txt, fontsize=1)
            if unit <= 0:
                continue
            # SIZE THE TEXT TO ITS OWN BOX rather than guessing a point size: a viewer's
            # selection rectangle and a search highlight both come from these metrics, so a
            # word typed at the wrong width highlights the wrong part of the line.
            fs = max(1.0, min(72.0, r.width / unit))
            tw.append(fitz.Point(r.x0, r.y1 + font.descender * fs), txt,
                      font=font, fontsize=fs)
            written += 1
        tw.write_text(page, render_mode=3)          # 3 = invisible
    return written


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--text", type=Path, required=True, help="the hand transcription")
    ap.add_argument("--cit", type=Path, help="its parallel citation file")
    ap.add_argument("--out", type=Path, help="write here (never over the input)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--font", type=Path, help="a TTF covering macrons (default: Tahoma)")
    ap.add_argument("--min-rate", type=float, default=0.90,
                    help="refuse --apply below this placement rate (default 0.90)")
    a = ap.parse_args()

    doc = fitz.open(a.pdf)
    ocr = pdf_words(doc)
    mine = read_transcription(a.text, a.cit)
    print(f"PDF   {a.pdf.name}  --  {doc.page_count} page(s), {len(ocr)} OCR word(s)")
    print(f"TEXT  {a.text.name}  --  {len(mine)} word(s)\n")

    placed, unplaced = align(ocr, mine)
    inferred, unplaced = infer_boxes(placed, unplaced)
    placed += inferred
    placed.sort(key=lambda r: r["i"])
    rate = report(doc, placed, unplaced, mine)

    print()
    if rate < a.min_rate:
        print(f"  ⛔ placement rate {rate:.1%} is below --min-rate {a.min_rate:.0%}.")
        print("     A text layer that is mostly right is worse than none: it looks searchable")
        print("     and silently is not. Fix the transcription, or lower the bar deliberately.")
        return 1
    if not a.apply:
        print("  DRY RUN. Re-run with --apply --out <file> to write.")
        return 0
    if not a.out:
        print("  --apply needs --out. This never writes over the scan it was given.")
        return 1
    if a.out.resolve() == a.pdf.resolve():
        print("  --out is the input. Refusing: the scan is the only copy of the book here.")
        return 1

    font, label = load_font(str(a.font) if a.font else None)
    n = write_layer(doc, placed, font, label)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(a.out), garbage=3, deflate=True)
    print(f"  wrote {a.out}  ({n} word(s), font {label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
