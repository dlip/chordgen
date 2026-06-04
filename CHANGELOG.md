# Changelog

## v2.0.0

Note: Introduced coding agent

### Upgrading

The vocabulary pipeline and chords.csv schema have changed. Existing users must
recreate their chords.csv:

```sh
chordgen setup --force
```

This will re-download the frequency list and regenerate `chords.csv` with the
new columns. Any manual edits to the previous `chords.csv` will be lost — back
it up first if you want to preserve them.

### Train mode

- New `chordgen train` command — an interactive Textual-based TUI that
  drills your chords as a typing-practice session.
- Words flow horizontally across the screen with the chord shown
  directly beneath each word. Mastered words (those past the
  `mastery_threshold` review count) hide their chord until you lapse
  on them again.
- Long-term scheduling is backed by [py-fsrs](https://github.com/open-spaced-repetition/py-fsrs)
  (the FSRS algorithm). Per-word state — including FSRS card,
  cumulative review count, and a per-word WPM EWMA — persists to
  `~/.config/chordgen/progress.json` after each completed session.
- In-session repetition is driven by FSRS's own learning /
  relearning steps: words you fail (or type slowly) cycle back into
  the queue until they graduate to Review state, at which point they
  count toward the session goal.
- Per-word speed grading: each word's WPM is compared to a rolling
  median of recent samples; words below `slow_wpm_fraction` of the
  median are graded `Hard` (instead of `Good`), nudging FSRS to
  schedule them sooner. The first word and any word that flashed red
  during typing are excluded from speed grading.
- Sessions report WPM and the slowest words on completion. Press any
  key to start a new session, or `Esc` / `Ctrl+C` to quit.
- New `train` block in `config.yaml`:
  `practice_list_size` (default 10), `words_per_session` (default
  25), `mastery_threshold` (default 3, now total FSRS reviews),
  `relearn_steps` (default 3), `target_retention` (default 0.9),
  `slow_wpm_fraction` (default 0.7), `slow_min_samples` (default 20).

### Vocabulary pipeline

- Replaced the bundled word list with on-demand downloads from
  [SUBTLEX](https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexus)
  during `chordgen setup`.
- Added `--source` flag to choose between `subtlex-us` and `subtlex-uk`.
- Added explicit `frequency` column to `chords.csv` (Zipf scale 0–7 for SUBTLEX
  sources). Replaces the implicit row-order frequency assumption.
- Removed the `reserved_chord` column. To reserve a chord, set the `chord`
  column on a row with an empty `frequency` cell — that combination is the
  new signal for "user-pinned, leave alone". See the README for details.
- Renamed CLI flag `--min-zipf` → `--min-frequency`.
- Renamed `pos` column → `category` to match the alt-generator config naming.

### Alt generation

- Redesigned the alt-generator around a category/inflector registry instead of
  hard-coded UD POS tags.
- Added `alts` block to `config.yaml` schema with per-category options (all
  enabled by default).

### Chord assignment

- New optimal assignment algorithm in `assigner.py`:
  - Reduces the problem to a sparse minimum-weight bipartite matching solved
    exactly with `scipy.sparse.csgraph.min_weight_full_bipartite_matching`.
    Replaces the previous greedy + 2-swap + eviction passes with a single
    globally-optimal solve.
  - Cost model: `option.score * weight(word)`, where weight is the row's
    `frequency` floored at `min_frequency_weight`. Frequent words attract
    low-score (short / fast) chords.
  - Slack edges with cost `unmatched_penalty * weight` keep the matching
    feasible; words for which leaving them unmatched is cheaper than the best
    available chord are reported in diagnostics with the words holding their
    top candidates.
  - Runs in well under a second for ~2000 words.
- Alt-coverage filter: words already reachable as another row's alt (e.g.
  `made` is `make`'s past tense) no longer get their own primary chord. Cycles
  in the alt graph (e.g. `could ↔ can`) are broken by keeping the
  higher-frequency word.
- `assignment` block in `config.yaml` exposes `min_frequency_weight` and
  `unmatched_penalty`. The previous `top_k` and `max_swap_passes` knobs were
  removed; the matcher considers every viable option per word.
