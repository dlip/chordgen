# Configuration

chordgen reads its config from `~/.config/chordgen/config.yaml`,
created by `chordgen setup`. The full schema (with every option's
default) is generated from the
[pydantic config model](https://github.com/dlip/chordgen/blob/main/src/chordgen/config.py)
and lives in
[schema.md](https://github.com/dlip/chordgen/blob/main/schema.md).

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
- **`train`** — train-mode TUI knobs (daily quotas, leech / mastery
  thresholds, slow grading). See [train](commands/train.md).
- **`drill`** — drill-mode TUI knobs (mode, count, timer). See
  [drill](commands/drill.md).
- **`theme`** — Textual theme used by the train and drill TUIs.
  Updated automatically when you change the theme via the in-app
  command palette (`Ctrl+P`).
