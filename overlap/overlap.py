#!/usr/bin/env python3
"""overlap.py -- does a composition QUOTE its source instead of imitating it? Read-only.

    python engine/overlap.py story.txt                          # against the active corpus's text
    python engine/overlap.py story.txt --corpus ece-mythology
    python engine/overlap.py story.txt --against a.txt b.txt    # against any text files
    python engine/overlap.py story.txt -n 4 --fail              # 4+ word runs; exit 1 on any

WHY IT EXISTS. The Cumae tiers bought this lesson: "write it in Olimpi's style" produced a
Tier 1 that had imported his CONTENT, and every gate stayed green because no gate was looking.
A style model and a source text are different things, and the difference is measurable: a
composition that shares a run of three or more words with the poet is quoting him, whether or
not anyone meant it to.

WHAT IT REPORTS: every MAXIMAL run of words the composition shares with the source -- a quoted
half-line is one finding, not five overlapping trigrams -- with the composition's line and the
first place in the source the run occurs. Spelling is folded away first (macrons and other
diacritics, case, v/u, j/i, punctuation), so a half-remembered hemistich cannot hide behind
orthography. Runs are found across line breaks on BOTH sides: a quotation does not stop at the
end of a verse.

WHAT IT CANNOT SEE: a paraphrase. Two words in common, a reordered phrase, or a synonym swap all
pass. It answers "did I copy?", not "is this original?".

Was `~/Desktop/sample_quiz/overlap.py` (2026-08-31), with the three ece texts hard-coded and
n-grams that could not cross a line break; moved into the engine 2026-10-04
(docs/WORK_ORDER_tools-tidy.md).
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:                       # reconfigure(), never a second TextIOWrapper (check_stdout_wrap)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def tokens(text: str) -> list[tuple[str, int]]:
    """(folded word, 1-based line number) for every word in `text`, in order."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        s = unicodedata.normalize("NFD", line)
        s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
        s = s.replace("v", "u").replace("j", "i")
        out += [(w, i) for w in re.findall(r"[a-z]+", s)]
    return out


def index(sources: list[Path], n: int) -> dict[tuple[str, ...], str]:
    """Every n-word run in the sources -> where it first occurs ("file:line")."""
    seen: dict[tuple[str, ...], str] = {}
    for p in sources:
        toks = tokens(p.read_text(encoding="utf-8", errors="replace"))
        words = [w for w, _ in toks]
        for i in range(len(words) - n + 1):
            seen.setdefault(tuple(words[i:i + n]), f"{p.name}:{toks[i][1]}")
    return seen


def shared_runs(comp: list[tuple[str, int]], seen: dict, n: int) -> list[tuple[int, int, str]]:
    """Maximal [start, end) token spans of the composition covered by shared n-grams."""
    words = [w for w, _ in comp]
    covered = [False] * len(words)
    where = {}
    for i in range(len(words) - n + 1):
        g = tuple(words[i:i + n])
        if g in seen:
            for k in range(i, i + n):
                covered[k] = True
            where.setdefault(i, seen[g])
    runs, i = [], 0
    while i < len(words):
        if not covered[i]:
            i += 1
            continue
        j = i
        while j < len(words) and covered[j]:
            j += 1
        first = next(where[k] for k in range(i, j) if k in where)
        runs.append((i, j, first))
        i = j
    return runs


def default_sources(argv: list[str]) -> list[Path]:
    try:
        import corpus                  # only when no --against: the tool also runs on its own
    except ImportError:
        sys.exit("no source given: pass the text to check against with --against <file> ...")
    c = corpus.selected(argv)
    if not c.raw_texts.exists():
        sys.exit(f"corpus {c.name!r} carries no running text (no {c.raw_texts.name}): "
                 f"it is a seed corpus.\n  Pass the source yourself: --against <file> ...")
    return [c.raw_texts]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("composition", type=Path, help="the text to check (UTF-8)")
    ap.add_argument("--against", type=Path, nargs="+", metavar="FILE",
                    help="source text file(s); default: the corpus's raw_texts.txt")
    ap.add_argument("--corpus", help="which corpus's text to check against (default: active)")
    ap.add_argument("-n", type=int, default=3, help="shortest run that counts (default 3)")
    ap.add_argument("--fail", action="store_true", help="exit 1 if any run is shared")
    a = ap.parse_args()
    if a.n < 2:
        ap.error("-n must be at least 2: single shared words are vocabulary, not quotation")

    sources = a.against or default_sources(sys.argv[1:])
    for p in [a.composition, *sources]:
        if not p.exists():
            sys.exit(f"no such file: {p}")
    seen = index(sources, a.n)
    comp = tokens(a.composition.read_text(encoding="utf-8", errors="replace"))
    runs = shared_runs(comp, seen, a.n)

    for i, j, first in runs:
        words = " ".join(w for w, _ in comp[i:j])
        lo, hi = comp[i][1], comp[j - 1][1]
        at = f"line {lo}" if lo == hi else f"lines {lo}-{hi}"
        print(f"  {at}: {j - i} words  '{words}'  <- also {first}")
    names = ", ".join(p.name for p in sources)
    print(f"\n{len(runs)} shared run(s) of {a.n}+ words with {names}")
    return 1 if (a.fail and runs) else 0


if __name__ == "__main__":
    sys.exit(main())
