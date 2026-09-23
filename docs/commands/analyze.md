# analyze

Find out how much of your own writing is covered by your current dictionary,
and which available forms would be most useful to learn next.

```sh
uv run chordgen analyze ~/writing/sample.txt
uv run chordgen analyze ~/writing/notes.md --limit 10
uv run chordgen analyze ~/books/novel.epub --baseline-wpm 60
```

The command runs locally. It reads the corpus, configured `chords.csv`, and
learning progress; it does **not** upload text, change your dictionary or
config, save learning progress, or advance book-resume state.

## Coverage and recommendations

The report shows:

- **Word tokens and unique words:** repeated occurrences count separately
  toward token coverage.
- **Assigned coverage:** words available as primary chords or alt forms in
  the CSV, with a separate count for each. Primary mappings take precedence
  when a word is also an alt; shared alts use the first assigned owner.
- **Independently learned coverage:** forms whose own FSRS card is in Review
  state and whose mapping has not changed. Knowing a base does not count its
  alts as learned. Legacy cards without mapping identity count provisionally,
  with a warning: their original chord/layout cannot be verified.
- **Frequent uncovered words:** candidates to consider adding manually with
  [`chordgen add`](add.md).
- **Available but unlearned forms:** existing mappings to practise.
- **Next to learn:** available forms ranked by occurrences in this text,
  grouping alts behind an unlearned prerequisite base. A family total is
  potential coverage **after learning all listed forms**, not the immediate
  benefit of learning only its base. Each occurrence contributes once.

Recommendations use your text's counts, not source-frequency scores. Manually
pinned words with blank frequency are included. The report does not reorder
learn's queue or add absent words automatically. `--limit` (default 20) limits
entries in each list, not the corpus used for coverage totals. A family's
forms stay together even if its base does not occur in the text.

## Recall cost versus an ordinary-typing estimate

[`chordgen learn --recall`](learn.md#isolated-recall) collects clean,
unassisted prompt-to-completion observations. With `--baseline-wpm`, analysis
compares each observed form's median latency with an estimate for ordinary
typing at the supplied speed:

```text
estimated ordinary seconds = (word characters + one space) × 60 / (5 × WPM)
estimated total seconds saved = occurrences × (ordinary seconds − median recall seconds)
```

The report shows the observation count (`n`), flags recall slower than the
baseline, and lists the lowest estimated savings first. It only uses latency
observations tied to the current physical chord, keyboard layout, and alt
slot. Missing, legacy-unidentified, or changed-mapping observations cannot
support a timing claim. Without a baseline or suitable observations, it
reports insufficient data rather than inventing a speed benefit.

These are **estimates, not measured passage savings**. Prompt recognition,
recall, and execution are combined; ordinary typing cost varies by word;
transitions between typing and chording have a cost; sparse observations may
not be representative. Emitted text does not reveal whether you typed letters
or used a chord. A fast unassisted observation is not proof of chord use.
The next-to-learn ranking is based on potential token coverage, not this
estimated time saving.

## Text and repertoire limits

Analysis reuses [book mode's loader](book.md#typeable-text):

- TXT, Markdown (treated as plain text), extensionless text, and EPUB are
  accepted. EPUB document/navigation text is included as loaded, so front
  matter can affect counts.
- Smart punctuation, ligatures, and supported accented Latin characters are
  normalised. Lookup is case-insensitive and strips most punctuation while
  retaining internal apostrophes.
- Tokens are whitespace-separated. Punctuation inside a token can join its
  components during lookup; this is not a linguistic tokenizer. Markdown
  syntax, links, and code are not specially parsed.
- Numeric-only and punctuation-only tokens are excluded. Coverage therefore
  does not measure all keystrokes, punctuation, capitalisation, or sentences.
- Standalone contraction appendages are not word mappings. Unassigned bases
  do not make their alt forms available.
- CSV availability is **not** a firmware deployment check. Export filters,
  firmware limits, and the configuration installed on the keyboard may leave
  some listed mappings unavailable in practice.

## Check actual mixed-typing benefit

Use a short representative passage and keep its contents, keyboard, and
installed dictionary fixed during the comparison:

1. Run `chordgen analyze passage.txt` to understand coverage. Do not interpret
   that percentage as a speed gain.
2. Practise weak forms with `chordgen learn --recall`, or use an explicit
   custom drill such as `chordgen drill look looks looked`. Drill does not
   update FSRS. Finish familiarisation before timing the comparison.
3. Run `chordgen book passage.txt --restart` and type the passage with ordinary
   typing only. Keep hints off and use the same correction policy throughout.
4. Restart the same passage and repeat using your usual mixture of typing and
   learned chords. Restart deliberately resets that passage's saved cursor;
   book mode does not change FSRS state.
5. Alternate which condition goes first over several pairs, with breaks.
   Record whole-passage elapsed time using an external timer, correction
   counts, and discomfort. Book's displayed WPM is a sliding-window aid, not
   an automatically recorded whole-passage benchmark. Use the same timing
   boundary for both conditions, including corrections and hesitation.
6. Compare the median whole-passage results and error burden. Check another
   held-out passage to reduce the effect of memorising the first one.

This is a manual comparison: the app cannot enforce ordinary-only typing or
verify chord use. Do not count isolated recall estimates as additional measured
savings on top of a passage result.
