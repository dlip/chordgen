# Changelog

## v2.0.0

### Upgrading

The vocabulary pipeline and chords.csv schema have changed. Existing users must
recreate their chords.csv:

```sh
chordgen setup --force
```

This will re-download the frequency list and regenerate `chords.csv` with the
new columns. Any manual edits to the previous `chords.csv` will be lost — back
it up first if you want to preserve them.

### Vocabulary pipeline

- Replaced the bundled word list with on-demand downloads from
  [SUBTLEX](https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexus)
  during `chordgen setup`.
- Added `--source` flag to choose between `subtlex-us` and `subtlex-uk`.
- Added explicit `frequency` column to `chords.csv` (Zipf scale 0–7 for SUBTLEX
  sources). Replaces the implicit row-order frequency assumption.
- Renamed CLI flag `--min-zipf` → `--min-frequency`.
- Renamed `pos` column → `category` to match the alt-generator config naming.

### Alt generation

- Redesigned the alt-generator around a category/inflector registry instead of
  hard-coded UD POS tags.
- Added `alts` block to `config.yaml` schema with per-category options (all
  enabled by default).

### Chord assignment

- New smart-greedy assignment algorithm in `assigner.py`:
  - Frequency-weighted cost: shorter chords are preferred for higher-frequency
    words.
  - Contention-aware tie-breaking using top-K option counts.
  - 2-swap local-search pass to reduce total cost after the greedy phase.
  - Eviction recovery for words that the greedy phase left without options.
  - Per-phase cost diagnostics printed at the end of `gen`.
- Alt-coverage filter: words already reachable as another row's alt (e.g.
  `made` is `make`'s past tense) no longer get their own primary chord. Cycles
  in the alt graph (e.g. `could ↔ can`) are broken by keeping the
  higher-frequency word.
- Added `assignment` block to `config.yaml` schema (`top_k`,
  `max_swap_passes`, `min_frequency_weight`).
