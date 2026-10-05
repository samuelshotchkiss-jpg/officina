#!/usr/bin/env python3
"""ocr_layer.py -- give a scanned PDF an invisible OCR text layer, page by page, upright.

    python macronizer/ocr_layer.py scan.pdf --out searchable.pdf
    python macronizer/ocr_layer.py scan.pdf --out lectio1.pdf --pages 3-5 --flip odd
    python macronizer/ocr_layer.py scan.pdf --out x.pdf --tesseract "C:/Program Files/Tesseract-OCR/tesseract.exe"

THE FIRST HALF OF A TWO-STEP METHOD. On macronized Latin, OCR is a LOCATOR, not a transcriber:
it finds WHERE each word sits on the page well, and gets WHAT the word is wrong in exactly the
places that matter (a macron read as a tilde, a breve, nothing). So this step lays the OCR's
words over the scan as invisible text, purely for their GEOMETRY, and the second step,
`retext_pdf.py --text <your transcription>`, throws the OCR's characters away and puts the hand
transcription in their place. The book you own becomes searchable for what it actually says.

WHAT IT DOES, per selected page:
  1. copies the page into a new PDF. A page scanned upside down (--flip) gets /Rotate 180,
     which turns it in the viewer without touching a pixel;
  2. renders it UPRIGHT (the render honours the rotation) and runs Tesseract on the image;
  3. lays each recognised word over the scan as invisible text (render mode 3), mapped back
     through the rotation, so selecting and searching land on the printed word.

THE SETTLED TESSERACT CONFIG (measured on photographed textbook pages, 2026): `-l script/Latin
--oem 1`. NOT `-l lat`: that model was trained on Latin printed without macrons and drops every
one. `--psm 4` (a single column of text of variable sizes) suits a page with margin glosses;
use `--psm 6` for a plain block of text.

Needs Tesseract (with the `script/Latin` traineddata) and PyMuPDF (`pip install pymupdf`), and
a TTF that covers the macron vowels for the invisible layer (default: Tahoma on Windows).

Made general on 2026-10-04 from the toolkit's per-book script for Via Latina X-XII
(docs/WORK_ORDER_tools-tidy.md), whose page map stays private.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
DEFAULT_FONT = "C:/Windows/Fonts/tahoma.ttf"       # covers a-macron .. y-macron; Helvetica does not
FONTNAME = "ocrlat"


def find_tesseract(given: str | None) -> str:
    for cand in (given, shutil.which("tesseract"), WINDOWS_TESSERACT):
        if cand and Path(cand).exists():
            return cand
    raise SystemExit("Tesseract not found. Install it (with the script/Latin traineddata) or pass "
                     "--tesseract <path to the executable>.")


def parse_pages(spec: str | None, n: int) -> list[int]:
    """'1-3,7' (1-based, as printed in a PDF viewer) -> [0, 1, 2, 6]. None = every page."""
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        lo, hi = int(a), int(b or a)
        out += range(lo - 1, hi)
    bad = [p + 1 for p in out if not 0 <= p < n]
    if bad:
        raise SystemExit(f"--pages: the scan has {n} pages; no page {bad[0]}")
    return out


def is_flipped(rule: str | None, page: int) -> bool:
    """`page` is 1-based. rule: None | 'odd' | 'even' | '2,4,9'."""
    if not rule:
        return False
    if rule in ("odd", "even"):
        return page % 2 == (1 if rule == "odd" else 0)
    return page in {int(x) for x in rule.split(",")}


def boxes(tess: str, png: Path, lang: str, psm: int):
    """(word, x, y, w, h) in pixels, from Tesseract's TSV output."""
    p = subprocess.run([tess, str(png), "stdout", "-l", lang, "--oem", "1", "--psm", str(psm), "tsv"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise SystemExit(f"Tesseract failed: {p.stderr.strip()[-500:]}")
    for line in (p.stdout or "").splitlines()[1:]:
        f = line.split("\t")
        if len(f) >= 12 and f[11].strip():
            try:
                x, y, w, h, conf = int(f[6]), int(f[7]), int(f[8]), int(f[9]), float(f[10])
            except ValueError:
                continue
            if conf >= 0 and w > 0 and h > 0:
                yield f[11].strip(), x, y, w, h


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scan", type=Path, help="the scanned PDF")
    ap.add_argument("--out", type=Path, required=True, help="the searchable PDF to write (never the input)")
    ap.add_argument("--pages", help="which pages, 1-based as a viewer numbers them: '1-3,7' (default: all)")
    ap.add_argument("--flip", help="pages scanned upside down: 'odd', 'even', or '2,4,9' (1-based)")
    ap.add_argument("--lang", default="script/Latin", help="Tesseract language (default script/Latin)")
    ap.add_argument("--psm", type=int, default=4, help="Tesseract page-segmentation mode (default 4)")
    ap.add_argument("--dpi", type=int, default=300, help="render resolution for the OCR (default 300)")
    ap.add_argument("--font", default=DEFAULT_FONT, help="a TTF covering the macron vowels")
    ap.add_argument("--tesseract", help="path to the tesseract executable")
    a = ap.parse_args()

    import pymupdf as fitz                     # after argparse: --help needs no PyMuPDF
    if a.out.resolve() == a.scan.resolve():
        raise SystemExit("--out must not be the scan itself")
    if not Path(a.font).exists():
        raise SystemExit(f"font not found: {a.font} (pass --font with a TTF that covers the macrons)")
    tess = find_tesseract(a.tesseract)
    src = fitz.open(a.scan)
    pages = parse_pages(a.pages, src.page_count)
    scale = 72.0 / a.dpi

    doc = fitz.open()
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i in pages:
            doc.insert_pdf(src, from_page=i, to_page=i)
            pg = doc[-1]
            if is_flipped(a.flip, i + 1):
                pg.set_rotation(180)
            png = Path(tmp) / f"p{i + 1}.png"
            pg.get_pixmap(dpi=a.dpi).save(png)          # honours /Rotate: the render is upright
            rot = pg.rotation
            pg.set_rotation(0)
            pg.insert_font(fontname=FONTNAME, fontfile=a.font)
            W, H = pg.rect.width, pg.rect.height
            n = 0
            for text, x, y, w, h in boxes(tess, png, a.lang, a.psm):
                fs = max(2.0, h * scale * 0.92)
                px, py = x * scale, y * scale
                if rot == 180:
                    pg.insert_text((W - px, H - py - h * scale), text, fontsize=fs, fontname=FONTNAME,
                                   rotate=180, render_mode=3, overlay=True)
                else:
                    pg.insert_text((px, py + h * scale * 0.85), text, fontsize=fs, fontname=FONTNAME,
                                   render_mode=3, overlay=True)
                n += 1
            pg.set_rotation(rot)
            total += n
            print(f"  page {i + 1:>3}{'  (flipped)' if rot == 180 else ''}  {n} words located")
    doc.save(a.out, garbage=3, deflate=True)
    print(f"wrote {a.out}  ({len(pages)} pages, {total} OCR words)\n"
          f"  next: python macronizer/retext_pdf.py {a.out} --text <your transcription> --out <final.pdf> --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
