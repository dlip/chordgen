# chords.csv

chordgen takes a `chords.csv` file such as the following, then automatically
selects the best chords for your keyboard and layout, and adds alternate
chords depending on what type of word it is.

| word | chord | pinned | category | frequency | alt1 | alt2 | alt3 |
| ---- | ----- | ------ | -------- | --------- | ---- | ---- | ---- |
| the  |       | false  | det      | 7.40      |      |      |      |
| and  |       | false  | cconj    | 7.18      |      |      |      |
| have |       | false  | verb     | 6.78      |      |      |      |

Automatically becomes:

| word | chord | pinned | category | frequency | alt1 | alt2 | alt3   |
| ---- | ----- | ------ | -------- | --------- | ---- | ---- | ------ |
| the  | t     | false  | det      | 7.40      |      |      |        |
| and  | and   | false  | cconj    | 7.18      |      |      |        |
| have | hv    | false  | verb     | 6.78      | has  | had  | having |

The exact chord picked for each word depends on contention with the
rest of the file: `have` ends up as `hv` because higher-frequency `h`
words further down (e.g. `huh`) get the single-letter `h` chord.

This file is then used to output to a format that can be used by various
programmable keyboard firmwares (QMK, ZMK, CharaChorder) or software
remapping (Kanata).

## Reserving a chord

If you want to pin a particular chord to a word, set the `chord` column and
set `pinned` to `true`. `gen` will keep that chord exactly as written while
still using the source-defined `frequency` for ranking and learning. Its
`alt1`–`alt3` cells are preserved exactly too, including empty cells, even
when `gen.alts.overwrite` is enabled. For example:

| word  | chord | pinned | category | frequency | alt1 | alt2 | alt3 |
| ----- | ----- | ------ | -------- | --------- | ---- | ---- | ---- |
| email | em    | true   | noun     | 4.20      |      |      |      |

To pin a word that already has a generated chord, edit the chord if needed
and change `pinned` to `true`. Set it back to `false` to let `gen` reassign it.

CSV files created before the `pinned` column remain compatible. When that
column is absent, an assigned chord with an empty frequency is treated as a
legacy pin. The next `add` or accepted `gen` write adds explicit pin values;
it cannot reconstruct frequency values that were previously deleted.

To protect chords you have already learned without losing frequency data,
use `chordgen gen --preserve-learned`. This reserves current learned mappings
and their alt slots for that run; it does not edit frequency cells or create
permanent manual pins. Preview with `chordgen gen --dry-run`. Learning progress
tracks mapping identity, so changing a chord or its physical layout requires
relearning rather than inheriting the previous mapping's mastery.

## Editing chords.csv

After `setup`, `chords.csv` is yours. Common workflows:

- **Removing a word** — delete the row.
- **Pinning a chord** — set the `chord` column and set `pinned` to `true`. See
  [Reserving a chord](#reserving-a-chord).
- **Adjusting category or alts** — edit the `category` cell or
  pre-fill `alt1`–`alt3`. By default `gen` keeps non-empty alt slots
  as written; set `gen.alts.overwrite: true` in `config.yaml` to force
  regeneration on every run.
- **Re-running** — `chordgen gen` is idempotent. Unpinned chord
  cells are cleared before solving, so any change to a row's word,
  category, frequency, or alts takes effect on the next run.
