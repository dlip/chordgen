# chords.csv

chordgen takes a `chords.csv` file such as the following, then automatically
selects the best chords for your keyboard and layout, and adds alternate
chords depending on what type of word it is.

| word | chord | category | frequency | alt1 | alt2 | alt3 |
| ---- | ----- | -------- | --------- | ---- | ---- | ---- |
| the  |       | det      | 7.40      |      |      |      |
| and  |       | cconj    | 7.18      |      |      |      |
| have |       | verb     | 6.78      |      |      |      |

Automatically becomes:

| word | chord | category | frequency | alt1 | alt2 | alt3   |
| ---- | ----- | -------- | --------- | ---- | ---- | ------ |
| the  | t     | det      | 7.40      |      |      |        |
| and  | and   | cconj    | 7.18      |      |      |        |
| have | hv    | verb     | 6.78      | has  | had  | having |

The exact chord picked for each word depends on contention with the
rest of the file: `have` ends up as `hv` because higher-frequency `h`
words further down (e.g. `huh`) get the single-letter `h` chord.

This file is then used to output to a format that can be used by various
programmable keyboard firmwares (QMK, ZMK, CharaChorder) or software
remapping (Kanata).

## Reserving a chord

If you want to pin a particular chord to a word, add a row by hand with
the `chord` column filled in and the `frequency` column **left empty**.
An empty `frequency` is the signal that the row was added by you, so
`gen` will keep your chord exactly as written and just generate alts
for it. For example:

| word  | chord | category | frequency | alt1 | alt2 | alt3 |
| ----- | ----- | -------- | --------- | ---- | ---- | ---- |
| email | em    | noun     |           |      |      |      |

To re-pin a word that already has a generated chord, just clear its
`frequency` cell and edit the `chord`.

## Editing chords.csv

After `setup`, `chords.csv` is yours. Common workflows:

- **Removing a word** — delete the row.
- **Pinning a chord** — add a row by hand with the `chord` column set
  and the `frequency` column left empty. See
  [Reserving a chord](#reserving-a-chord).
- **Adjusting category or alts** — edit the `category` cell or
  pre-fill `alt1`–`alt3`. By default `gen` keeps non-empty alt slots
  as written; set `gen.alts.overwrite: true` in `config.yaml` to force
  regeneration on every run.
- **Re-running** — `chordgen gen` is idempotent. Non-reserved chord
  cells are cleared before solving, so any change to a row's word,
  category, frequency, or alts takes effect on the next run.
