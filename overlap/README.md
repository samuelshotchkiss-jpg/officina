# Overlap: imitation or quotation?

When you write Latin "in the style of" a poet, for a story or a simplified tier of a passage,
it is easy to end up quoting him instead: a half-remembered phrase slips in, and nothing looks
wrong. `overlap.py` finds every run of three or more words that your text shares with the source.

```bash
python overlap.py my_story.txt --against metamorphoses8.txt
python overlap.py my_story.txt --against met.txt aen.txt -n 4 --fail
```

- Spelling is folded away before comparing: macrons and other marks, capitals, punctuation,
  u/v and i/j. A quotation cannot hide behind orthography.
- Runs are found across line breaks, in both texts.
- Each finding is reported once, as the longest shared run, with your line number and the
  first place it occurs in the source.
- `-n` sets the shortest run that counts (default 3). `--fail` makes it exit with status 1 when
  anything is shared, so it can serve as a check before you print.

It cannot see a paraphrase: a reordered phrase or a synonym passes. It answers "did I copy?",
not "is this original?". It needs only Python, with no packages.
