# Searchable scans

You have photographed or scanned a Latin textbook you own, and you have typed out (or will type
out) its reading by hand, macrons included. These two tools put your transcription into the scan
as its invisible text layer. The PDF still looks exactly like the book, but searching and copying
now give your text.

## Why two steps

On macronized Latin, OCR is good at finding **where** each word sits on the page, and bad at
**what** the word is: a macron comes out as a tilde, a breve or nothing. So:

1. `ocr_layer.py` runs Tesseract on each page and lays its words over the scan as invisible
   text, purely for their positions.
2. `retext_pdf.py` throws away the OCR's letters and puts your transcription in their place,
   word by word. It matches the two with the diacritics folded away: the OCR's letters are
   mostly right even when its macrons are wrong.

```bash
pip install pymupdf
python ocr_layer.py book.pdf --out lectio1.ocr.pdf --pages 3-5 --flip even
python retext_pdf.py lectio1.ocr.pdf --text lectio1.txt --out lectio1.pdf --apply
```

- `--pages` uses the page numbers your PDF viewer shows. `--flip` names pages that were scanned
  upside down (`odd`, `even`, or a list like `2,4,9`); they are turned in the viewer, and the
  image itself is not changed.
- `lectio1.txt` has one line of your transcription per printed line. An optional `--cit` file,
  with a citation on each line, makes the report name each unplaced word by its line.
- `retext_pdf.py` reports how many words it placed. It refuses to write a file in which fewer
  than 90% landed on an OCR box (`--min-rate` changes the bar), because a text layer that is
  mostly right looks searchable and silently isn't. Run it without `--apply` first to see the report.

**Tesseract.** Install it with the `script/Latin` model and use that (the default here). Do not
use `lat`: that model was trained on Latin printed without macrons, and it drops every one.
`--psm 4` (the default) suits a page with margin glosses; try `--psm 6` for a plain block of
text. If a dark gutter shadow keeps the OCR from finding words near the spine, rescanning the
pages flatter helps more than any setting.

**Fonts.** The invisible layer uses Tahoma by default (its Windows path), because it includes
the macron vowels. Pass `--font` with another TTF elsewhere.
