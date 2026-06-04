# gen

Generates chords and alts for `chords.csv` in-place.

The pipeline runs in three phases:

1.  **Score** — for each word, enumerate every chord that keeps the
    first letter and preserves left-to-right order, then score each
    candidate using the configured keyboard layout (effort per key,
    same-row / same-column / scissor / directional penalties).
2.  **Generate alts** — based on the word's `category` (verb, noun,
    adjective, adverb), fill `alt1`–`alt3` with inflected forms (e.g.
    `look → looks, looked, looking`). Alt slots already filled by hand
    are kept by default.
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
