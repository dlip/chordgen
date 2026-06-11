# drill

Speed-drill TUI for words you've already learned. Drill mode is
**read-only** — it doesn't touch FSRS state, lapse counters, or
daily quotas. Use it as a warm-up or to benchmark your typing speed
against the chords you already know.

- The word pool is restricted to words whose FSRS card is in
  Review state (i.e. graduated through the learn mode). If no
  graduated words exist yet, drill prompts you to run
  `chordgen learn` first.
- Words are picked by random shuffle from that pool.
- A drill ends after a fixed number of words (`drill.mode = count`,
  using `drill.count`) or after a fixed amount of time
  (`drill.mode = time`, using `drill.time_seconds`). The default is
  a 30-second timed drill.
- The summary screen reports WPM, accuracy (correct / total), and
  any words you fumbled. Press `Tab` to start another drill (Tab
  also restarts mid-drill if you want to bail out), or `Esc` /
  `Ctrl+C` to quit.

### Alt chords

When the chord row for a graduated word has `alt1` / `alt2` / `alt3`
inflections, those alt forms ride along into the drill pool — so
graduating `set` also drills `sets`, `setting`, and `settings`. On
a stumble, the chord shown under the word is suffixed with the slot
digit (e.g. base shows `au`, alt1 shows `au1`, alt2 shows `au2`).
Below the keyboard an `alt1 alt2 alt3` indicator highlights the
slot you need to combine with the chord on your firmware. Set
`drill.include_alts: false` to drill only the base words from each
chord row.

### Personal-best leaderboard

Each completed drill records your WPM into a per-keyboard-layout
leaderboard stored at `~/.config/chordgen/scores.json`. The summary
screen shows the top 5 scores (with the date each was set) for the
current layout, and tags a fresh entry as `(new personal best!)`
when applicable.

The leaderboard is keyed by `<keyboard-type>:<layout>` — e.g.
`standard:qwerty` or `directional:charachorder`. When you set
`gen.keyboard.<type>.layout = custom`, the key uses your
`custom_layout_name` (default `custom`), so you can rename it to
something descriptive like `colemak-mod` and have its own scoreboard.

The scores file is intentionally separate from `progress.json` so
your high-scores survive the FSRS schema migrations that wipe
training progress.

### Drilling on arbitrary words

You can override the graduated FSRS pool by passing words directly
on the command line, or by pointing at a whitespace-separated file
of words. When run this way drill uses every word from the list
that has a chord in `chords.csv` regardless of FSRS state — words
you have already graduated to Review state are highlighted in
yellow, the rest are shown dim. Words without a chord at all are
silently dropped.

```sh
chordgen drill the quick brown fox
chordgen drill --words-file words.txt
chordgen drill -f words.txt extra inline words
```

`progress.json` is read so the highlight is honest, but never
written — drill never changes FSRS state.

### Configuration

Relevant `config.yaml` knobs (under `drill`):

| Key                  | Default | Purpose                                                                      |
| -------------------- | ------- | ---------------------------------------------------------------------------- |
| `show_words`         | 10      | Number of words shown on screen at once.                                     |
| `mode`               | `time`  | `count` ends after a fixed number of words; `time` ends after a fixed timer. |
| `count`              | 25      | Words to drill when `mode = count`.                                          |
| `time_seconds`       | 30      | Drill length in seconds when `mode = time`.                                  |
| `include_alts`       | `true`  | Include alt-slot inflections from `chords.csv` in the drill pool.            |
| `always_show_chords` | `false` | Reveal chords below every word in the row, not just on a stumble.            |
