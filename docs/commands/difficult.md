# difficult

Find forms to practise or inspect:

```sh
uv run chordgen difficult
uv run chordgen -c /path/to/config.yaml difficult --limit 20
```

The command reads your selected config, its dictionary CSV, and
`~/.config/chordgen/progress.json`. It does not change files, create missing
directories, reassign chords, reset cards, or start a practice session.

## Reading the rankings

**Most lapses** lists forms with at least one recorded lapse, highest first.
A lapse is an `Again` rating on a card already in FSRS Review state. Errors
while initially learning or relearning do not each add a lapse. Counts are
lifetime totals, not recent failure rates. Total reviews provide context;
they include learning and assisted attempts, so dividing lapses by reviews
would not give a reliable recall-failure rate.

A form gets the `leech` label when its lapses reach the positive
`learn.leech_threshold` (default 8). Setting this to 0 disables the label,
not the lapse list.

**Longest unassisted recalls** ranks median prompt-to-completion seconds,
longest first. Each form needs at least three valid observations to enter
this list. Every row shows its sample count. Lapse rows can show a median
with fewer samples, but those forms do not enter the recall ranking.

Rows include the current chord hint, owning base, primary/alt slot, and
word length. For example, an alt2 form with hint `lk2` uses `lk` with your
alt2 modifier. Alts have their own evidence; graduating a base or lapsing
on it does not add observations to its alts.

`--limit` defaults to 10 per ranked list. Ties use case-insensitive word
order. Truncation does not affect the totals. The primary/alt1/alt2/alt3
summary counts all verified current cards, forms with lapses, total lapses,
and forms meeting the recall minimum. These are practice-ownership counts:
primary mappings take precedence over alts and shared alts use the first
assigned owner, as in learn mode. Different slots have different exposure;
the counts are not comparative modifier failure rates.

## What the evidence can tell you

Recall samples come only from clean, hint-free attempts in
[`learn --recall`](learn.md#isolated-recall). Each stored window contains up
to 200 observations per form. The report ignores invalid values, including
booleans, nonpositive numbers and nonfinite numbers. It does not substitute
throughput samples or a WPM moving average for missing recall observations.

Timing includes thinking, word length, input, and the committing space.
The app cannot tell whether text came from a chord or ordinary typing.
Three samples is a display minimum, not a claim of statistical confidence.
Samples have no timestamps, so this report cannot identify a recent trend.

This is a descriptive ranking, separate from learn's WPM-based `Hard`
grading. The grading history pools observations without per-word mapping
identities; using it here could mix current and retired chords. A longer
recall does not by itself mean a chord is physically uncomfortable or
needs replacing. Even the fastest collection of forms has a longest one.

## Current mappings and missing data

Only an exact saved mapping identity match contributes evidence. Identity
covers the word, base, chord keys, alt slot, keyboard type, and configured
layout. Progress keys retain the dictionary's spelling, including `I`.
Here, "verified current" means that the saved identity matches. This report
does not validate chord collisions, physical key availability, or deployed
firmware. Use [`chordgen check`](check.md) for dictionary and configured
binding diagnostics; it does not verify firmware deployment either.

The report counts legacy cards with unknown identities, known changed
mappings, unavailable words, and malformed cards separately. It never binds
legacy identities or deletes old cards. A malformed card is excluded while
valid cards remain visible, with a partial-report warning.

A missing progress file is a normal fresh-learning state. A missing config
or dictionary, malformed input, or unsupported progress version is an error,
not an empty successful report. File-level input errors block the rankings.
Exit status is 0 for valid reports, including empty ones; 1 for invalid
inputs or cards; and 2 for invalid command-line arguments.

## Acting on the report

1. Run `chordgen learn --recall` to collect clean recall evidence through the
   normal FSRS queue. Initial hints and error attempts do not add samples.
2. Use `chordgen drill WORD ...` for targeted practice on selected forms.
   Drill does not update FSRS or the recall measurements in this report.
3. Run [`chordgen check`](check.md) to inspect mappings and modeled comfort.
   If a chord still needs changing, [repin it manually](../concepts/chords-csv.md#reserving-a-chord).
   Changing a base chord affects its alts too and requires relearning.
