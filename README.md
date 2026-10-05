# Officina

*officīna, -ae* (f.): a workshop.

Small, standalone tools from a Latin teacher's working toolkit, published so that other teachers
can use them with their own texts and classes. Each folder stands on its own: take the one you
need.

| | folder | what it makes | needs |
|---|---|---|---|
| <img src="docs/worksheet.png" width="140" alt="A worksheet page"> | [`worksheets/`](worksheets/README.md) | fillable, printable exercise worksheets (PDF), checked against print-size rules so they work on paper too | Python, PyMuPDF, Pillow |
| | [`scans/`](scans/README.md) | a scanned book made searchable, with your own transcription (macrons and all) as its text | Python, PyMuPDF, Tesseract |
| | [`overlap/`](overlap/README.md) | a check that Latin you wrote imitates its source instead of quoting it | Python only |
| <img src="docs/crossword.png" width="140" alt="A crossword"> | [`renderers/`](renderers/README.md) | a course schedule and a reading quiz (Word), and a crossword (HTML), each from a JSON file | Node |

Every example here is original or public domain: the Latin is Ovid's, and the exercises, quiz,
schedule and crossword were written for these examples.

## Before you start

You will type commands into a terminal (on Windows, *PowerShell*; on a Mac, *Terminal*).
Install only what the tool you want needs:

1. **Python 3.10 or newer**, from [python.org](https://www.python.org/downloads/). Then, inside
   this folder: `pip install -r requirements.txt`.
2. **Node 18 or newer**, from [nodejs.org](https://nodejs.org/), for `renderers/` only. Then,
   inside `renderers/`: `npm install`.
3. **Tesseract**, for `scans/` only ([installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)),
   with its `script/Latin` model. Not `lat`: see [`scans/README.md`](scans/README.md).
4. **A font with macrons.** PDF's built-in fonts have no ā ē ī ō ū ȳ. On Windows the tools use
   Palatino Linotype and Tahoma, which are already installed; elsewhere, pass a TTF that has
   them (each README says how).

Every Python tool explains itself with `--help`.

## Where this comes from

These files are exported from a private toolkit that builds vocabulary lists, readers and
quizzes for one teacher's classes. The export is one-way, done by a tool that refuses to write
anything carrying an in-copyright text, a student's data or a private file. That is why some
comments in the code mention files you will not find here. The repository is updated by new
exports, not by editing it directly. Issues and suggestions are welcome.

## Built on

[PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0) · [Pillow](https://python-pillow.org/) (MIT-CMU) ·
[Tesseract](https://github.com/tesseract-ocr/tesseract) (Apache-2.0) ·
[docx](https://github.com/dolanmiu/docx) (MIT) ·
[crossword-layout-generator](https://github.com/MichaelWehar/Crossword-Layout-Generator) (MIT) ·
[Exolve](https://github.com/viresh-ratnakar/exolve) (MIT, included in `renderers/vendor/`).

## Licence

Code is AGPL-3.0, written content is CC BY-NC-SA 4.0, and the Latin is public domain.
[`COPYRIGHT.md`](COPYRIGHT.md) says which file is which.
