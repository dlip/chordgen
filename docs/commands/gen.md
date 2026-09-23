# gen

Generates chords and alts for `chords.csv` in-place.

```sh
chordgen gen --dry-run           # preview without writing CSV, config, or progress
chordgen gen --preserve-learned  # keep learned mappings and their family slots
chordgen gen --yes              # explicitly accept changes to learned mappings
```

Generation lists changed chord/alt cells before writing. If a currently
learned mapping changes or disappears, it asks for confirmation; an accepted
change retires only the affected learning card. `--preserve-learned` reserves
learned mappings for this run without clearing their source frequency or
changing the manual-pinning convention. It also preserves their existing alt
slots even when alt overwrite is enabled. Ignoring a protected learned word
is a conflict and stops generation before any writes.

Progress now identifies the physical chord, actual keyboard layout, and alt
slot. Legacy cards have no original mapping identity: they are bound once to
the current dictionary with a warning, retaining their existing FSRS state.
A dry run performs that binding only in memory. Reordering the letters of a
chord or editing unrelated dictionary rows does not invalidate mastery.

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
    each word gets a unique chord and the total `score × family_weight` is
    globally minimised. Frequent words attract short / low-effort
    chords. Words for which every viable chord is already cheaper for
    another word are reported in the diagnostics.

Words shorter than `gen.min_word_length` are skipped, except rows
with `category: contraction` (`'s`, `'m`, …) which are always
eligible — they're short by construction.

By default the matcher runs a single global pass that minimises total
`score × family_weight`. If you find rare words bumping common ones onto
longer chords, set `gen.assignment.priority_tiers` in `config.yaml`
(e.g. `[500, 1000]`) to solve in tiers — top 500 most-frequent words
first, then the next 500, then the rest, with each tier's chords
reserved out of the next. This protects common words like `the` /
`and` / `have` from being out-bid by rare words competing for the
same key.

#### Tradeoffs of tiered assignment

Priority tiers give high-frequency words first pick, but they carry
observable costs:

- **Words below the tier cut can become permanently untypeable.**
  Once a key is taken by an earlier tier it is reserved forever —
  later tiers can only shift chords among themselves. On a real
  2,000-word chords.csv with `[600, 1000]` and `key_replacement` set,
  a global solve assigned chords to 94 more words (recovering `die`,
  `fall`, `learn`, `add`, `star`, `tree`, `ice`, `hurt`, `dream`,
  `wear`, and others) at ~7% higher weighted cost — the cost being a
  slightly longer chord for ~190 top-600 words. Only 7 genuinely
  blocked words remained.

- **Orphaned alts need remaining free keys.** A form counts as covered
  only if its base actually receives a chord. If that base is blocked,
  a recovery pass attempts to assign the form its own primary chord
  using remaining keys. Recovery handles coverage chains and cycles,
  but does not displace successful earlier assignments or guarantee a
  globally optimal family allocation. Unassigned rows retain their alt
  definitions so rerunning generation cannot lose those relationships.

- **Family value is potential coverage, not guaranteed coverage.** Base
  weights include their unique represented forms. A form shared by multiple
  bases contributes to the first viable owner in CSV order, and an already
  assigned primary/family takes precedence. If a prospective owner loses
  its chord, recovery can still assign the form, but earlier assignments
  are not re-optimized. This remains a heuristic around the exact matcher.

If you use tiers, watch the unmatched list in `gen` diagnostics for
moderately common words that vanished. Removing tiers (setting
`priority_tiers: []`) and running `chordgen gen` will show how many
you're really losing.

### frequency_exponent

Controls how sharply frequency amplifies cost differences between
competing words. The cost formula is:

```
form_weight = max(frequency, min_frequency_weight)^frequency_exponent
family_weight = base_weight + sum(unique covered forms' weights)
cost = chord_score × family_weight
```

Each covered form contributes at most once. Repeated slots, competing
owners, and independently assigned primaries do not double-count it. Forms
absent from the CSV contribute no invented frequency. The exponent is
applied **before** adding weights; the source-defined CSV frequency is never
rewritten or assumed to be Zipf. These are utility weights, not probabilities
or measured time savings. The exponent must be greater than zero.

- **1.0** — linear weighting. A word with frequency 6.0 is weighted 6×
  as much as a word with frequency 1.0.
- **3.0** (default) — cubic weighting. A word with frequency 6.0 is
  weighted 216× as much as a word with frequency 1.0. This strongly
  favours short chords going to high-frequency words.

Raise this if you still see rare words getting short chords at the
expense of common ones. Lower positive exponents soften that preference.

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
    "'": x      # "o'clock" → chord can use "x" wherever the apostrophe sits
```

Each key must be a single lowercase character — letters or punctuation
(useful for remapping `'` since few layouts put it on a comfortable
chord position). Each value must be a single lowercase letter that
*is* present on your keyboard. Chords containing a replaced character
will be scored against the replacement letter's key position and
effort on your keyboard.
