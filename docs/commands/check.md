# check

Inspect your current dictionary before learning or exporting it:

```sh
uv run chordgen check
uv run chordgen -c /path/to/config.yaml check --limit 20
```

This command is **read-only**. It does not rewrite config, generate assignments,
repair the CSV, bind or reset progress, create output files, or load firmware
source. It reads the selected config, its dictionary CSV, and the usual
`~/.config/chordgen/progress.json`.

## Reading the report

- **Errors** identify invalid inputs, ambiguous physical mappings, or unusable
  configured export bindings. Exit status is **1** if any errors exist.
- **Warnings** identify potential surprises that may be intentional: shared
  alt forms, generation-constraint violations, export omissions, or stale
  learning identities. Warnings alone return **0**.
- **Information** describes capabilities and comfort considerations. Long or
  same-finger chords are not automatically errors. Single-key chords, pinned
  mappings with blank frequency, and irregular word families are valid.

Each diagnostic has a stable code and affected records/words where relevant.
CSV record numbers start at 1 after the header. `--limit` defaults to 10 and
limits examples **per diagnostic group**, not the checks performed. Additional
examples are counted. Invalid CLI arguments retain the usual usage-error exit
status of 2.

## Dictionary and layout checks

The checker looks for duplicate words (case-insensitive), colliding chord key
sets (regardless of order), repeated keys inside a chord, missing layout keys,
and malformed rows or headers. The seven normal CSV columns are required;
additional named columns such as `debug` are accepted.

Active alt slots are checked for competing owners, redundant self forms, and
forms shadowed by an assigned primary. The report explains the primary or
first-owner mapping that practice currently uses. Dormant alt definitions on
unassigned rows do not imply active coverage or ownership conflicts.

Layout and effort-map dimensions must work with the configured keyboard
model. Repeated meaningful layout labels are ambiguous; `_` placeholders are
allowed. Already assigned chords are inspected as stored: `key_replacement`
is not applied to them again.

A chord rejected by the current scoring constraints produces a warning rather
than an automatic repair. It might be an intentional manual choice or a
mapping generated before you changed the constraints.

## Export selection versus deployment

Only enabled output formats are checked. The report compares the **actual
practice mapping** (base, letter keys, and alt slot), not just whether some
binding elsewhere emits the same word.

| Format | Current selection behavior |
| --- | --- |
| QMK | All assigned rows, including nonempty alt slots |
| ZMK / Kanata | First `limit` assigned rows in CSV order, including their alts; `0` means unlimited |
| CharaChorder | All assigned primary forms; no alt bindings |
| Training | Primary forms in complete blocks of ten; a final incomplete block is currently omitted |

Contraction appendages consume exporter row limits but are not included in the
standalone practice denominator. Primary-only capabilities are informational;
limit omissions and training's dropped final rows are warnings. This command
reports the training limitation without changing the exporter.

Key translations and trigger combinations are checked where the configuration
contains enough information, including alt/shift triggers and ZMK's automatic
punctuation bindings. Missing mappings, repeated resolved keys, or identical
resolved triggers are errors. A blocked target shows **selection counts only**,
not usable coverage.

This is **not a firmware compilation or deployment check**. In particular:

- QMK C aliases are treated as opaque configured symbols; no `keymap.c` parsing
  or automatic `key_codes` discovery occurs.
- Kanata source-key names are not verified against an external `defsrc`.
- Physical ZMK positions are interpreted as configured, not verified against
  the keyboard wiring or flashed layout.
- Different symbolic aliases may resolve to the same hardware key without
  the checker knowing. Installed output may differ from the configuration.
- Counts concern unshifted practice mappings, not equivalence of punctuation,
  capitalisation, macro text encoding, or all firmware-specific behavior.

## Learning progress and chord comfort

Progress identities are compared with the current repertoire and actual
configured layout. Known changed identities and cards for unavailable forms
are warnings. Legacy cards without an identity are explicitly unknown, not
verified matches. A missing progress file means a fresh learning state;
unreadable, malformed, or unsupported progress is an error, never silently
reported as an empty successful history. No migration is saved.

The report includes a chord-length distribution and examples with four or
more **letter keys**, excluding the trigger and alt modifiers. Modeled
same-finger combinations and standard-keyboard top/bottom-row scissors help
you choose chords to try physically. These are comfort prompts, not measured
speed predictions or medical/ergonomic judgments.

When an input is invalid, dependent sections are marked unavailable while
independent checks continue. Fix the indicated input and rerun; nothing is
changed automatically.
