# drill

Speed-drill TUI for words you've already learned. Drill mode is
**read-only** — it doesn't touch FSRS state, lapse counters, or
daily quotas. Use it as a warm-up or to benchmark your typing speed
against the chords you already know.

- The word pool is restricted to words whose FSRS card is in
  Review state (i.e. graduated through the train mode). If no
  graduated words exist yet, drill prompts you to run
  `chordgen train` first.
- Words are picked by random shuffle from that pool.
- A drill ends after a fixed number of words (`drill.mode = count`,
  using `drill.count`) or after a fixed amount of time
  (`drill.mode = time`, using `drill.time_seconds`). The default is
  a 30-second timed drill.
- The summary screen reports WPM, accuracy (correct / total), and
  any words you fumbled. Press `Tab` to start another drill (Tab
  also restarts mid-drill if you want to bail out), or `Esc` /
  `Ctrl+C` to quit.

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
of words. Words without a chord in `chords.csv` are silently
dropped — they simply won't appear during the drill.

```sh
chordgen drill the quick brown fox
chordgen drill --words-file words.txt
chordgen drill -f words.txt extra inline words
```

When run this way drill ignores `progress.json` entirely, so you
can practise on any list of words regardless of FSRS state.

### Configuration

Relevant `config.yaml` knobs (under `drill`):

| Key            | Default | Purpose                                                                      |
| -------------- | ------- | ---------------------------------------------------------------------------- |
| `show_words`   | 10      | Number of words shown on screen at once.                                     |
| `mode`         | `time`  | `count` ends after a fixed number of words; `time` ends after a fixed timer. |
| `count`        | 25      | Words to drill when `mode = count`.                                          |
| `time_seconds` | 30      | Drill length in seconds when `mode = time`.                                  |
