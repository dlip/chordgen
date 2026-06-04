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

### Configuration

Relevant `config.yaml` knobs (under `drill`):

| Key            | Default | Purpose                                                                      |
| -------------- | ------- | ---------------------------------------------------------------------------- |
| `show_words`   | 10      | Number of words shown on screen at once.                                     |
| `mode`         | `time`  | `count` ends after a fixed number of words; `time` ends after a fixed timer. |
| `count`        | 25      | Words to drill when `mode = count`.                                          |
| `time_seconds` | 30      | Drill length in seconds when `mode = time`.                                  |
