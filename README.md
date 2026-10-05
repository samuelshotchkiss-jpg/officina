# Latin teacher tools

Small, standalone tools from a Latin teacher's working toolkit, published so that other teachers
can use them on their own texts. Each folder stands on its own: take the one you need.

| folder | what it does | needs |
|---|---|---|
| [`worksheets/`](worksheets/README.md) | fillable, printable exercise worksheets (PDF) from a JSON file, checked against print-size rules | Python 3.10+, PyMuPDF, Pillow, a font with macrons |
| [`scans/`](scans/README.md) | make a scanned book searchable, with your own transcription as its text, macrons and all | Python, PyMuPDF, Tesseract |
| [`overlap/`](overlap/README.md) | check that a Latin composition imitates its source instead of quoting it | Python (nothing else) |
| [`renderers/`](renderers/README.md) | JSON in, Word or HTML out: a course schedule, a reading quiz, a crossword | Node 18+ |

Every example in this repository is original or public domain: the Latin is Ovid's, and the
exercises, quiz and crossword were written for these examples.

## Where this comes from

These files are exported from a private toolkit that builds vocabulary lists, readers and
quizzes for one teacher's classes. The export is one-way, done by a tool that refuses to write
anything carrying an in-copyright text, a student's data, or a private file. So this repository
is updated by new exports rather than by editing it directly. Issues and suggestions are welcome.

## Licence

Code is AGPL-3.0, written content is CC BY-NC-SA 4.0, and the Latin is public domain.
[`COPYRIGHT.md`](COPYRIGHT.md) says which file is which.
