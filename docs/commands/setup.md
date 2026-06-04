# setup

Creates `~/.config/chordgen/config.yaml` and downloads a
frequency-ranked `chords.csv` from SUBTLEX. After `setup`, `chords.csv`
is yours to edit by hand.

### Flags

| Flag              | Default      | Purpose                                                            |
| ----------------- | ------------ | ------------------------------------------------------------------ |
| `--source`        | `subtlex-us` | Vocabulary source. Also: `subtlex-uk`.                             |
| `--size`          | `2000`       | Number of words to keep.                                           |
| `--min-frequency` | `3.0`        | Drop words below this Zipf score (3.0 ≈ 1 occurrence per million). |
| `--force`         | off          | Overwrite an existing `chords.csv`.                                |
