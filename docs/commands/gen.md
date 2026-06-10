# gen

Generates chords and alts for `chords.csv` in-place.

The pipeline runs in three phases:

1.  **Score** — for each word, enumerate every chord that keeps the
    first letter and preserves left-to-right order, then score each
    candidate using the configured keyboard layout (effort per key,
    same-row / same-column / scissor / directional penalties).
2.  **Generate alts** — based on the word's `category` (verb, noun,
    adjective, adverb, pronoun), fill `alt1`–`alt3` with inflected
    forms (e.g. `look → looks, looked, looking`; `I → me, my,
    myself`). Alt slots already filled by hand are kept by default.
3.  **Assign** — solve a sparse minimum-cost bipartite matching so
    each word gets a unique chord and the total `score × frequency` is
    globally minimised. Frequent words attract short / low-effort
    chords. Words for which every viable chord is already cheaper for
    another word are reported in the diagnostics.

By default the matcher runs a single global pass that minimises total
`score × frequency`. If you find rare words bumping common ones onto
longer chords, set `gen.assignment.priority_tiers` in `config.yaml`
(e.g. `[500, 1000]`) to solve in tiers — top 500 most-frequent words
first, then the next 500, then the rest, with each tier's chords
reserved out of the next. This protects common words like `the` /
`and` / `have` from being out-bid by rare words competing for the
same key.

### frequency_exponent

Controls how sharply frequency amplifies cost differences between
competing words. The cost formula is:

```
cost = chord_score × frequency^frequency_exponent
```

- **0.0** — all words have equal weight; frequency is ignored entirely.
  Every key goes to whichever word happens to claim it cheapest.
- **1.0** — linear weighting. A word with frequency 6.0 is weighted 6×
  as much as a word with frequency 1.0.
- **3.0** (default) — cubic weighting. A word with frequency 6.0 is
  weighted 216× as much as a word with frequency 1.0. This strongly
  favours short chords going to high-frequency words.

Raise this if you still see rare words getting short chords at the
expense of common ones. Set to 0 if you want every word treated
equally regardless of how often you'll type it.

### key_replacement

If your keyboard is missing certain keys (e.g. no `q` or `z`), you can
map them to alternate letters when generating chord candidates. The
replacement affects only the chord string — the typed word stays the
same.

```yaml
gen:
  key_replacement:
    q: k        # "quick" → chord uses "k" instead of "q"
    z: s        # "zebra" → chord uses "s" instead of "z"
```

Each key must be a single lowercase letter that is absent from your
layout; each value must be a single lowercase letter that *is* present.
Chords containing a replaced letter will be scored against the
replacement letter's key position and effort on your keyboard.
