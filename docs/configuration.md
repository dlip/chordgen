# Configuration

chordgen reads its config from `~/.config/chordgen/config.yaml`,
created by `chordgen setup`. The full schema (with every option's
default) is generated from the
[pydantic config model](https://github.com/dlip/chordgen/blob/main/src/chordgen/config.py),
see [Schema](schema.md).

For non-trivial setups (custom layouts, key codes, priority tiers),
[my dotfiles](https://github.com/dlip/dotfiles/tree/main/.config/chordgen)
are a useful reference.

## Top-level keys

- **`gen`** — chord generation: vocabulary file, keyboard model,
  alt-generator categories, and assignment options. See
  [gen](commands/gen.md).
- **`output`** — which output formats to emit and per-format options
  (key codes, key positions, chord timeouts, ...). See
  [Output formats](output-formats/qmk.md).
- **`learn`** — learn-mode TUI knobs (daily quotas, leech / mastery
  thresholds, slow grading). See [learn](commands/learn.md).
- **`drill`** — drill-mode TUI knobs (mode, count, timer). See
  [drill](commands/drill.md).
- **`theme`** — Textual theme used by the learn and drill TUIs.
  Updated automatically when you change the theme via the in-app
  command palette (`Ctrl+P`).

## Ignoring words

The `gen.ignore_words` list tells `chordgen gen` to leave certain rows
alone. Ignored words remain in `chords.csv`, but they are skipped when
scoring and assigning chords, so they won't consume chord keys or
trigger "unable to find options" warnings. Their `chord` and alt slots
are cleared each run. This is useful for low-value short words
(fillers, interjections, dialect forms) that appear in frequency lists
but aren't worth a dedicated chord.

Example:

```yaml
gen:
  ignore_words:
    - oi
    - ya
    - hm
    - ho
    - em
    - eh
    - um
    - ah
    - ha
```
