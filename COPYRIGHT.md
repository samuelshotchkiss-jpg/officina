# Copyright and licensing

This repository combines material under separate terms, and every file is under exactly one of
them. The lists below are generated from the export manifest, so they name every file.

## 1. The Latin — public domain

The Latin of Ovid and the other ancient authors quoted in the examples is in the public domain,
and so are facts about it: a word's meaning, its forms, the length of its vowels.

## 2. Written content — CC BY-NC-SA 4.0

Licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (see
[`LICENSE-CONTENT`](LICENSE-CONTENT)): the documentation and the example inputs, which are the
exercises, quiz, schedule and crossword written for this repository.

- `README.md`
- `worksheets/README.md`
- `worksheets/example/packets_data.json`
- `scans/README.md`
- `overlap/README.md`
- `renderers/README.md`
- `renderers/examples/schedule.json`
- `renderers/examples/swyk.json`
- `renderers/examples/crossword.json`

In plain terms: others may share and adapt this material, but must credit it, may not use it
commercially, and must release adaptations under the same terms.

## 3. Code — AGPL-3.0

Licensed under the GNU Affero General Public License, version 3 (see
[`LICENSE-CODE`](LICENSE-CODE)):

- `worksheets/worksheet.py`
- `scans/ocr_layer.py`
- `scans/retext_pdf.py`
- `overlap/overlap.py`
- `renderers/schedule_docx.js`
- `renderers/swyk_docx.js`
- `renderers/crossword.js`
- `renderers/package.json`

The text these programs print on a page (labels, headings, a quiz's instructions) is part of
the program and shares its licence. In plain terms: anyone may use and modify the code,
including for their own texts and classes, but must keep it open. The Affero clause adds that
anyone who runs a modified version as a website or other network service must offer its users
the corresponding source.

## 4. Third-party code

- `renderers/vendor/exolve-m.js`, `renderers/vendor/exolve-m.css`: Exolve, MIT licence, (c) 2019 Viresh Ratnakar; see renderers/vendor/LICENSE

## Why this split

Making the code non-commercial as well would block legitimate educational reuse (teachers at
tuition-charging schools, nonprofits, open educational-resource libraries), while the AGPL
already prevents what matters: closed, proprietary versions of the code. The content stays
non-commercial; the code stays open. CC BY-NC-SA 4.0 and AGPL-3.0 are not compatible within one
file, and here they never share one. If you extract material, keep that boundary.
