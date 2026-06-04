# train

![Training](../images/training.png)

Interactive typing-practice TUI that drills your chords using
spaced repetition. Long-term scheduling is backed by
[py-fsrs](https://github.com/open-spaced-repetition/py-fsrs) (the FSRS
algorithm); in-session repetition rides on FSRS's own
learning / relearning steps. Words flow horizontally across the
screen — type each word followed by a space, and the next one is
appended.

The session model mirrors Anki: each calendar day has a budget of
`new_words_per_day` brand-new words and `reviews_per_day` overdue
reviews. The session ends when the budget is empty and any in-flight
learning words have graduated.

- Words are picked first from cards that are overdue in the FSRS
  schedule (sorted by retrievability), then from words your typing
  speed has flagged as slow, then by descending frequency for words
  you've never seen. Each bucket is capped by the day's remaining
  review / new budget.
- New / learning words show their chord directly under the word.
  Once a word has graduated to FSRS Review state and accumulated
  `train.mastery_threshold` total reviews, the chord is hidden until
  you lapse on it again.
- Any mistake during a word grades the review as `Again`, sending the
  card back into the learning queue. An `Again` on a card already in
  Review counts as a *lapse*; words that accumulate
  `train.leech_threshold` lapses are flagged as **leeches** in the
  session summary so you can re-pin or revise the chord in
  `chords.csv`.
- Per-word speed grading: the WPM of each clean word is compared to a
  rolling median of recent samples. Words below
  `train.slow_wpm_fraction` of the median are graded `Hard` (instead
  of `Good`) so FSRS schedules them sooner. The first word of a
  session and any word that flashed red are excluded from speed
  grading.
- When a word is rescheduled mid-session it's appended to the tail of
  the visible queue rather than inserted right after the current word,
  so the next word doesn't flip under your fingers.
- Under the chord row you'll see three Anki-style counts of the
  on-screen queue: blue = new, red = learning / relearning, green =
  graduated.
- Progress is persisted to `~/.config/chordgen/progress.json` after
  every word commit, so quitting mid-session never loses your daily
  counters or FSRS state. Press `Esc` or `Ctrl+C` at any time to quit.
- Once the day's quota is exhausted you land on a "No more words due
  today!" screen — there's no per-session summary, because the train
  mode is about long-term retention rather than speed tests. For
  speed practice on words you already know, use the separate
  [`chordgen drill`](drill.md) mode.

### Useful keys during a session

| Key              | Action                                                                                                                                                |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| any letter       | type next character of the word                                                                                                                       |
| `Space`          | commit a fully-typed word                                                                                                                             |
| `Backspace`      | undo last letter                                                                                                                                      |
| `Ctrl+W`         | clear the current word (I recommend binding alt/ctrl backspace in your terminal to this and making a dedicated key on your keyboard if programmable) |
| `Esc` / `Ctrl+C` | quit the trainer                                                                                                                                      |

### Configuration

Relevant `config.yaml` knobs (under `train`):

| Key                 | Default | Purpose                                                                               |
| ------------------- | ------- | ------------------------------------------------------------------------------------- |
| `show_words`        | 10      | Number of words shown on screen at once.                                              |
| `new_words_per_day` | 20      | Daily cap on brand-new words introduced (Anki-style).                                 |
| `reviews_per_day`   | 200     | Daily cap on overdue / re-drilled review words surfaced.                              |
| `leech_threshold`   | 8       | Lapses (Again on a graduated card) before a word is flagged as a leech. 0 to disable. |
| `mastery_threshold` | 3       | Total FSRS reviews before the chord is hidden for a graduated word.                   |
| `relearn_steps`     | 3       | Number of FSRS relearning steps after a lapse (in-session re-drills).                 |
| `target_retention`  | 0.9     | FSRS desired retention rate; affects long-term interval lengths.                      |
| `slow_wpm_fraction` | 0.7     | Fraction of the rolling-median WPM under which a word is graded `Hard`.               |
| `slow_min_samples`  | 20      | Minimum WPM samples collected before slow-grading kicks in.                           |
