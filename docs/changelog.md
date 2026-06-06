# Changelog

## v2.3.0

- **Book mode resume uses file content hash.** Progress is now keyed
  by the SHA-1 of the file's bytes instead of its absolute path, so
  you can move or rename the book file and still pick up where you
  left off. The `path` field is no longer stored in `books.json`.

## v2.2.0

- **Book mode: `↑`/`↓` now move by one line instead of one
  paragraph.** Paragraph skip is still available via the existing
  `action_skip_para_fwd`/`action_skip_para_back` methods — only the
  default keybinding changed. `PgUp`/`PgDn` continue to move by half
  a screen-page.

## v2.1.0

- **Drill mode now accepts arbitrary words.** Pass words as
  positional arguments (`chordgen drill the quick brown fox`) or
  point at a whitespace-separated file with `--words-file/-f`. In
  this mode the FSRS graduated pool is bypassed and `progress.json`
  is left untouched. Words without a chord in `chords.csv` are
  silently dropped.
- **TUI layout refresh.** Train and drill modes now render the
  session stats above the word stream, with the current word
  horizontally centred on screen. The underline cursor between the
  word and its chord has been removed so the chord sits directly
  beneath the word. The keyboard view stays at the bottom.
- **Drill personal-best leaderboard.** Each completed drill records
  its WPM into a per-keyboard-layout top-5 leaderboard stored in
  `~/.config/chordgen/scores.json`. The drill summary screen shows
  the current layout's top scores (with dates) and tags new entries
  as `(new personal best!)`. The leaderboard is keyed by
  `<keyboard-type>:<layout>`; for `layout = custom` it uses the new
  `gen.keyboard.<type>.custom_layout_name` field (default `custom`)
  so multiple custom layouts can have separate scoreboards. Stored
  separately from `progress.json` so high-scores survive FSRS schema
  migrations.
- **Failed words captured at first mistype.** Drill mode records a
  word as failed the moment you mistype it, rather than when the
  word completes. This means a word the user was stuck on when the
  timer expires now correctly shows up in the failed-words list.
- **New `book` mode.** `chordgen book PATH` lets you type your way
  through an arbitrary book (`.txt`, `.md`, or `.epub`). The TUI
  shows a window of the text centred on the cursor, your keyboard
  layout pinned to the bottom, and a sliding-window WPM (default
  last 30 seconds, configurable via `book.wpm_window_seconds`).
  Words for which the user has already learned a chord (FSRS
  Review state) are highlighted in yellow; mistyping a learned
  word reveals its chord and lights up the chord keys on the
  keyboard view, mirroring drill mode's reveal-on-stumble UX.
  Cursor position is auto-saved per-book to
  `~/.config/chordgen/books.json` so re-running `chordgen book
  <path>` resumes where you left off (`--restart` to start over).
  Navigation: `←`/`→` move by word, `↑`/`↓` by paragraph,
  `PgUp`/`PgDn` by half a screen-page. Adds `ebooklib` and
  `beautifulsoup4` as dependencies.
- **Line-based rendering.** The book view now scrolls by line
  rather than by word. The cursor's line stays vertically centred
  with as many previous and following lines as fit on screen, and
  text is wrapped to a configurable `book.max_width` (default 80
  columns).
- **Typeable-character normalisation.** Smart quotes, em/en
  dashes, ligatures, accented Latin (à, é, ñ, ç, æ, œ, ß, …) and
  miscellaneous symbols (™, …, •, ©, ®, °, ×, ÷) are folded to
  their plain ASCII equivalents on load so books typed on a basic
  QWERTY layout never get stuck on an untypeable glyph.

## v2.0.0

A major release that overhauls the chord-generation pipeline and
introduces interactive practice. Highlights:

- **Train mode** — a Textual TUI backed by the FSRS spaced-repetition
  algorithm, with Anki-style daily quotas, per-word speed grading,
  leech detection, and an ASCII keyboard view that highlights chord
  keys.
- **Drill mode** — a read-only speed-drill TUI for words you've
  already graduated, with timer or word-count sessions and live WPM.
- **Vocabulary pipeline** — on-demand SUBTLEX downloads at `setup`
  time, with explicit `frequency` (Zipf) and `category` columns;
  reserve a chord by leaving its `frequency` cell empty.
- **Optimal chord assignment** — replaces the old greedy + 2-swap
  passes with a sparse minimum-cost bipartite matcher, plus
  alt-coverage filtering and optional frequency tiers.
- **Redesigned alt generator** — category/inflector registry instead
  of hard-coded UD POS tags, fully configurable from `config.yaml`.

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
  drills your chords with spaced repetition. Words flow horizontally
  across the screen; type each word followed by a space and the next
  one is appended.
- Long-term scheduling is backed by [py-fsrs](https://github.com/open-spaced-repetition/py-fsrs)
  (the FSRS algorithm). Per-word state — FSRS card, cumulative
  review count, lapse count, last-seen date, and per-word WPM EWMA —
  persists to `~/.config/chordgen/progress.json` after every word
  commit, so quitting mid-session never loses progress.
- Anki-style daily quotas: each calendar day has a budget of
  `new_words_per_day` brand-new words and `reviews_per_day` overdue
  reviews. Once both budgets are spent and any in-flight learning
  words have graduated, you land on a "No more words due today!"
  screen instead of a per-session summary.
- Anki-style queue counts under the chord row show the on-screen
  composition at a glance: blue = new, red = learning / relearning,
  green = graduated.
- New / learning words show their chord directly under the word.
  Once a word has graduated to FSRS Review state and accumulated
  `mastery_threshold` total reviews, the chord is hidden until you
  lapse on it.
- Any mistake during a word grades the review as `Again`, sending the
  card back into the learning queue. An `Again` on a card already in
  Review counts as a *lapse*; words that accumulate `leech_threshold`
  lapses are flagged as **leeches** so you can re-pin or revise the
  chord in `chords.csv`.
- Per-word speed grading: each clean word's WPM is compared to a
  rolling median of recent samples. Words below `slow_wpm_fraction`
  of the median are graded `Hard` (instead of `Good`) so FSRS
  schedules them sooner. The first word and any word that flashed
  red are excluded from speed grading.
- Words rescheduled mid-session are appended to the tail of the
  visible queue rather than inserted right after the current word,
  so the next word doesn't flip under your fingers.
- An ASCII representation of the configured keyboard renders below
  the word list, with the chord keys for the current word highlighted.
  Both `standard` and `directional` keyboard types are supported.
- The active Textual theme is persisted to `config.yaml` whenever
  you change it from the in-app command palette (`Ctrl+P`).
- New `train` block in `config.yaml`: `show_words` (default 10),
  `new_words_per_day` (default 20), `reviews_per_day` (default 200),
  `leech_threshold` (default 8), `mastery_threshold` (default 3),
  `relearn_steps` (default 3), `target_retention` (default 0.9),
  `slow_wpm_fraction` (default 0.7), `slow_min_samples` (default 20).
- New top-level `theme` field in `config.yaml`
  (default `"textual-dark"`).

### Drill mode

- New `chordgen drill` command — a read-only speed-drill TUI for
  words you've already learned. Drill mode does **not** touch FSRS
  state, lapse counters, or daily quotas; use it to warm up or
  benchmark WPM against the chords you already know.
- Word pool is restricted to cards in FSRS Review state; if no
  graduated words exist yet, drill prompts you to run
  `chordgen train` first. Words are sampled by random shuffle.
- A drill ends after a fixed word count (`drill.mode = count`,
  using `drill.count`) or a fixed timer (`drill.mode = time`, using
  `drill.time_seconds`). Default is a 30-second timed drill.
- Live WPM is displayed during the run. Chords stay hidden unless
  you make a mistake, mirroring the mastered-word behaviour in
  train mode.
- Summary screen reports WPM, accuracy, and any failed words
  (de-duplicated). Press `Tab` to start another drill (Tab also
  restarts mid-drill), or `Esc` / `Ctrl+C` to quit.
- New `drill` block in `config.yaml`: `show_words` (default 10),
  `mode` (default `"time"`), `count` (default 25),
  `time_seconds` (default 30).

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
- `assignment` block in `config.yaml` exposes `min_frequency_weight`,
  `unmatched_penalty`, `frequency_exponent` (raise the cost weight of
  frequent words so they aren't out-bid by rare ones), and
  `priority_tiers` (split the pool into frequency tiers and solve
  each in order, reserving previous-tier chords). The previous
  `top_k` and `max_swap_passes` knobs were removed; the matcher
  considers every viable option per word.
